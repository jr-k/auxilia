from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth.dependencies import require_admin
from app.database_connections.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionPatch,
    DatabaseConnectionResponse,
    DatabaseConnectorStatusResponse,
    SQLiteFileResponse,
)
from app.database_connections.service import (
    DatabaseConnectionService,
    get_database_connection_service,
)
from app.users.models import UserDB


router = APIRouter(
    prefix="/database-connections",
    tags=["database-connections"],
)


@router.get("/", response_model=list[DatabaseConnectionResponse])
async def list_database_connections(
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> list[DatabaseConnectionResponse]:
    return await service.list_responses()


@router.get("/status", response_model=DatabaseConnectorStatusResponse)
async def get_database_connector_status(
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectorStatusResponse:
    return await service.status()


@router.post("/", response_model=DatabaseConnectionResponse, status_code=201)
async def create_database_connection(
    data: DatabaseConnectionCreate,
    current_user: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectionResponse:
    return await service.create(data, current_user)


@router.post("/sqlite-files", response_model=SQLiteFileResponse, status_code=201)
async def upload_sqlite_file(
    file: UploadFile = File(...),
    current_user: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> SQLiteFileResponse:
    return await service.upload_sqlite_file(file, current_user)


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
async def get_database_connection(
    connection_id: UUID,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectionResponse:
    return await service.to_response(await service.get_scoped(connection_id))


@router.patch("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_database_connection(
    connection_id: UUID,
    data: DatabaseConnectionPatch,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectionResponse:
    return await service.update(connection_id, data)


@router.post("/{connection_id}/reconcile", status_code=202)
async def reconcile_database_connection(
    connection_id: UUID,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> dict[str, str]:
    await service.request_reconcile(connection_id)
    return {"status": "pending"}


@router.delete("/{connection_id}", status_code=204)
async def delete_database_connection(
    connection_id: UUID,
    detach_agents: bool = False,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> None:
    await service.delete(connection_id, detach_agents=detach_agents)
