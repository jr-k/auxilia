from typing import Final, Literal, NotRequired, TypedDict
from uuid import UUID


NOTIFICATION_CHANNEL: Final = "notification"


class NotificationDelivery(TypedDict):
    channel: Literal["notification"]
    workspace_id: str
    user_id: str
    title: str
    channel_ids: NotRequired[list[str]]


def build_notification_delivery(
    *,
    workspace_id: UUID,
    user_id: UUID,
    title: str,
    channel_ids: list[str],
) -> NotificationDelivery:
    delivery: NotificationDelivery = {
        "channel": NOTIFICATION_CHANNEL,
        "workspace_id": str(workspace_id),
        "user_id": str(user_id),
        "title": title,
    }
    if channel_ids:
        delivery["channel_ids"] = channel_ids
    return delivery
