"""Gmail MCP tools backed by the stable Gmail REST API."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

import httpx2
from fastapi import APIRouter
from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from fastmcp.server.dependencies import get_access_token
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from app.mcp.gmail.settings import (
    GMAIL_API_BASE,
    GMAIL_SCOPES,
    gmail_mcp_base_url,
    gmail_mcp_url,
)


def _auth() -> RemoteAuthProvider:
    verifier = GoogleTokenVerifier(required_scopes=GMAIL_SCOPES)
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl("https://accounts.google.com")],
        base_url=gmail_mcp_base_url(),
        scopes_supported=GMAIL_SCOPES,
        resource_name="Auxilia Gmail",
    )


gmail_mcp = FastMCP(
    "Auxilia Gmail",
    instructions=(
        "Read and organize the authenticated user's Gmail mailbox and create drafts. "
        "Messages are never sent by this server."
    ),
    auth=_auth(),
)

gmail_metadata_router = APIRouter()


@gmail_metadata_router.get("/.well-known/oauth-protected-resource/gmail/mcp")
async def gmail_protected_resource_metadata() -> dict[str, Any]:
    """RFC 9728 metadata at the root path clients derive from the MCP URL."""
    return {
        "resource": gmail_mcp_url(),
        "authorization_servers": ["https://accounts.google.com"],
        "scopes_supported": GMAIL_SCOPES,
        "resource_name": "Auxilia Gmail",
    }


def _bearer_token() -> str:
    access_token = get_access_token()
    if access_token is None:
        raise PermissionError("Gmail authorization is required")
    return access_token.token


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx2.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            f"{GMAIL_API_BASE}/{path.lstrip('/')}",
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {_bearer_token()}"},
        )
    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message")
        except (TypeError, ValueError):
            detail = None
        raise RuntimeError(
            f"Gmail API returned {response.status_code}"
            + (f": {detail}" if detail else "")
        )
    return response.json()


def _decode_base64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except ValueError:
        return ""


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["name"]).lower(): str(item.get("value", ""))
        for item in payload.get("headers", [])
        if item.get("name")
    }


def _body_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    mime_type = str(payload.get("mimeType", ""))
    body = payload.get("body") or {}
    data = body.get("data")
    if data and mime_type in {"text/plain", "text/html"}:
        parts.append(
            {
                "mime_type": mime_type,
                "content": _decode_base64url(str(data)),
            }
        )
    for child in payload.get("parts") or []:
        parts.extend(_body_parts(child))
    return parts


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload") or {}
    headers = _headers(payload)
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "label_ids": message.get("labelIds", []),
        "snippet": message.get("snippet"),
        "internal_date": message.get("internalDate"),
        "from": headers.get("from"),
        "to": headers.get("to"),
        "cc": headers.get("cc"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "message_id": headers.get("message-id"),
        "body_parts": _body_parts(payload),
    }


READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE_ONLY_DRAFT = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
MODIFIES_MAILBOX = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)


@gmail_mcp.tool(annotations=READ_ONLY)
async def gmail_search_messages(
    query: str = "",
    max_results: int = 20,
    page_token: str | None = None,
    include_spam_trash: bool = False,
) -> dict[str, Any]:
    """Search Gmail using the same query syntax as the Gmail search box."""
    params: dict[str, Any] = {
        "maxResults": min(max(max_results, 1), 100),
        "includeSpamTrash": include_spam_trash,
    }
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token
    return await _request("GET", "messages", params=params)


@gmail_mcp.tool(annotations=READ_ONLY)
async def gmail_get_message(message_id: str) -> dict[str, Any]:
    """Read one Gmail message, including decoded text and HTML body parts."""
    message = await _request("GET", f"messages/{message_id}", params={"format": "full"})
    return _normalize_message(message)


@gmail_mcp.tool(annotations=READ_ONLY)
async def gmail_search_threads(
    query: str = "",
    max_results: int = 20,
    page_token: str | None = None,
    include_spam_trash: bool = False,
) -> dict[str, Any]:
    """Search Gmail threads using Gmail query syntax."""
    params: dict[str, Any] = {
        "maxResults": min(max(max_results, 1), 100),
        "includeSpamTrash": include_spam_trash,
    }
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token
    return await _request("GET", "threads", params=params)


@gmail_mcp.tool(annotations=READ_ONLY)
async def gmail_get_thread(thread_id: str) -> dict[str, Any]:
    """Read every message in one Gmail thread."""
    thread = await _request("GET", f"threads/{thread_id}", params={"format": "full"})
    return {
        "id": thread.get("id"),
        "history_id": thread.get("historyId"),
        "messages": [
            _normalize_message(message) for message in thread.get("messages", [])
        ],
    }


@gmail_mcp.tool(annotations=READ_ONLY)
async def gmail_list_labels() -> dict[str, Any]:
    """List the system and user labels available in Gmail."""
    return await _request("GET", "labels")


@gmail_mcp.tool(annotations=WRITE_ONLY_DRAFT)
async def gmail_create_draft(
    to: list[str],
    subject: str,
    body_text: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_html: str | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    """Create a Gmail draft. This tool never sends the message."""
    if not to:
        raise ValueError("At least one recipient is required")

    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    draft_message: dict[str, Any] = {"raw": raw}
    if thread_id:
        draft_message["threadId"] = thread_id
    return await _request("POST", "drafts", json={"message": draft_message})


@gmail_mcp.tool(annotations=MODIFIES_MAILBOX)
async def gmail_modify_message_labels(
    message_id: str,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Add or remove labels on a Gmail message."""
    if not add_label_ids and not remove_label_ids:
        raise ValueError("At least one label must be added or removed")
    return await _request(
        "POST",
        f"messages/{message_id}/modify",
        json={
            "addLabelIds": add_label_ids or [],
            "removeLabelIds": remove_label_ids or [],
        },
    )


gmail_mcp_app = gmail_mcp.http_app(
    path="/mcp",
    stateless_http=True,
    json_response=True,
)
