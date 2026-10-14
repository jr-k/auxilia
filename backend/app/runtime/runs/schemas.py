from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.runtime.runs.models import RunDB
from app.runtime.runs.state import MultitaskStrategy, RunStatus


class RunCreate(BaseModel):
    """Client payload for `POST /threads/{thread_id}/runs`.

    `input` starts a new turn; `command` resumes a HITL interrupt. `config`
    mirrors the langgraph-sdk run config (carries `trigger` / overrides).
    """

    input: dict | None = None
    command: dict | None = None
    config: dict | None = None
    multitask_strategy: MultitaskStrategy = "reject"


class RunResponse(BaseModel):
    """API projection of a run — operational state only (no input/command)."""

    id: str
    workspace_id: UUID
    thread_id: str
    status: RunStatus
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: RunDB) -> "RunResponse":
        return cls(
            id=record.id,
            workspace_id=record.workspace_id,
            thread_id=record.thread_id,
            status=record.status,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class QueuedPromptCreate(BaseModel):
    content: str | list[dict[str, Any]] | None = None
    text: str | None = Field(default=None, min_length=1, max_length=100_000)


class QueuedPromptPatch(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)


class QueuedPromptOrder(BaseModel):
    ordered_ids: list[str]


class QueuedPromptAttachmentResponse(BaseModel):
    filename: str
    media_type: str


class QueuedPromptResponse(BaseModel):
    id: str
    text: str
    attachments: list[QueuedPromptAttachmentResponse]
    position: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: RunDB) -> "QueuedPromptResponse | None":
        messages = (record.input or {}).get("messages")
        if not isinstance(messages, list) or len(messages) != 1:
            return None
        message = messages[0]
        if not isinstance(message, dict) or message.get("type") != "human":
            return None
        content = message.get("content")
        if not isinstance(content, (str, list)) or record.queue_position is None:
            return None
        if isinstance(content, list) and not all(
            isinstance(block, dict) for block in content
        ):
            return None
        return cls(
            id=record.id,
            text=queued_prompt_text(content),
            attachments=queued_prompt_attachments(content),
            position=record.queue_position,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


def queued_prompt_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        block["text"]
        for block in content
        if block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def queued_prompt_attachments(
    content: str | list[dict[str, Any]],
) -> list[QueuedPromptAttachmentResponse]:
    if isinstance(content, str):
        return []
    attachments: list[QueuedPromptAttachmentResponse] = []
    for block in content:
        if block.get("type") == "image_url":
            image = block.get("image_url")
            url = (
                image
                if isinstance(image, str)
                else image.get("url", "")
                if isinstance(image, dict)
                else ""
            )
            media_type = "image/jpeg"
            if isinstance(url, str) and url.startswith("data:"):
                declared_type = url[5:].split(";", 1)[0].split(",", 1)[0]
                if declared_type:
                    media_type = declared_type
            extension = media_type.split("/", 1)[-1].split("+", 1)[0]
            extension = extension.removeprefix("x-").replace("jpeg", "jpg")
            attachments.append(
                QueuedPromptAttachmentResponse(
                    filename=f"Image.{extension or 'jpg'}",
                    media_type=media_type,
                )
            )
        elif block.get("type") == "file":
            attachments.append(
                QueuedPromptAttachmentResponse(
                    filename=block.get("filename")
                    if isinstance(block.get("filename"), str)
                    else "file",
                    media_type=block.get("mime_type")
                    if isinstance(block.get("mime_type"), str)
                    else "application/octet-stream",
                )
            )
    return attachments


def has_queued_prompt_content(content: str | list[dict[str, Any]]) -> bool:
    if isinstance(content, str):
        return bool(content.strip()) and len(content) <= 100_000
    if not content:
        return False
    text_length = sum(
        len(block["text"])
        for block in content
        if block.get("type") == "text" and isinstance(block.get("text"), str)
    )
    if text_length > 100_000:
        return False
    for block in content:
        if (
            block.get("type") == "text"
            and isinstance(block.get("text"), str)
            and block["text"].strip()
        ):
            return True
        if block.get("type") == "image_url":
            image = block.get("image_url")
            if isinstance(image, str) and image:
                return True
            if (
                isinstance(image, dict)
                and isinstance(image.get("url"), str)
                and image["url"]
            ):
                return True
        if block.get("type") == "file" and isinstance(block.get("base64"), str):
            return True
    return False


def queued_prompt_input(content: str | list[dict[str, Any]]) -> dict:
    return {"messages": [{"type": "human", "content": content}]}


def queued_prompt_input_with_text(record: RunDB, text: str) -> dict:
    messages = (record.input or {}).get("messages")
    message = messages[0] if isinstance(messages, list) and len(messages) == 1 else {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return queued_prompt_input(text)
    attachments = [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") != "text"
    ]
    return queued_prompt_input([{"type": "text", "text": text}, *attachments])
