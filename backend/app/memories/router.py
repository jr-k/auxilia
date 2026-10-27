from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.memories.schemas import (
    MemoryCategoryCreate,
    MemoryCategoryOrder,
    MemoryCategoryPatch,
    MemoryCategoryResponse,
    MemoryCreate,
    MemoryLibraryResponse,
    MemoryPatch,
    MemoryPreferencesPatch,
    MemoryPreferencesResponse,
    MemoryResponse,
)
from app.memories.service import MemoryService, get_memory_service
from app.users.models import UserDB


router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("/", response_model=MemoryLibraryResponse)
async def list_memories(
    q: str | None = None,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryLibraryResponse:
    return await service.list_library(current_user.id, q)


@router.get("/categories", response_model=list[MemoryCategoryResponse])
async def list_memory_categories(
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> list[MemoryCategoryResponse]:
    return await service.list_categories(current_user.id)


@router.post(
    "/categories",
    response_model=MemoryCategoryResponse,
    status_code=201,
)
async def create_memory_category(
    data: MemoryCategoryCreate,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryCategoryResponse:
    return await service.create_category(current_user.id, data)


@router.put("/categories/order", response_model=list[MemoryCategoryResponse])
async def reorder_memory_categories(
    data: MemoryCategoryOrder,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> list[MemoryCategoryResponse]:
    return await service.reorder_categories(current_user.id, data.category_ids)


@router.patch(
    "/categories/{category_id}",
    response_model=MemoryCategoryResponse,
)
async def update_memory_category(
    category_id: UUID,
    data: MemoryCategoryPatch,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryCategoryResponse:
    return await service.update_category(category_id, current_user.id, data)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_memory_category(
    category_id: UUID,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> None:
    await service.delete_category(category_id, current_user.id)


@router.get("/preferences", response_model=MemoryPreferencesResponse)
async def get_memory_preferences(
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferencesResponse:
    return await service.get_preferences(current_user.id)


@router.patch("/preferences", response_model=MemoryPreferencesResponse)
async def update_memory_preferences(
    data: MemoryPreferencesPatch,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryPreferencesResponse:
    return await service.set_auto_capture(current_user.id, data.auto_capture_enabled)


@router.post("/", response_model=MemoryResponse, status_code=201)
async def create_memory(
    data: MemoryCreate,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    return await service.create_memory(current_user.id, data)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    data: MemoryPatch,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> MemoryResponse:
    return await service.update_memory(memory_id, current_user.id, data)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: UUID,
    current_user: UserDB = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
) -> None:
    await service.delete_memory(memory_id, current_user.id)
