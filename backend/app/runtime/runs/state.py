"""What a run *is*: its lifecycle and the legal transitions.

A run is the execution envelope around one agent turn (see `SPEC.md`). Its
record is the `RunDB` row in Postgres (`models.py`); durable conversation
state stays in the LangGraph checkpoint.
"""

from enum import Enum
from typing import Literal


#: What `create` does when the thread already has an active run: `reject`
#: raises, `enqueue` waits for the per-thread mutex. One alias shared by the
#: column, the API schema, and the service so the type checker sees a single
#: vocabulary instead of three `str`s that happen to agree.
MultitaskStrategy = Literal["reject", "enqueue"]


def delivery_force_enable_all_capabilities(
    delivery: dict | None,
) -> bool | None:
    """Return a Slack side-channel capability override, if one was recorded."""
    if not delivery or delivery.get("channel") != "slack":
        return None
    value = delivery.get("force_enable_all_capabilities")
    return value if isinstance(value, bool) else None


class RunStatus(str, Enum):
    """Run lifecycle. Names match the LangGraph Server v1 wire shape; `cancelled`
    is auxilia's explicit Stop."""

    pending = "pending"
    running = "running"
    interrupted = "interrupted"
    success = "success"
    error = "error"
    timeout = "timeout"
    cancelled = "cancelled"


# Fallback error for an OAuth requirement that unexpectedly escapes the
# per-server runtime filtering. Named errors use the same prefix so delivery
# consumers can still show a reconnect affordance.
MCP_REAUTH_ERROR = (
    "MCP authorization required: an MCP server used by this agent (or one of "
    "its subagents) is no longer connected for this user. Reconnect it from "
    "the agent's chat page, then run again."
)
_MCP_REAUTH_NAMED_PREFIX = "MCP authorization required: MCP server "


def mcp_reauth_error(server_name: str | None) -> str:
    """Build the durable run error, naming the server whenever it is known."""
    if not server_name or not (label := " ".join(server_name.split())):
        return MCP_REAUTH_ERROR
    return (
        f"{_MCP_REAUTH_NAMED_PREFIX}'{label}' is no longer connected for this "
        "user. Reconnect it from the agent's chat page, then run again."
    )


def is_mcp_reauth_error(error: str | None) -> bool:
    """Recognize both the legacy generic error and its named variant."""
    return error == MCP_REAUTH_ERROR or bool(
        error and error.startswith(_MCP_REAUTH_NAMED_PREFIX)
    )


# Terminal states stamp `threads.last_run_status` and TTL the run's Redis
# ephemera. `interrupted` is terminal *for this run* — resuming a HITL
# interrupt creates a new run.
TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.interrupted,
        RunStatus.success,
        RunStatus.error,
        RunStatus.timeout,
        RunStatus.cancelled,
    }
)

# Exhaustive transition table. Anything not listed is illegal and raises.
# The repository derives its SQL guards from this table (claim: WHERE
# status='pending'; finalize: WHERE status IN legal_source_statuses(target)),
# so it is the single source of truth for legality, in Python and in SQL.
_ALLOWED: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.pending: frozenset(
        {RunStatus.running, RunStatus.cancelled, RunStatus.error}
    ),
    RunStatus.running: frozenset(
        {
            RunStatus.interrupted,
            RunStatus.success,
            RunStatus.error,
            RunStatus.timeout,
            RunStatus.cancelled,
        }
    ),
    RunStatus.interrupted: frozenset(),
    RunStatus.success: frozenset(),
    RunStatus.error: frozenset(),
    RunStatus.timeout: frozenset(),
    RunStatus.cancelled: frozenset(),
}


class InvalidRunTransitionError(Exception):
    """Raised on an illegal status transition — always a programming bug."""

    def __init__(self, current: RunStatus, target: RunStatus):
        super().__init__(f"Illegal run transition: {current.value} → {target.value}")
        self.current = current
        self.target = target


def transition(current: RunStatus, target: RunStatus) -> RunStatus:
    """Return `target` if `current → target` is legal, else raise."""
    if target not in _ALLOWED[current]:
        raise InvalidRunTransitionError(current, target)
    return target


def legal_source_statuses(target: RunStatus) -> frozenset[RunStatus]:
    """The statuses from which `target` is a legal transition — the SQL
    finalize guard (e.g. a `pending` run can be reaped to `error` but can
    never be reported `success`)."""
    return frozenset(
        source for source, targets in _ALLOWED.items() if target in targets
    )


def is_terminal(status: RunStatus) -> bool:
    return status in TERMINAL_STATUSES
