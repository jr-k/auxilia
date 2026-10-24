from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.auth.dependencies import require_admin
from app.database import get_db
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


@router.get("/{connection_id}/sqlite-file", response_class=FileResponse)
async def download_sqlite_file(
    connection_id: UUID,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    source = await service.get_sqlite_download_source(connection_id)
    # Release the request transaction before snapshotting and streaming a file
    # that may be up to 1 GiB; neither operation needs a pooled DB connection.
    await db.commit()
    download = await service.prepare_sqlite_download(source)
    return FileResponse(
        download.path,
        media_type="application/vnd.sqlite3",
        filename=download.filename,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(download.path.unlink, missing_ok=True),
    )


@router.patch("/{connection_id}", response_model=DatabaseConnectionResponse)
async def update_database_connection(
    connection_id: UUID,
    data: DatabaseConnectionPatch,
    _: UserDB = Depends(require_admin),
    service: DatabaseConnectionService = Depends(get_database_connection_service),
) -> DatabaseConnectionResponse:
    result = await service.update(connection_id, data)
    if result.replaced_file is not None:
        # Commit the new file reference before deleting the old file, which is a
        # non-rollbackable filesystem side effect.
        await service.db.commit()
        await service.cleanup_replaced_file(result.replaced_file)
    return result.response


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
