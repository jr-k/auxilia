import base64
import mimetypes
from dataclasses import dataclass
from typing import Any

from app.integrations.whatsapp.client import WhatsAppAPIError, WhatsAppClient


_MAX_FILE_BYTES = 100 * 1024 * 1024
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
class WhatsAppAttachments:
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


async def load_whatsapp_attachments(
    client: WhatsAppClient, message: dict[str, Any]
) -> WhatsAppAttachments:
    message_type = str(message.get("type") or "")
    media = message.get(message_type)
    if message_type not in {"image", "document", "audio", "video"} or not isinstance(
        media, dict
    ):
        return WhatsAppAttachments([], [])
    media_id = media.get("id")
    filename = str(
        media.get("filename")
        or {
            "image": "whatsapp-image",
            "document": "whatsapp-document",
            "audio": "whatsapp-audio",
            "video": "whatsapp-video",
        }.get(message_type, "whatsapp-file")
    )
    if not isinstance(media_id, str) or not media_id:
        return WhatsAppAttachments([], [filename])
    try:
        data, remote_name, mime_type = await client.download_media(media_id)
    except WhatsAppAPIError:
        return WhatsAppAttachments([], [filename])
    if len(data) > _MAX_FILE_BYTES:
        return WhatsAppAttachments([], [filename])
    block = _block(
        data,
        filename or remote_name or "whatsapp-file",
        str(media.get("mime_type") or mime_type),
    )
    return (
        WhatsAppAttachments([block], [])
        if block is not None
        else WhatsAppAttachments([], [filename])
    )
