from typing import Any

import httpx

from app.exceptions import DomainValidationError


class TelegramAPIError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str):
        self._token = token
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._file_base_url = f"https://api.telegram.org/file/bot{token}"

    async def request(self, method: str, **payload: Any) -> Any:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                response = await client.post(f"{self._base_url}/{method}", json=payload)
        except httpx.HTTPError:
            raise TelegramAPIError("Telegram is temporarily unavailable") from None
        try:
            body = response.json()
        except ValueError:
            raise TelegramAPIError("Telegram returned an invalid response") from None
        if not response.is_success or not isinstance(body, dict) or not body.get("ok"):
            description = (
                str(body.get("description") or "Telegram request failed")
                if isinstance(body, dict)
                else "Telegram request failed"
            )
            if method == "editMessageText" and "message is not modified" in description:
                return True
            raise TelegramAPIError(description)
        return body.get("result")

    async def get_me(self) -> dict[str, Any]:
        result = await self.request("getMe")
        return result if isinstance(result, dict) else {}

    async def get_webhook_info(self) -> dict[str, Any]:
        result = await self.request("getWebhookInfo")
        return result if isinstance(result, dict) else {}

    async def set_webhook(self, url: str, secret: str) -> None:
        await self.request(
            "setWebhook",
            url=url,
            secret_token=secret,
            allowed_updates=["message", "edited_message", "callback_query"],
            max_connections=20,
        )

    async def delete_webhook(self) -> None:
        await self.request("deleteWebhook")

    async def send_chat_action(
        self, chat_id: str, action: str, *, message_thread_id: str = ""
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "action": action}
        if message_thread_id:
            payload["message_thread_id"] = int(message_thread_id)
        await self.request("sendChatAction", **payload)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        message_thread_id: str = "",
        reply_markup: dict[str, Any] | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
        if message_thread_id:
            payload["message_thread_id"] = int(message_thread_id)
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}
        result = await self.request("sendMessage", **payload)
        return result if isinstance(result, dict) else {}

    async def edit_message(
        self,
        chat_id: str,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text[:4096],
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await self.request("editMessageText", **payload)

    async def answer_callback(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        await self.request(
            "answerCallbackQuery",
            callback_query_id=callback_query_id,
            **({"text": text[:200]} if text else {}),
        )

    async def edit_reply_markup(
        self,
        chat_id: str,
        message_id: int,
        reply_markup: dict[str, Any],
    ) -> None:
        await self.request(
            "editMessageReplyMarkup",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def get_file(self, file_id: str) -> dict[str, Any]:
        result = await self.request("getFile", file_id=file_id)
        return result if isinstance(result, dict) else {}

    async def download_file(self, file_id: str) -> tuple[bytes, str | None]:
        metadata = await self.get_file(file_id)
        path = metadata.get("file_path")
        if not isinstance(path, str) or not path:
            raise DomainValidationError("Telegram did not return a file path")
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
                response = await client.get(f"{self._file_base_url}/{path}")
                response.raise_for_status()
        except httpx.HTTPError:
            raise TelegramAPIError("Could not download the Telegram file") from None
        return response.content, path.rsplit("/", 1)[-1]

    async def send_document(
        self,
        chat_id: str,
        filename: str,
        content: bytes,
        *,
        message_thread_id: str = "",
        caption: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, str] = {"chat_id": chat_id}
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        if caption:
            data["caption"] = caption[:1024]
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                response = await client.post(
                    f"{self._base_url}/sendDocument",
                    data=data,
                    files={"document": (filename, content)},
                )
        except httpx.HTTPError:
            raise TelegramAPIError("Could not upload the Telegram file") from None
        try:
            body = response.json()
        except ValueError:
            raise TelegramAPIError("Telegram returned an invalid response") from None
        if not response.is_success or not isinstance(body, dict) or not body.get("ok"):
            raise TelegramAPIError(
                str(body.get("description") or "Telegram upload failed")
                if isinstance(body, dict)
                else "Telegram upload failed"
            )
        result = body.get("result")
        return result if isinstance(result, dict) else {}

    async def send_photo(
        self,
        chat_id: str,
        filename: str,
        content: bytes,
        *,
        message_thread_id: str = "",
        caption: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, str] = {"chat_id": chat_id}
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        if caption:
            data["caption"] = caption[:1024]
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                response = await client.post(
                    f"{self._base_url}/sendPhoto",
                    data=data,
                    files={"photo": (filename, content)},
                )
        except httpx.HTTPError:
            raise TelegramAPIError("Could not upload the Telegram image") from None
        try:
            body = response.json()
        except ValueError:
            raise TelegramAPIError("Telegram returned an invalid response") from None
        if not response.is_success or not isinstance(body, dict) or not body.get("ok"):
            raise TelegramAPIError(
                str(body.get("description") or "Telegram upload failed")
                if isinstance(body, dict)
                else "Telegram upload failed"
            )
        result = body.get("result")
        return result if isinstance(result, dict) else {}
