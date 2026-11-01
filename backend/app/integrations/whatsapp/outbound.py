from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainValidationError
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.db_models import WhatsAppOutboundMessageDB
from app.integrations.whatsapp.repository import WhatsAppSessionRepository
from app.integrations.whatsapp.service import (
    WhatsAppConnectionService,
    WhatsAppRuntimeConfig,
)


SESSION_WINDOW = timedelta(hours=24)


class WhatsAppOutboundGateway:
    """The only free-form WhatsApp send path.

    Every caller rechecks the workspace switch, connection state and service
    window immediately before sending.
    """

    def __init__(
        self,
        db: AsyncSession,
        config: WhatsAppRuntimeConfig,
        *,
        recipient_id: str,
        recipient_type: str = "individual",
    ):
        self.db = db
        self.config = config
        self.recipient_id = recipient_id
        self.recipient_type = recipient_type
        self.client = WhatsAppClient(config.access_token, config.phone_number_id)

    async def ensure_available(self) -> None:
        fresh = await WhatsAppConnectionService(self.db).get_runtime(self.config.id)
        if fresh is None or not fresh.workspace_enabled or not fresh.enabled:
            raise DomainValidationError("The WhatsApp connection is disabled")
        self.config = fresh
        self.client = WhatsAppClient(fresh.access_token, fresh.phone_number_id)
        session = await WhatsAppSessionRepository(self.db).get_recipient(
            fresh.id, self.recipient_type, self.recipient_id
        )
        if (
            session is None
            or session.last_user_message_at + SESSION_WINDOW <= datetime.now(UTC)
        ):
            raise DomainValidationError(
                "WhatsApp's 24-hour customer service window is closed. "
                "Ask the user to send a new WhatsApp message first."
            )

    async def send_text(
        self, text: str, *, reply_to_message_id: str | None = None
    ) -> str:
        await self.ensure_available()
        message_id = await self.client.send_message(
            self.recipient_id,
            text,
            recipient_type=self.recipient_type,
            reply_to_message_id=reply_to_message_id,
        )
        self._track(message_id)
        return message_id

    async def send_approval(self, body: str, token: str) -> str:
        await self.ensure_available()
        if self.recipient_type != "individual":
            raise DomainValidationError(
                "Interactive WhatsApp approvals are unavailable in groups"
            )
        message_id = await self.client.send_approval(self.recipient_id, body, token)
        self._track(message_id)
        return message_id

    async def send_media(
        self,
        *,
        filename: str,
        content: bytes,
        mime_type: str,
        caption: str | None = None,
    ) -> str:
        await self.ensure_available()
        media_id = await self.client.upload_media(filename, content, mime_type)
        media_type = (
            "image"
            if mime_type.startswith("image/")
            else "video"
            if mime_type.startswith("video/")
            else "audio"
            if mime_type.startswith("audio/")
            else "document"
        )
        message_id = await self.client.send_media(
            self.recipient_id,
            media_type=media_type,
            media_id=media_id,
            caption=caption,
            filename=filename,
            recipient_type=self.recipient_type,
        )
        self._track(message_id)
        return message_id

    def _track(self, message_id: str) -> None:
        self.db.add(
            WhatsAppOutboundMessageDB(
                whatsapp_connection_id=self.config.id,
                message_id=message_id,
                recipient_id=self.recipient_id,
                status="accepted",
                status_at=datetime.now(UTC),
            )
        )
