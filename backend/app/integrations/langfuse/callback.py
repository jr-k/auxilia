"""The Langfuse client and LangChain callback handler, built lazily.

Lazily on purpose. These used to be module-level constants, evaluated at import
time — and `app/runtime/agent.py` imports this module, so *any* failure constructing the
client (a malformed base URL, a Langfuse SDK that validates eagerly) took down
every import of the agent runtime, at startup, for an optional integration
(design review §5.10). Now a bad configuration can at worst break tracing.

The result is memoized rather than rebuilt per call: `CallbackHandler` is passed
into every agent run, and a fresh client per run would mean a fresh exporter
thread per run.
"""

import logging

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.observability.service import ObservabilityRuntimeConfig


logger = logging.getLogger(__name__)

_clients: dict[str, tuple[Langfuse, CallbackHandler]] = {}


def _build_langfuse(
    config: ObservabilityRuntimeConfig,
) -> tuple[Langfuse, CallbackHandler]:
    client = Langfuse(
        public_key=config.public_key,
        secret_key=config.secret_key,
        host=config.base_url,
        timeout=config.timeout_seconds,
    )
    return client, CallbackHandler(public_key=config.public_key)


def get_langfuse_callback_handler(
    config: ObservabilityRuntimeConfig,
) -> CallbackHandler | None:
    """Return a handler for the current DB revision, or None when invalid."""
    cached = _clients.get(config.fingerprint)
    if cached is not None:
        return cached[1]
    try:
        client, handler = _build_langfuse(config)
        _clients[config.fingerprint] = (client, handler)
        return handler
    except Exception:
        logger.exception("Langfuse is misconfigured; continuing without tracing")
        return None


def flush_langfuse() -> None:
    """Flush buffered traces. Called from the FastAPI lifespan on shutdown.

    Langfuse batches spans and ships them on a background timer. On Cloud Run
    the instance is frozen and killed the moment the last request drains, so
    without this the tail of every scale-to-zero cycle is simply lost — and the
    tail is disproportionately where the interesting runs are.

    Never built here: flushing must not be the thing that constructs a client
    the process never needed.
    """
    for client, _handler in _clients.values():
        try:
            client.flush()
        except Exception:  # noqa: BLE001 — a failed flush must not fail shutdown
            logger.warning("Flushing Langfuse traces on shutdown failed", exc_info=True)
