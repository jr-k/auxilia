from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response

from app.agents.core.service import AgentService, get_agent_service
from app.auth.dependencies import get_current_user, require_admin
from app.sandbox.models import SandboxDB
from app.sandbox.schemas import (
    SandboxAgentResponse,
    SandboxConnectionProbe,
    SandboxConnectionResult,
    SandboxCreate,
    SandboxPatch,
    SandboxResponse,
    SandboxSecretHint,
)
from app.sandbox.service import SandboxService, get_sandbox_service
from app.threads.service import ThreadService, get_thread_service
from app.users.models import UserDB
from app.utils.images import image_response, process_uploaded_image


sandboxes_router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])


async def get_sandbox_dependency(
    sandbox_id: UUID,
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxDB:
    return await service.get_scoped(sandbox_id)


@sandboxes_router.get("/", response_model=list[SandboxResponse])
async def list_sandboxes(
    _: UserDB = Depends(get_current_user),
    service: SandboxService = Depends(get_sandbox_service),
) -> list[SandboxResponse]:
    return await service.list_responses()


@sandboxes_router.post("/", response_model=SandboxResponse, status_code=201)
async def create_sandbox(
    data: SandboxCreate,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxResponse:
    return await service.create(data)


@sandboxes_router.post(
    "/test-connection",
    response_model=SandboxConnectionResult,
)
async def test_sandbox_connection(
    data: SandboxConnectionProbe,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxConnectionResult:
    return await service.test_connection(data)


@sandboxes_router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: UUID,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxResponse:
    return await service.get_response(sandbox_id)


@sandboxes_router.get("/{sandbox_id}/image", response_class=Response)
async def get_sandbox_image(
    sandbox_id: UUID,
    if_none_match: str | None = Header(default=None),
    _: UserDB = Depends(get_current_user),
    service: SandboxService = Depends(get_sandbox_service),
) -> Response:
    image = await service.get_image(sandbox_id)
    return image_response(
        data=image.data,
        media_type=image.media_type,
        digest=image.sha256,
        if_none_match=if_none_match,
    )


@sandboxes_router.put("/{sandbox_id}/image")
async def set_sandbox_image(
    sandbox_id: UUID,
    file: UploadFile = File(...),
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> dict[str, UUID]:
    image = await process_uploaded_image(file)
    return {"image_revision": await service.set_image(sandbox_id, image)}


@sandboxes_router.delete("/{sandbox_id}/image", status_code=204)
async def delete_sandbox_image(
    sandbox_id: UUID,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> None:
    await service.delete_image(sandbox_id)


@sandboxes_router.get(
    "/{sandbox_id}/agents",
    response_model=list[SandboxAgentResponse],
    # In this order: the admin gate first, so a non-admin cannot tell an
    # existing sandbox id from a missing one by 404 vs 403.
    dependencies=[Depends(require_admin), Depends(get_sandbox_dependency)],
)
async def list_sandbox_agents(
    sandbox_id: UUID,
    agents: AgentService = Depends(get_agent_service),
) -> list[SandboxAgentResponse]:
    return await agents.list_for_sandbox(sandbox_id)


@sandboxes_router.get("/{sandbox_id}/secret-hint", response_model=SandboxSecretHint)
async def get_sandbox_secret_hint(
    sandbox_id: UUID,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxSecretHint:
    return await service.get_secret_hint(sandbox_id)


@sandboxes_router.patch("/{sandbox_id}", response_model=SandboxResponse)
async def update_sandbox(
    sandbox_id: UUID,
    data: SandboxPatch,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
) -> SandboxResponse:
    return await service.update(sandbox_id, data)


@sandboxes_router.delete("/{sandbox_id}", status_code=204)
async def delete_sandbox(
    sandbox_id: UUID,
    detach_agents: bool = False,
    _: UserDB = Depends(require_admin),
    service: SandboxService = Depends(get_sandbox_service),
    agents: AgentService = Depends(get_agent_service),
    threads: ThreadService = Depends(get_thread_service),
) -> None:
    """Composes three modules in the direction they depend: bindings belong
    to agents, the stamps to threads, the row to sandboxes. One request
    transaction, so a refused delete (still bound, no `detach_agents`) rolls
    the whole thing back."""
    if detach_agents:
        await agents.detach_sandbox(sandbox_id)
    # The threads this sandbox issued ids to lose their stamp with it.
    # `sandbox_source_id` is ON DELETE SET NULL, and a null source reads as
    # "legacy, reconnect" — so without this the dead id would look reusable
    # to whatever provider the agent is rebound to next.
    await threads.clear_sandbox(sandbox_id)
    await service.delete(sandbox_id)
