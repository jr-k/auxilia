"""Provider-native, server-side web search tool definitions."""

from typing import Any


NATIVE_WEB_SEARCH_PROVIDERS = frozenset({"openai", "anthropic", "google"})


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
