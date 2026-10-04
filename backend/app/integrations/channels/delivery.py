from app.integrations.discord.consumer import build_discord_run_consumer
from app.integrations.slack.consumer import build_slack_run_consumer
from app.integrations.telegram.consumer import build_telegram_run_consumer
from app.runtime.runs.delivery import DeliveryConsumer
from app.runtime.runs.models import RunDB


def build_channel_run_consumer(record: RunDB) -> DeliveryConsumer | None:
    """Dispatch a push-delivery record to its provider-owned consumer."""
    for factory in (
        build_slack_run_consumer,
        build_telegram_run_consumer,
        build_discord_run_consumer,
    ):
        consumer = factory(record)
        if consumer is not None:
            return consumer
    return None
