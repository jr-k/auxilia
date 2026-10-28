"""Ollama connection validation and local-model discovery."""

import asyncio
import ipaddress
import json
import re
import socket
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel

from app.exceptions import DomainValidationError


_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_MODELS = 200


class DiscoveredOllamaModel(BaseModel):
    model_id: str
    runtime_model_id: str
    display_name: str
    chef: str
    chef_slug: str
    multimodal: bool
    supports_structured_output: bool
    supports_tools: bool


def _normalized_url(raw_url: str) -> tuple[str, SplitResult]:
    value = raw_url.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DomainValidationError("Ollama URL is invalid") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DomainValidationError("Ollama URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise DomainValidationError("Ollama URL must not contain credentials")
    if parsed.fragment or parsed.query:
        raise DomainValidationError("Ollama URL must not contain a query or fragment")
    hostname = parsed.hostname
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    normalized = urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))
    return normalized, parsed


async def validate_ollama_url(raw_url: str) -> str:
    """Normalize an admin-managed endpoint and reject dangerous destinations.

    Private and loopback addresses are intentionally accepted: local-network
    access is the purpose of this provider. Link-local and metadata ranges are
    not useful Ollama targets and are blocked.
    """

    normalized, parsed = _normalized_url(raw_url)
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise DomainValidationError(
            f"Could not resolve Ollama host '{parsed.hostname}'"
        ) from exc
    for *_, sockaddr in addresses:
        address = ipaddress.ip_address(sockaddr[0])
        if (
            address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        ):
            raise DomainValidationError(
                "Ollama URL resolves to a blocked link-local or reserved address"
            )
    return normalized


async def _read_json(response: httpx.Response) -> dict:
    if response.is_redirect:
        raise DomainValidationError("Ollama endpoint redirects are not allowed")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise DomainValidationError(
            f"Ollama returned HTTP {response.status_code}"
        ) from exc
    body = await response.aread()
    if len(body) > _MAX_RESPONSE_BYTES:
        raise DomainValidationError("Ollama response is too large")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DomainValidationError("Ollama returned an invalid JSON response") from exc
    if not isinstance(value, dict):
        raise DomainValidationError("Ollama returned an unexpected response")
    return value


def _brand(model_name: str, details: dict) -> tuple[str, str]:
    family = str(details.get("family") or "").lower()
    value = f"{model_name} {family}".lower()
    aliases = (
        (("qwen",), ("Qwen", "qwen")),
        (("llama",), ("Meta", "meta")),
        (("gemma",), ("Google", "google")),
        (("deepseek",), ("DeepSeek", "deepseek")),
        (("mistral", "mixtral", "codestral"), ("Mistral", "mistral")),
        (("phi",), ("Microsoft", "microsoft")),
        (("granite",), ("IBM", "ibm")),
        (("command-r", "command r", "aya"), ("Cohere", "cohere")),
        (("nemotron",), ("NVIDIA", "nvidia")),
        (("glm",), ("Z.ai", "zai")),
        (("kimi", "moonshot"), ("Moonshot AI", "moonshotai")),
        (("smollm",), ("Hugging Face", "huggingface")),
        (("solar",), ("Upstage", "upstage")),
    )
    for markers, brand in aliases:
        if any(marker in value for marker in markers):
            return brand
    if family:
        slug = re.sub(r"[^a-z0-9]+", "-", family).strip("-")
        if slug:
            return family.replace("-", " ").title(), slug
    return "Ollama", "ollama"


def _display_name(model_name: str) -> str:
    base, separator, tag = model_name.partition(":")
    label = base.replace("-", " ").replace("_", " ").strip().title()
    return f"{label} ({tag})" if separator else label


async def discover_ollama_models(base_url: str) -> list[DiscoveredOllamaModel]:
    normalized = await validate_ollama_url(base_url)
    timeout = httpx.Timeout(10.0, connect=5.0)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", f"{normalized}/api/tags") as response:
                tags = await _read_json(response)
            raw_models = tags.get("models")
            if not isinstance(raw_models, list):
                raise DomainValidationError(
                    "Ollama /api/tags response has no model list"
                )
            if len(raw_models) > _MAX_MODELS:
                raise DomainValidationError(
                    f"Ollama returned more than {_MAX_MODELS} models"
                )
            inspection_slots = asyncio.Semaphore(8)

            async def inspect(raw_model: object) -> DiscoveredOllamaModel | None:
                if not isinstance(raw_model, dict):
                    return None
                name = raw_model.get("name") or raw_model.get("model")
                if not isinstance(name, str) or not name.strip():
                    return None
                runtime_model_id = name.strip()
                async with (
                    inspection_slots,
                    client.stream(
                        "POST",
                        f"{normalized}/api/show",
                        json={"model": runtime_model_id},
                    ) as response,
                ):
                    shown = await _read_json(response)
                raw_capabilities = shown.get("capabilities")
                capabilities = (
                    {str(value).lower() for value in raw_capabilities}
                    if isinstance(raw_capabilities, list)
                    else set()
                )
                details = shown.get("details")
                if not isinstance(details, dict):
                    details = raw_model.get("details")
                if not isinstance(details, dict):
                    details = {}
                chef, chef_slug = _brand(runtime_model_id, details)
                supports_tools = "tools" in capabilities
                return DiscoveredOllamaModel(
                    model_id=f"ollama/{runtime_model_id}",
                    runtime_model_id=runtime_model_id,
                    display_name=_display_name(runtime_model_id),
                    chef=chef,
                    chef_slug=chef_slug,
                    multimodal="vision" in capabilities,
                    # Auxilia's fallback structured-output path is a forced tool
                    # call, so it is available only when Ollama confirms tools.
                    supports_structured_output=supports_tools,
                    supports_tools=supports_tools,
                )

            inspected = await asyncio.gather(*(inspect(model) for model in raw_models))
    except DomainValidationError:
        raise
    except httpx.TimeoutException as exc:
        raise DomainValidationError("Timed out while connecting to Ollama") from exc
    except httpx.HTTPError as exc:
        raise DomainValidationError(f"Could not connect to Ollama: {exc}") from exc
    return [model for model in inspected if model is not None]
