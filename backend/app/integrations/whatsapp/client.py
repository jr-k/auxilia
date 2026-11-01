from typing import Any

import httpx

from app.integrations.whatsapp.settings import whatsapp_settings


class WhatsAppAPIError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.code = code


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str):
        self._access_token = access_token
        self.phone_number_id = phone_number_id
        self._base_url = (
            f"https://graph.facebook.com/{whatsapp_settings.graph_api_version}"
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=request_timeout or whatsapp_settings.request_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}/{path.lstrip('/')}",
                    headers=self._headers,
                    json=json,
                    data=data,
                    files=files,
                )
        except httpx.HTTPError:
            raise WhatsAppAPIError("WhatsApp is temporarily unavailable") from None
        try:
            body = response.json()
        except ValueError:
            raise WhatsAppAPIError("WhatsApp returned an invalid response") from None
        if not response.is_success or not isinstance(body, dict):
            error = body.get("error") if isinstance(body, dict) else None
            message = (
                str(error.get("message") or "WhatsApp request failed")
                if isinstance(error, dict)
                else "WhatsApp request failed"
            )
            code = error.get("code") if isinstance(error, dict) else None
            raise WhatsAppAPIError(
                message,
                code=code if isinstance(code, int) else None,
            )
        return body

    async def get_phone_number(self) -> dict[str, Any]:
        return await self.request(
            "GET",
            f"{self.phone_number_id}?fields=id,display_phone_number,verified_name",
        )

    async def list_business_phone_numbers(
        self, business_account_id: str
    ) -> list[dict[str, Any]]:
        body = await self.request(
            "GET",
            f"{business_account_id}/phone_numbers"
            "?fields=id,display_phone_number,verified_name",
        )
        data = body.get("data")
        return (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )

    async def send_message(
        self,
        recipient_id: str,
        text: str,
        *,
        recipient_type: str = "individual",
        reply_to_message_id: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": recipient_type,
            "to": recipient_id,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}
        return self._message_id(
            await self.request("POST", f"{self.phone_number_id}/messages", json=payload)
        )

    async def send_approval(self, recipient_id: str, body: str, token: str) -> str:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"th:{token}:approve", "title": "Approve"},
                        },
                        {
                            "type": "reply",
                            "reply": {"id": f"th:{token}:reject", "title": "Reject"},
                        },
                    ]
                },
            },
        }
        return self._message_id(
            await self.request("POST", f"{self.phone_number_id}/messages", json=payload)
        )

    async def mark_read(
        self, message_id: str, *, show_typing_indicator: bool = False
    ) -> None:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if show_typing_indicator:
            payload["typing_indicator"] = {"type": "text"}
        await self.request("POST", f"{self.phone_number_id}/messages", json=payload)

    async def upload_media(self, filename: str, content: bytes, mime_type: str) -> str:
        body = await self.request(
            "POST",
            f"{self.phone_number_id}/media",
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, content, mime_type)},
            request_timeout=whatsapp_settings.media_timeout_seconds,
        )
        media_id = body.get("id")
        if not isinstance(media_id, str) or not media_id:
            raise WhatsAppAPIError("WhatsApp did not return a media ID")
        return media_id

    async def send_media(
        self,
        recipient_id: str,
        *,
        media_type: str,
        media_id: str,
        caption: str | None = None,
        filename: str | None = None,
        recipient_type: str = "individual",
    ) -> str:
        media: dict[str, Any] = {"id": media_id}
        if caption and media_type in {"image", "video", "document"}:
            media["caption"] = caption[:1024]
        if filename and media_type == "document":
            media["filename"] = filename
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": recipient_type,
            "to": recipient_id,
            "type": media_type,
            media_type: media,
        }
        return self._message_id(
            await self.request("POST", f"{self.phone_number_id}/messages", json=payload)
        )

    async def download_media(self, media_id: str) -> tuple[bytes, str | None, str]:
        metadata = await self.request(
            "GET", f"{media_id}?phone_number_id={self.phone_number_id}"
        )
        url = metadata.get("url")
        if not isinstance(url, str) or not url:
            raise WhatsAppAPIError("WhatsApp did not return a media URL")
        try:
            async with httpx.AsyncClient(
                timeout=whatsapp_settings.media_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(url, headers=self._headers)
                response.raise_for_status()
        except httpx.HTTPError:
            raise WhatsAppAPIError("Could not download WhatsApp media") from None
        mime_type = str(
            metadata.get("mime_type")
            or response.headers.get("content-type")
            or "application/octet-stream"
        )
        return response.content, None, mime_type

    @staticmethod
    def _message_id(body: dict[str, Any]) -> str:
        messages = body.get("messages")
        first = messages[0] if isinstance(messages, list) and messages else None
        message_id = first.get("id") if isinstance(first, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise WhatsAppAPIError("WhatsApp did not return a message ID")
        return message_id
