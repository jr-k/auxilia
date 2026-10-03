from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.two_factor import (
    build_otpauth_uri,
    build_qr_code_data_url,
    create_scoped_token,
    decode_scoped_token,
    find_backup_code,
    generate_backup_codes,
    generate_totp_secret,
    hash_backup_code,
    verify_totp,
)
from app.auth.utils import get_password_hash, verify_password
from app.database import get_db
from app.exceptions import (
    AlreadyExistsError,
    DomainValidationError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.pagination import Page, PageParams
from app.service import BaseService
from app.teams.repository import TeamRepository
from app.users.models import UserDB, UserImageDB, UserTwoFactorDB, WorkspaceRole
from app.users.repository import UserRepository
from app.users.schemas import (
    BackupCodesResponse,
    PasswordChange,
    ProfilePatch,
    TwoFactorConfirmRequest,
    TwoFactorDisableRequest,
    TwoFactorRegenerateRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatus,
    UserCreate,
    UserPatch,
    UserResponse,
    UserRoleCounts,
    UserRolePatch,
    UserTeamPatch,
)
from app.utils.encryption import decrypt_value, encrypt_value
from app.utils.images import ProcessedImage


class UserService(BaseService[UserDB, UserRepository]):
    not_found_message = "User not found"

    def __init__(self, db: AsyncSession):
        super().__init__(db, UserRepository(db))
        self.team_repository = TeamRepository(db)

    async def _ensure_email_available(self, email: str) -> None:
        if await self.repository.get_by_email(email):
            raise AlreadyExistsError("Email already registered")

    async def create(self, data: UserCreate) -> UserDB:
        if data.email:
            await self._ensure_email_available(data.email)
        return await self.repository.create(data)

    async def get(self, user_id: UUID) -> UserDB:
        return await self.get_or_404(user_id)

    async def get_by_email(self, email: str) -> UserDB:
        user = await self.repository.get_by_email(email)
        if not user:
            raise NotFoundError(self.not_found_message)
        return user

    async def update_profile(self, user: UserDB, data: ProfilePatch) -> UserDB:
        first_name = data.first_name.strip() or None
        last_name = data.last_name.strip() or None
        user.first_name = first_name
        user.last_name = last_name
        user.name = " ".join(part for part in (first_name, last_name) if part) or None
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: UserDB, data: PasswordChange) -> None:
        await self._verify_current_password(user, data.current_password)
        user.password_hash = await get_password_hash(data.new_password)
        self.db.add(user)
        await self.db.flush()

    async def get_image(self, user_id: UUID) -> UserImageDB:
        await self.get_or_404(user_id)
        image = await self.repository.get_image(user_id)
        if image is None:
            raise NotFoundError("User image not found")
        return image

    async def set_image(self, user_id: UUID, image: ProcessedImage) -> UUID:
        await self.get_or_404(user_id)
        revision = uuid4()
        await self.repository.set_image(
            user_id,
            data=image.data,
            media_type=image.media_type,
            sha256=image.sha256,
            revision=revision,
        )
        return revision

    async def delete_image(self, user_id: UUID) -> None:
        await self.get_or_404(user_id)
        await self.repository.delete_image(user_id)

    async def get_two_factor_status(self, user: UserDB) -> TwoFactorStatus:
        two_factor = await self.repository.get_two_factor(user.id)
        return TwoFactorStatus(
            enabled=user.two_factor_enabled and two_factor is not None,
            backup_codes_remaining=(
                len(two_factor.backup_code_hashes) if two_factor else 0
            ),
        )

    async def begin_two_factor_setup(
        self, user: UserDB, data: TwoFactorSetupRequest
    ) -> TwoFactorSetupResponse:
        if user.two_factor_enabled:
            raise DomainValidationError("Two-factor authentication is already enabled")
        await self._verify_current_password(user, data.current_password)
        secret = generate_totp_secret()
        otpauth_uri = build_otpauth_uri(secret, user.email or str(user.id))
        return TwoFactorSetupResponse(
            secret=secret,
            otpauth_uri=otpauth_uri,
            qr_code_data_url=build_qr_code_data_url(otpauth_uri),
            setup_token=create_scoped_token(user.id, "two_factor_setup", secret=secret),
        )

    async def confirm_two_factor_setup(
        self, user: UserDB, data: TwoFactorConfirmRequest
    ) -> BackupCodesResponse:
        if user.two_factor_enabled:
            raise DomainValidationError("Two-factor authentication is already enabled")
        decoded = decode_scoped_token(data.setup_token, "two_factor_setup")
        if decoded is None or decoded[0] != user.id or not decoded[1]:
            raise DomainValidationError("Two-factor setup has expired")
        secret = decoded[1]
        if not verify_totp(secret, data.code):
            raise InvalidCredentialsError("Invalid authentication code")
        backup_codes = generate_backup_codes()
        await self.repository.set_two_factor(
            user.id,
            secret_encrypted=encrypt_value(secret),
            backup_code_hashes=[hash_backup_code(code) for code in backup_codes],
        )
        return BackupCodesResponse(backup_codes=backup_codes)

    async def disable_two_factor(
        self, user: UserDB, data: TwoFactorDisableRequest
    ) -> None:
        await self._verify_current_password(user, data.current_password)
        await self.verify_second_factor(user.id, data.code)
        await self.repository.disable_two_factor(user.id)

    async def regenerate_backup_codes(
        self, user: UserDB, data: TwoFactorRegenerateRequest
    ) -> BackupCodesResponse:
        await self._verify_current_password(user, data.current_password)
        two_factor = await self.verify_second_factor(user.id, data.code)
        backup_codes = generate_backup_codes()
        await self.repository.set_backup_code_hashes(
            two_factor,
            [hash_backup_code(code) for code in backup_codes],
        )
        return BackupCodesResponse(backup_codes=backup_codes)

    async def verify_second_factor(self, user_id: UUID, code: str) -> UserTwoFactorDB:
        two_factor = await self.repository.get_two_factor(user_id, for_update=True)
        if two_factor is None:
            raise InvalidCredentialsError("Two-factor authentication is not enabled")
        secret = decrypt_value(two_factor.secret_encrypted)
        if verify_totp(secret, code):
            return two_factor
        backup_index = find_backup_code(code, two_factor.backup_code_hashes)
        if backup_index is None:
            raise InvalidCredentialsError("Invalid authentication code")
        remaining = list(two_factor.backup_code_hashes)
        remaining.pop(backup_index)
        await self.repository.set_backup_code_hashes(two_factor, remaining)
        return two_factor

    @staticmethod
    async def _verify_current_password(
        user: UserDB, current_password: str | None
    ) -> None:
        if user.password_hash is None:
            return
        if not current_password or not await verify_password(
            current_password, user.password_hash
        ):
            raise InvalidCredentialsError("Current password is incorrect")

    async def list(
        self,
        page: PageParams,
        role: WorkspaceRole | None = None,
        search: str | None = None,
    ) -> Page[UserResponse]:
        users, total = await self.repository.list(page, role=role, search=search)
        items = [UserResponse.model_validate(user) for user in users]
        return Page.build(items, total, page)

    async def count_by_role(self) -> UserRoleCounts:
        counts = await self.repository.count_by_role()
        return UserRoleCounts(
            total=sum(counts.values()),
            member=counts.get(WorkspaceRole.member, 0),
            editor=counts.get(WorkspaceRole.editor, 0),
            admin=counts.get(WorkspaceRole.admin, 0),
        )

    async def list_by_ids(self, user_ids: list[UUID]) -> list[UserDB]:
        return await self.repository.list_by_ids(user_ids)

    async def update(self, user_id: UUID, data: UserPatch) -> UserDB:
        user = await self.get_or_404(user_id)
        update_data = data.model_dump(exclude_unset=True)
        new_email = update_data.get("email")
        if "email" in update_data and new_email is not None and new_email != user.email:
            await self._ensure_email_available(new_email)
        return await self.repository.update(user, data)

    async def update_role(self, user_id: UUID, data: UserRolePatch) -> UserDB:
        user = await self.get_or_404(user_id)
        return await self.repository.update(user, data)

    async def update_team(self, user_id: UUID, data: UserTeamPatch) -> UserDB:
        user = await self.get_or_404(user_id)
        if data.team_id is not None and not await self.team_repository.get(
            data.team_id
        ):
            raise NotFoundError("Team not found")
        return await self.repository.update(user, data)

    async def delete(self, user_id: UUID) -> None:
        user = await self.get_or_404(user_id)
        await self.repository.delete(user)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)
