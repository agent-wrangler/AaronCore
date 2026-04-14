"""Shared model/provider normalization helpers."""

from __future__ import annotations

from urllib.parse import urlparse


_PROVIDER_SPECS = {
    "deepseek": {
        "aliases": ("deepseek", "ds"),
        "url_hints": ("deepseek",),
        "model_prefixes": ("deepseek",),
        "runtime_provider": "openai",
    },
    "openai": {
        "aliases": ("openai", "gpt", "chatgpt"),
        "url_hints": ("openai",),
        "model_prefixes": ("gpt-", "o1", "o3", "o4", "chatgpt"),
        "runtime_provider": "openai",
    },
    "claude": {
        "aliases": ("claude", "anthropic"),
        "url_hints": ("anthropic",),
        "model_prefixes": ("claude-",),
        "runtime_provider": "anthropic",
    },
    "qwen": {
        "aliases": ("qwen",),
        "url_hints": ("dashscope", "qwen"),
        "model_prefixes": ("qwen-", "qwen"),
        "runtime_provider": "openai",
    },
    "minimax": {
        "aliases": ("minimax", "mm", "hailuo"),
        "url_hints": ("minimax", "minimaxi"),
        "model_prefixes": ("minimax-", "minimax"),
        "runtime_provider": "minimax",
    },
    "doubao": {
        "aliases": ("doubao",),
        "url_hints": ("volcengine", "volces", "doubao"),
        "model_prefixes": ("doubao",),
        "runtime_provider": "openai",
    },
    "glm": {
        "aliases": ("glm", "zhipu", "chatglm"),
        "url_hints": ("bigmodel", "zhipu"),
        "model_prefixes": ("glm-", "chatglm"),
        "runtime_provider": "openai",
    },
    "kimi": {
        "aliases": ("kimi", "moonshot"),
        "url_hints": ("moonshot", "kimi"),
        "model_prefixes": ("moonshot", "kimi"),
        "runtime_provider": "openai",
    },
}

_CODEX_TRANSPORT_ALIASES = {"codex_cli", "codex-subscription", "codex_subscription"}
_TRANSPORT_ALIASES = {
    "openai_api": "openai_api",
    "openai-api": "openai_api",
    "anthropic_api": "anthropic_api",
    "anthropic-api": "anthropic_api",
    "codex_cli": "codex_cli",
    "codex-cli": "codex_cli",
    "codex-subscription": "codex_cli",
    "codex_subscription": "codex_cli",
}
_API_MODE_ALIASES = {
    "chat": "chat_completions",
    "chat_completions": "chat_completions",
    "chat-completions": "chat_completions",
    "anthropic": "anthropic_messages",
    "anthropic_messages": "anthropic_messages",
    "anthropic-messages": "anthropic_messages",
    "codex": "codex_cli",
    "codex_cli": "codex_cli",
    "codex-cli": "codex_cli",
}
_AUTH_MODE_ALIASES = {
    "api_key": "api_key",
    "api-key": "api_key",
    "codex_cli": "codex_cli",
    "codex-cli": "codex_cli",
    "codex-subscription": "codex_cli",
    "codex_subscription": "codex_cli",
}


def normalize_transport(value, *, base_url: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in _TRANSPORT_ALIASES:
        return _TRANSPORT_ALIASES[raw]
    normalized_base = str(base_url or "").strip().lower()
    if normalized_base.startswith("codex://"):
        return "codex_cli"
    return "openai_api"


def normalize_provider_key(value) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    for provider_key, spec in _PROVIDER_SPECS.items():
        if raw == provider_key or raw in spec["aliases"]:
            return provider_key
    return raw


def _value_matches_provider(provider_key: str, value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    spec = _PROVIDER_SPECS.get(provider_key, {})
    for alias in spec.get("aliases", ()):
        if alias and alias in lowered:
            return True
    for hint in spec.get("url_hints", ()):
        if hint and hint in lowered:
            return True
    for prefix in spec.get("model_prefixes", ()):
        if prefix and lowered.startswith(prefix):
            return True
    return False


def _base_url_host(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    candidate = text if "://" in text else f"https://{text}"
    try:
        return str(urlparse(candidate).hostname or "").strip().lower()
    except ValueError:
        return ""


def provider_key_from_base_url(base_url: str) -> str:
    lowered = str(base_url or "").strip().lower()
    if not lowered:
        return ""

    host = _base_url_host(lowered)
    if host:
        for provider_key, spec in _PROVIDER_SPECS.items():
            for hint in spec.get("url_hints", ()):
                if hint and hint in host:
                    return provider_key

    for provider_key in _PROVIDER_SPECS:
        if _value_matches_provider(provider_key, lowered):
            return provider_key
    return ""


def infer_provider_key(model_id: str, cfg: dict | None = None) -> str:
    config = cfg if isinstance(cfg, dict) else {}
    explicit = normalize_provider_key(config.get("provider_key"))

    transport = normalize_transport(config.get("transport"), base_url=config.get("base_url", ""))
    if transport == "codex_cli":
        return "openai"

    base_url_provider = provider_key_from_base_url(config.get("base_url") or "")

    if explicit:
        if base_url_provider and base_url_provider != explicit:
            return base_url_provider
        return explicit
    if base_url_provider:
        return base_url_provider

    candidates = [
        str(config.get("model") or "").strip().lower(),
        str(model_id or "").strip().lower(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        for provider_key in _PROVIDER_SPECS:
            if _value_matches_provider(provider_key, candidate):
                return provider_key
    return ""


def runtime_provider_kind(cfg: dict | None = None, *, provider_key: str = "", transport: str = "", api_mode: str = "") -> str:
    config = cfg if isinstance(cfg, dict) else {}
    normalized_transport = normalize_transport(transport or config.get("transport"), base_url=config.get("base_url", ""))
    if normalized_transport == "codex_cli":
        return "openai"

    normalized_provider_key = normalize_provider_key(provider_key or config.get("provider_key"))
    if normalized_provider_key:
        return _PROVIDER_SPECS.get(normalized_provider_key, {}).get("runtime_provider", "openai")

    normalized_api_mode = normalize_api_mode(api_mode or config.get("api_mode"), provider="", transport=normalized_transport)
    if normalized_api_mode == "anthropic_messages":
        return "anthropic"

    explicit_provider = str(config.get("provider") or "").strip().lower()
    if explicit_provider in {"openai", "anthropic", "minimax"}:
        return explicit_provider
    return "openai"


def normalize_api_mode(value, *, provider: str = "", transport: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in _API_MODE_ALIASES:
        return _API_MODE_ALIASES[raw]
    if normalize_transport(transport, base_url="") == "codex_cli":
        return "codex_cli"
    if str(provider or "").strip().lower() == "anthropic":
        return "anthropic_messages"
    return "chat_completions"


def normalize_auth_mode(value, *, transport: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in _AUTH_MODE_ALIASES:
        return _AUTH_MODE_ALIASES[raw]
    if normalize_transport(transport, base_url="") == "codex_cli":
        return "codex_cli"
    return "api_key"


def normalize_model_config(cfg: dict | None, *, fallback_model: str = "") -> dict:
    normalized = dict(cfg or {})
    model_name = str(normalized.get("model") or fallback_model or "").strip()
    if model_name:
        normalized["model"] = model_name
    elif "model" in normalized:
        normalized.pop("model", None)

    display_name = str(normalized.get("display_name") or "").strip()
    if display_name and display_name != model_name:
        normalized["display_name"] = display_name
    else:
        normalized.pop("display_name", None)

    base_url = str(normalized.get("base_url") or "").strip()
    transport = normalize_transport(normalized.get("transport"), base_url=base_url)
    provider_key = infer_provider_key(model_name or fallback_model, normalized)
    provider = runtime_provider_kind(normalized, provider_key=provider_key, transport=transport)
    api_mode = normalize_api_mode(normalized.get("api_mode"), provider=provider, transport=transport)
    auth_mode = normalize_auth_mode(normalized.get("auth_mode"), transport=transport)

    normalized["base_url"] = "codex://local" if transport == "codex_cli" else base_url
    normalized["transport"] = transport
    normalized["provider"] = provider
    normalized["api_mode"] = api_mode
    normalized["auth_mode"] = auth_mode
    normalized["vision"] = bool(normalized.get("vision", False))
    if provider_key:
        normalized["provider_key"] = provider_key
    elif "provider_key" in normalized:
        normalized.pop("provider_key", None)
    if transport == "codex_cli":
        normalized.pop("api_key", None)
    return normalized
