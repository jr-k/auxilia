import base64
import mimetypes
from dataclasses import dataclass
from typing import Any

from app.integrations.telegram.client import TelegramAPIError, TelegramClient


MAX_TELEGRAM_FILE_BYTES = 20 * 1024 * 1024
_IMAGE_MIME_TYPES = frozenset({"image/gif", "image/jpeg", "image/png", "image/webp"})
_TEXT_APPLICATION_MIME_TYPES = frozenset(
    {
        "application/javascript",
        "application/json",
        "application/toml",
        "application/xml",
        "application/yaml",
    }
)


@dataclass(frozen=True)
class TelegramAttachments:
    content_blocks: list[dict[str, Any]]
    rejected_names: list[str]


def _block(
    data: bytes, filename: str, declared_mime: str | None
) -> dict[str, Any] | None:
    mime_type = (declared_mime or "").split(";", 1)[0].lower()
    if not mime_type or mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(filename)[0] or ""
    if data.startswith(b"%PDF-"):
        mime_type = "application/pdf"
    elif data.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mime_type = "image/gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime_type = "image/webp"
    is_text = (
        not mime_type
        or mime_type.startswith("text/")
        or mime_type in _TEXT_APPLICATION_MIME_TYPES
    )
    if is_text:
        if b"\x00" in data:
            return None
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
        return {"type": "text", "text": f'Attached file "{filename}":\n\n{text}'}
    encoded = base64.b64encode(data).decode("ascii")
    if mime_type in _IMAGE_MIME_TYPES:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}",
                "detail": "auto",
            },
        }
    if mime_type == "application/pdf" and data.startswith(b"%PDF-"):
        return {
            "type": "file",
            "mime_type": mime_type,
            "base64": encoded,
            "filename": filename,
        }
    return None


async def load_telegram_attachments(
    client: TelegramClient, message: dict[str, Any]
) -> TelegramAttachments:
    candidates: list[tuple[str, str, str | None, int | None]] = []
    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        photo = photos[-1]
        if isinstance(photo, dict) and isinstance(photo.get("file_id"), str):
            candidates.append(
                (
                    photo["file_id"],
                    "telegram-photo.jpg",
                    "image/jpeg",
                    photo.get("file_size"),
                )
            )
    document = message.get("document")
    if isinstance(document, dict) and isinstance(document.get("file_id"), str):
        candidates.append(
            (
                document["file_id"],
                str(document.get("file_name") or "telegram-document"),
                str(document.get("mime_type") or "") or None,
                document.get("file_size"),
            )
        )
    blocks: list[dict[str, Any]] = []
    rejected: list[str] = []
    for file_id, filename, mime_type, size in candidates:
        if isinstance(size, int) and size > MAX_TELEGRAM_FILE_BYTES:
            rejected.append(filename)
            continue
        try:
            data, remote_name = await client.download_file(file_id)
        except TelegramAPIError:
            rejected.append(filename)
            continue
        if len(data) > MAX_TELEGRAM_FILE_BYTES:
            rejected.append(filename)
            continue
        block = _block(data, filename or remote_name or "telegram-file", mime_type)
        if block is None:
            rejected.append(filename)
        else:
            blocks.append(block)
    return TelegramAttachments(blocks, rejected)
