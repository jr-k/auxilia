from typing import Any

import httpx

from app.exceptions import DomainValidationError


class TelegramClient:
    def __init__(self, token: str):
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def request(self, method: str, **payload: Any) -> Any:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/{method}", json=payload)
        try:
            body = response.json()
        except ValueError as exc:
            raise DomainValidationError(
                "Telegram returned an invalid response"
            ) from exc
        if not response.is_success or not body.get("ok"):
            description = str(body.get("description") or "Telegram request failed")
            if method == "editMessageText" and "message is not modified" in description:
                return True
            raise DomainValidationError(str(description))
        return body.get("result")

    async def get_me(self) -> dict:
        result = await self.request("getMe")
        return result if isinstance(result, dict) else {}

    async def set_webhook(self, url: str, secret: str) -> None:
        await self.request(
            "setWebhook",
            url=url,
            secret_token=secret,
            allowed_updates=["message", "callback_query"],
        )

    async def delete_webhook(self) -> None:
        await self.request("deleteWebhook")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        message_thread_id: str = "",
        reply_markup: dict | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
        if message_thread_id:
            payload["message_thread_id"] = int(message_thread_id)
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = await self.request("sendMessage", **payload)
        return result if isinstance(result, dict) else {}

    async def edit_message(self, chat_id: str, message_id: int, text: str) -> None:
        await self.request(
            "editMessageText",
            chat_id=chat_id,
            message_id=message_id,
            text=text[:4096],
        )

    async def answer_callback(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        await self.request(
            "answerCallbackQuery",
            callback_query_id=callback_query_id,
            **({"text": text} if text else {}),
        )
