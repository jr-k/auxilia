from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response

from app.appearance.schemas import (
    WorkspaceAppearancePatch,
    WorkspaceAppearanceResponse,
)
from app.appearance.service import (
    WorkspaceAppearanceService,
    get_workspace_appearance_service,
)
from app.auth.dependencies import require_admin
from app.exceptions import NotFoundError
from app.users.models import UserDB
from app.utils.images import image_response, process_uploaded_image


router = APIRouter(prefix="/appearance", tags=["appearance"])


@router.get("/", response_model=WorkspaceAppearanceResponse)
async def get_workspace_appearance(
    service: WorkspaceAppearanceService = Depends(get_workspace_appearance_service),
) -> WorkspaceAppearanceResponse:
    return await service.get_settings()


@router.patch("/", response_model=WorkspaceAppearanceResponse)
async def update_workspace_appearance(
    data: WorkspaceAppearancePatch,
    _: UserDB = Depends(require_admin),
    service: WorkspaceAppearanceService = Depends(get_workspace_appearance_service),
) -> WorkspaceAppearanceResponse:
    return await service.update_name(data.app_name)


@router.get("/logo")
async def get_workspace_logo(
    if_none_match: str | None = Header(default=None),
    service: WorkspaceAppearanceService = Depends(get_workspace_appearance_service),
) -> Response:
    row = await service.get_logo()
    if (
        row is None
        or row.logo_data is None
        or row.logo_media_type is None
        or row.logo_sha256 is None
    ):
        raise NotFoundError("Workspace logo not found")
    return image_response(
        data=row.logo_data,
        media_type=row.logo_media_type,
        digest=row.logo_sha256,
        if_none_match=if_none_match,
    )


@router.put("/logo", response_model=WorkspaceAppearanceResponse)
async def upload_workspace_logo(
    image: UploadFile = File(...),
    _: UserDB = Depends(require_admin),
    service: WorkspaceAppearanceService = Depends(get_workspace_appearance_service),
) -> WorkspaceAppearanceResponse:
    return await service.set_logo(await process_uploaded_image(image))


@router.delete("/logo", response_model=WorkspaceAppearanceResponse)
async def delete_workspace_logo(
    _: UserDB = Depends(require_admin),
    service: WorkspaceAppearanceService = Depends(get_workspace_appearance_service),
) -> WorkspaceAppearanceResponse:
    return await service.delete_logo()
