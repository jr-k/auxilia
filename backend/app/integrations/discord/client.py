from typing import Any

import httpx

from app.exceptions import DomainValidationError


DISCORD_API = "https://discord.com/api/v10"


class DiscordClient:
    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bot {token}"}

    async def request(
        self, method: str, path: str, *, json: dict | list | None = None
    ) -> Any:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                f"{DISCORD_API}{path}",
                headers=self.headers,
                json=json,
            )
        if response.status_code == 204:
            return None
        try:
            body = response.json()
        except ValueError as exc:
            raise DomainValidationError("Discord returned an invalid response") from exc
        if not response.is_success:
            detail = body.get("message") if isinstance(body, dict) else None
            raise DomainValidationError(str(detail or "Discord request failed"))
        return body

    async def get_me(self) -> dict:
        result = await self.request("GET", "/users/@me")
        return result if isinstance(result, dict) else {}

    async def register_commands(self, application_id: str) -> None:
        command = {
            "name": "auxilia",
            "description": "Talk to an auxilia agent",
            "options": [
                {
                    "type": 1,
                    "name": "link",
                    "description": "Link your auxilia account",
                    "options": [
                        {
                            "type": 3,
                            "name": "code",
                            "description": "One-time code from auxilia",
                            "required": True,
                        }
                    ],
                },
                {
                    "type": 1,
                    "name": "new",
                    "description": "Start a conversation with an agent",
                    "options": [
                        {
                            "type": 3,
                            "name": "agent",
                            "description": "Agent",
                            "required": True,
                            "autocomplete": True,
                        }
                    ],
                },
                {
                    "type": 1,
                    "name": "ask",
                    "description": "Send a message to the active agent",
                    "options": [
                        {
                            "type": 3,
                            "name": "prompt",
                            "description": "Your message",
                            "required": True,
                        }
                    ],
                },
            ],
        }
        await self.request(
            "PUT",
            f"/applications/{application_id}/commands",
            json=[command],
        )

    async def edit_original(
        self, application_id: str, interaction_token: str, content: str
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.patch(
                f"{DISCORD_API}/webhooks/{application_id}/{interaction_token}/messages/@original",
                json={
                    "content": content[:2000],
                    "allowed_mentions": {"parse": []},
                },
            )
        if not response.is_success:
            raise DomainValidationError("Could not update the Discord response")

    async def followup(
        self,
        application_id: str,
        interaction_token: str,
        content: str,
        *,
        components: list[dict] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "content": content[:2000],
            "allowed_mentions": {"parse": []},
        }
        if components is not None:
            payload["components"] = components
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{DISCORD_API}/webhooks/{application_id}/{interaction_token}",
                json=payload,
            )
        if not response.is_success:
            raise DomainValidationError("Could not send the Discord response")

    async def send_channel_message(
        self,
        channel_id: str,
        content: str,
        *,
        components: list[dict] | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "content": content[:2000],
            "allowed_mentions": {"parse": []},
        }
        if components is not None:
            payload["components"] = components
        result = await self.request(
            "POST", f"/channels/{channel_id}/messages", json=payload
        )
        return result if isinstance(result, dict) else {}

    async def edit_channel_message(
        self, channel_id: str, message_id: str, content: str
    ) -> None:
        await self.request(
            "PATCH",
            f"/channels/{channel_id}/messages/{message_id}",
            json={
                "content": content[:2000],
                "allowed_mentions": {"parse": []},
            },
        )
