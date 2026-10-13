import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile

from app.database_connections.settings import database_file_settings
from app.exceptions import DomainValidationError


_SQLITE_HEADER = b"SQLite format 3\x00"
_ALLOWED_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredSQLiteFile:
    original_name: str
    stored_name: str
    size_bytes: int


def _clean_name(filename: str | None) -> str:
    name = Path(filename or "").name.strip()
    if (
        not name
        or len(name) > 255
        or any(char in name for char in "\r\n\x00")
        or Path(name).suffix.lower() not in _ALLOWED_SUFFIXES
    ):
        raise DomainValidationError(
            "Upload a SQLite file ending in .db, .sqlite, or .sqlite3"
        )
    return name


def _copy_upload(stream: BinaryIO, original_name: str) -> StoredSQLiteFile:
    root = database_file_settings.storage_path
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}.sqlite3"
    temporary_path = root / f".{stored_name}.upload"
    final_path = root / stored_name
    size = 0
    header = b""

    try:
        with temporary_path.open("xb") as destination:
            while chunk := stream.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > database_file_settings.max_upload_bytes:
                    raise DomainValidationError("The SQLite file is too large")
                if len(header) < len(_SQLITE_HEADER):
                    header += chunk[: len(_SQLITE_HEADER) - len(header)]
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())

        if header != _SQLITE_HEADER:
            raise DomainValidationError("The uploaded file is not a SQLite database")

        os.replace(temporary_path, final_path)
        final_path.chmod(0o600)
        return StoredSQLiteFile(
            original_name=original_name,
            stored_name=stored_name,
            size_bytes=size,
        )
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


async def store_sqlite_upload(upload: UploadFile) -> StoredSQLiteFile:
    original_name = _clean_name(upload.filename)
    await upload.seek(0)
    return await asyncio.to_thread(_copy_upload, upload.file, original_name)
