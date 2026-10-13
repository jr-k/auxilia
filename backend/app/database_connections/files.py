import asyncio
import os
import re
import time
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
_STORED_FILE_PATTERN = re.compile(r"^[0-9a-f]{32}\.sqlite3$")
_TEMP_FILE_PATTERN = re.compile(r"^\.[0-9a-f]{32}\.sqlite3\.upload$")
_SIDECAR_FILE_PATTERN = re.compile(
    r"^(?P<stored_name>[0-9a-f]{32}\.sqlite3)-(?:journal|shm|wal)$"
)
_SHARED_DIRECTORY_MODE = 0o755
_SHARED_FILE_MODE = 0o644


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
    root.chmod(_SHARED_DIRECTORY_MODE)
    stored_name = f"{uuid4().hex}.sqlite3"
    temporary_path = root / f".{stored_name}.upload"
    final_path = root / stored_name
    size = 0
    header = b""

    try:
        with temporary_path.open("xb") as destination:
            temporary_path.chmod(0o600)
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
        final_path.chmod(_SHARED_FILE_MODE)
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


def _delete_stored_file(stored_name: str) -> None:
    if not _STORED_FILE_PATTERN.fullmatch(stored_name):
        raise ValueError("Invalid stored database filename")
    root = database_file_settings.storage_path
    (root / stored_name).unlink(missing_ok=True)
    for suffix in ("-journal", "-shm", "-wal"):
        (root / f"{stored_name}{suffix}").unlink(missing_ok=True)


async def delete_stored_file(stored_name: str) -> None:
    await asyncio.to_thread(_delete_stored_file, stored_name)


def runtime_path_for_stored_file(stored_name: str) -> Path:
    if not _STORED_FILE_PATTERN.fullmatch(stored_name):
        raise ValueError("Invalid stored database filename")
    return database_file_settings.runtime_path / stored_name


def _ensure_stored_file_permissions(known_names: set[str]) -> int:
    root = database_file_settings.storage_path
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(_SHARED_DIRECTORY_MODE)
    updated = 0
    for stored_name in known_names:
        if not _STORED_FILE_PATTERN.fullmatch(stored_name):
            continue
        path = root / stored_name
        try:
            if path.stat().st_mode & 0o777 == _SHARED_FILE_MODE:
                continue
            path.chmod(_SHARED_FILE_MODE)
            updated += 1
        except FileNotFoundError:
            continue
    return updated


async def ensure_stored_file_permissions(known_names: set[str]) -> int:
    return await asyncio.to_thread(_ensure_stored_file_permissions, known_names)


def _delete_untracked_files(
    known_names: set[str],
    *,
    older_than_seconds: int,
) -> int:
    root = database_file_settings.storage_path
    if not root.exists():
        return 0
    cutoff = time.time() - older_than_seconds
    deleted = 0
    for path in root.iterdir():
        sidecar_match = _SIDECAR_FILE_PATTERN.fullmatch(path.name)
        if (
            path.name in known_names
            or (
                sidecar_match is not None
                and sidecar_match.group("stored_name") in known_names
            )
            or not (
                _STORED_FILE_PATTERN.fullmatch(path.name)
                or _TEMP_FILE_PATTERN.fullmatch(path.name)
                or sidecar_match
            )
        ):
            continue
        try:
            if path.stat().st_mtime > cutoff:
                continue
            path.unlink(missing_ok=True)
            deleted += 1
        except FileNotFoundError:
            continue
    return deleted


async def delete_untracked_files(
    known_names: set[str],
    *,
    older_than_seconds: int = 300,
) -> int:
    return await asyncio.to_thread(
        _delete_untracked_files,
        known_names,
        older_than_seconds=older_than_seconds,
    )
