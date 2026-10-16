from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response

from app.auth.dependencies import get_current_user, require_editor
from app.skills.schemas import (
    SkillAgentRef,
    SkillResponse,
    SkillSave,
    SkillSummary,
)
from app.skills.service import SkillService, get_skill_service
from app.users.models import UserDB
from app.utils.images import image_response, process_uploaded_image


router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/", response_model=list[SkillSummary])
async def list_skills(
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
):
    return await service.list_summaries(user)


@router.post("/", response_model=SkillResponse, status_code=201)
async def create_skill(
    data: SkillSave,
    # Editors curate the library. A skill is instructions every agent in the
    # workspace can be given, under a name nobody else can then use — reading
    # and using one is open to everyone, but putting one there is not.
    user: UserDB = Depends(require_editor),
    service: SkillService = Depends(get_skill_service),
):
    return await service.create(data, user)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: UUID,
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
):
    return await service.get(skill_id, user)


@router.get("/{skill_id}/image", response_class=Response)
async def get_skill_image(
    skill_id: UUID,
    if_none_match: str | None = Header(default=None),
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> Response:
    image = await service.get_image(skill_id, user)
    return image_response(
        data=image.data,
        media_type=image.media_type,
        digest=image.sha256,
        if_none_match=if_none_match,
    )


@router.put("/{skill_id}/image")
async def set_skill_image(
    skill_id: UUID,
    file: UploadFile = File(...),
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> dict[str, UUID]:
    image = await process_uploaded_image(file)
    return {"image_revision": await service.set_image(skill_id, user, image)}


@router.delete("/{skill_id}/image", status_code=204)
async def delete_skill_image(
    skill_id: UUID,
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> None:
    await service.delete_image(skill_id, user)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: UUID,
    data: SkillSave,
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
):
    return await service.update(skill_id, data, user)


@router.get("/{skill_id}/agents", response_model=list[SkillAgentRef])
async def list_skill_agents(
    skill_id: UUID,
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
) -> list[SkillAgentRef]:
    return await service.list_bound_agents(skill_id, user)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: UUID,
    detach_agents: bool = False,
    user: UserDB = Depends(get_current_user),
    service: SkillService = Depends(get_skill_service),
):
    await service.delete(skill_id, user, detach_agents=detach_agents)
