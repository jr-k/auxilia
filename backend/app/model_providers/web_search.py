"""Provider-native, server-side web search tool definitions."""

from typing import Any


NATIVE_WEB_SEARCH_PROVIDERS = frozenset({"openai", "anthropic", "google"})


def compatible_reasoning_effort(
    provider: str,
    reasoning_effort: str | None,
    *,
    web_search_enabled: bool,
) -> str | None:
    """Return an effort accepted when the provider's web-search tool is bound."""
    if (
        provider == "openai"
        and web_search_enabled
        and reasoning_effort == "minimal"
    ):
        return "low"
    return reasoning_effort


def native_web_search_tool(provider: str) -> dict[str, Any] | None:
    """Return the provider tool shape LangChain passes through unchanged."""
    match provider:
        case "openai":
            return {"type": "web_search"}
        case "anthropic":
            return {"type": "web_search_20260209", "name": "web_search"}
        case "google":
            return {"google_search": {}}
        case _:
            return None
