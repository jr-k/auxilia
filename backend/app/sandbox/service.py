import asyncio
from uuid import UUID, uuid4

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import DomainValidationError, NotFoundError, SandboxUnavailableError
from app.sandbox.models import SandboxDB, SandboxImageDB, SandboxProviderType
from app.sandbox.provider import build_provider_from_config
from app.sandbox.repository import SandboxRepository
from app.sandbox.schemas import (
    SandboxConnectionProbe,
    SandboxConnectionResult,
    SandboxCreate,
    SandboxCreateDB,
    SandboxPatch,
    SandboxResponse,
    SandboxSecretHint,
    config_extras,
    validate_config,
)
from app.service import BaseService
from app.utils.encryption import decrypt_value, encrypt_value
from app.utils.images import ProcessedImage
from app.workspaces.dependencies import get_active_workspace_id


class SandboxService(BaseService[SandboxDB, SandboxRepository]):
    not_found_message = "Sandbox not found"

    def __init__(self, db: AsyncSession, workspace_id: UUID):
        super().__init__(db, SandboxRepository(db))
        self.workspace_id = workspace_id

    async def get_scoped(self, sandbox_id: UUID) -> SandboxDB:
        row = await self.repository.get_scoped(sandbox_id, self.workspace_id)
        if row is None:
            raise NotFoundError(self.not_found_message)
        return row

    @staticmethod
    def _validate(
        provider: SandboxProviderType, url: str, secret: str | None, config: dict
    ):
        try:
            return validate_config(provider, url=url, secret=secret, config=config)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(loc) for loc in first["loc"] if loc != "provider")
            detail = f"{field}: {first['msg']}" if field else first["msg"]
            raise DomainValidationError(
                f"The sandbox configuration is invalid because {detail}"
            ) from exc

    @staticmethod
    def to_response(row: SandboxDB) -> SandboxResponse:
        return SandboxResponse(
            **row.model_dump(exclude={"encrypted_secret"}),
            has_secret=row.encrypted_secret is not None,
        )

    async def create(self, data: SandboxCreate) -> SandboxResponse:
        validated = self._validate(data.provider, data.url, data.secret, data.config)
        row = await self.repository.create(
            SandboxCreateDB(
                workspace_id=self.workspace_id,
                name=data.name,
                description=data.description,
                provider=data.provider,
                url=data.url,
                config=config_extras(validated),
                encrypted_secret=(encrypt_value(data.secret) if data.secret else None),
            )
        )
        return self.to_response(row)

    async def list_responses(self) -> list[SandboxResponse]:
        return [
            self.to_response(row)
            for row in await self.repository.list(self.workspace_id)
        ]

    async def test_connection(
        self, data: SandboxConnectionProbe
    ) -> SandboxConnectionResult:
        """Probe a draft configuration without saving or creating a sandbox."""
        secret = data.secret
        if data.sandbox_id is not None:
            row = await self.get_scoped(data.sandbox_id)
            if row.provider != data.provider:
                raise DomainValidationError(
                    "The sandbox provider cannot be changed while testing an edit."
                )
            if not secret and row.encrypted_secret:
                secret = decrypt_value(row.encrypted_secret)

        validated = self._validate(data.provider, data.url, secret, data.config)
        try:
            provider = build_provider_from_config(validated)
            await asyncio.to_thread(provider.check_available)
        except SandboxUnavailableError as exc:
            return SandboxConnectionResult(reachable=False, error=exc.reason)
        except Exception as exc:  # noqa: BLE001 — probe failures are response data
            return SandboxConnectionResult(
                reachable=False,
                error=str(exc) or type(exc).__name__,
            )
        return SandboxConnectionResult(reachable=True)

    async def get_response(self, sandbox_id: UUID) -> SandboxResponse:
        return self.to_response(await self.get_scoped(sandbox_id))

    async def update(self, sandbox_id: UUID, data: SandboxPatch) -> SandboxResponse:
        row = await self.get_scoped(sandbox_id)

        # Re-validate the merged result before mutating anything, so a patch
        # can never leave an invalid config behind. An omitted/empty secret
        # keeps the stored one (write-only field).
        url = data.url if data.url is not None else row.url
        # Overlay, not replace: the stored config always carries every field
        # (defaults materialized on write), so a partial patch must not reset
        # the fields it omits back to defaults.
        config = (
            {**row.config, **data.config} if data.config is not None else row.config
        )
        secret = data.secret or (
            decrypt_value(row.encrypted_secret) if row.encrypted_secret else None
        )
        validated = self._validate(row.provider, url, secret, config)

        updated = await self.repository.update(row, data)
        updated.config = config_extras(validated)
        if data.secret:
            updated.encrypted_secret = encrypt_value(data.secret)
        self.db.add(updated)
        await self.db.flush()
        await self.db.refresh(updated)
        return self.to_response(updated)

    async def delete(self, sandbox_id: UUID) -> None:
        """Delete the sandbox row. Refused while agents are bound: the binding
        FK has no cascade (consistent with MCP bindings), so the flush fails
        and surfaces as a clean 400. Detaching agents and forgetting the
        thread stamps this sandbox issued are the agents' and threads' jobs —
        the router composes them before this (#369). Threads are never bound
        to a sandbox, so detached agents simply run without code execution
        afterwards."""
        row = await self.get_scoped(sandbox_id)
        try:
            await self.repository.delete(row)
        except IntegrityError as exc:
            raise DomainValidationError(
                "This sandbox is used by agents; detach it first."
            ) from exc

    async def get_image(self, sandbox_id: UUID) -> SandboxImageDB:
        await self.get_scoped(sandbox_id)
        image = await self.repository.get_image(sandbox_id)
        if image is None:
            raise NotFoundError("Sandbox image not found")
        return image

    async def set_image(self, sandbox_id: UUID, image: ProcessedImage) -> UUID:
        await self.get_scoped(sandbox_id)
        revision = uuid4()
        await self.repository.set_image(
            sandbox_id,
            data=image.data,
            media_type=image.media_type,
            sha256=image.sha256,
            revision=revision,
        )
        return revision

    async def delete_image(self, sandbox_id: UUID) -> None:
        await self.get_scoped(sandbox_id)
        await self.repository.delete_image(sandbox_id)

    async def get_secret_hint(self, sandbox_id: UUID) -> SandboxSecretHint:
        row = await self.get_scoped(sandbox_id)
        if not row.encrypted_secret:
            return SandboxSecretHint(is_set=False)
        secret = decrypt_value(row.encrypted_secret)
        # Only reveal the last 4 for secrets long enough that it stays a small
        # fraction of the value; short secrets return length only.
        last4 = secret[-4:] if len(secret) >= 10 else None
        return SandboxSecretHint(is_set=True, last4=last4, length=len(secret))


def get_sandbox_service(
    db: AsyncSession = Depends(get_db),
    workspace_id: UUID = Depends(get_active_workspace_id),
) -> SandboxService:
    return SandboxService(db, workspace_id)
