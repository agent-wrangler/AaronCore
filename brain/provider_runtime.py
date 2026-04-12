import os
from urllib.parse import urlparse

import requests

from . import codex_cli_runtime as _codex_cli_runtime

_DOMESTIC_HOSTS = {"minimaxi.com", "dashscope.aliyuncs.com", "open.bigmodel.cn", "api.volcengine.com"}


def extract_network_meta(resp) -> dict:
    meta = getattr(resp, "_aaroncore_network_meta", None)
    if not isinstance(meta, dict):
        meta = getattr(resp, "_novacore_network_meta", None)
    return dict(meta) if isinstance(meta, dict) else {}


def debug_proxy_fallback(stage: str, data: dict):
    try:
        from core.shared import debug_write

        debug_write(stage, data)
    except Exception:
        pass


def env_proxy_values() -> dict:
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
    values = {}
    for key in keys:
        value = str(os.environ.get(key) or "").strip()
        if value:
            values[key] = value
    return values


def has_local_proxy_env() -> bool:
    for value in env_proxy_values().values():
        lowered = value.lower()
        if "127.0.0.1" in lowered or "localhost" in lowered:
            return True
    return False


def should_retry_without_env(exc: Exception) -> bool:
    text = str(exc or "").lower()
    retry_signals = (
        "proxyerror",
        "failed to establish a new connection",
        "connection refused",
        "actively refused",
        "cannot connect to proxy",
    )
    return has_local_proxy_env() and any(sig in text for sig in retry_signals)


def post_with_proxy_fallback(url: str, **kwargs):
    host = urlparse(url).hostname or ""
    if any(domain in host for domain in _DOMESTIC_HOSTS):
        kwargs.setdefault("proxies", {"http": None, "https": None})
    return requests.request("POST", url, **kwargs)


def is_minimax_provider(cfg: dict) -> bool:
    model = str(cfg.get("model", "")).lower()
    base_url = str(cfg.get("base_url", "")).lower()
    return "minimax" in model or "minimaxi.com" in base_url


def is_anthropic_provider(cfg: dict) -> bool:
    if is_minimax_provider(cfg):
        return False
    base_url = str(cfg.get("base_url", "")).lower()
    return "/anthropic" in base_url


def is_codex_cli_provider(cfg: dict) -> bool:
    return _codex_cli_runtime.is_codex_cli_provider(cfg)


def validate_codex_cli_login(*, timeout: int = 10) -> tuple[bool, str]:
    return _codex_cli_runtime.validate_codex_cli_login(timeout=timeout)


def build_openai_base_url(base_url: str, cfg: dict | None = None) -> str:
    url = str(base_url or "").rstrip("/")
    if cfg and is_minimax_provider(cfg):
        if url.endswith("/anthropic/v1"):
            return url[: -len("/anthropic/v1")] + "/v1"
        if url.endswith("/anthropic"):
            return url[: -len("/anthropic")] + "/v1"
        if "/anthropic/" in url:
            return url.replace("/anthropic", "", 1)
    return url


def minimax_toolcall_fallback_model(model_name: str) -> str:
    model = str(model_name or "").strip()
    lowered = model.lower()
    if lowered == "minimax-m2.7":
        return "MiniMax-M2.5"
    if lowered == "minimax-m2.7-highspeed":
        return "MiniMax-M2.5-highspeed"
    return model


def is_minimax_invalid_chat_setting(status_code: int, body_text: str, cfg: dict) -> bool:
    if not is_minimax_provider(cfg):
        return False
    if int(status_code or 0) != 400:
        return False
    text = str(body_text or "").lower()
    return "invalid chat setting" in text or '"http_code":"400"' in text and "2013" in text


def is_minimax_server_tool_error(status_code: int, body_text: str, cfg: dict) -> bool:
    if not is_minimax_provider(cfg):
        return False
    code = int(status_code or 0)
    if code < 500:
        return False
    text = str(body_text or "").lower()
    return "server_error" in text or "unknown error" in text or '"http_code":"500"' in text


def with_minimax_fallback_cfg(cfg: dict, body_text: str, status_code: int) -> dict | None:
    if not (
        is_minimax_invalid_chat_setting(status_code, body_text, cfg)
        or is_minimax_server_tool_error(status_code, body_text, cfg)
    ):
        return None
    fallback_model = minimax_toolcall_fallback_model(cfg.get("model", ""))
    if not fallback_model or fallback_model == cfg.get("model"):
        return None
    retry_cfg = dict(cfg)
    retry_cfg["model"] = fallback_model
    try:
        from core.shared import debug_write

        debug_write(
            "minimax_toolcall_fallback",
            {
                "from_model": cfg.get("model", ""),
                "to_model": fallback_model,
                "status": int(status_code or 0),
                "reason": str(body_text or "")[:300],
            },
        )
    except Exception:
        pass
    return retry_cfg


def build_openai_extra_body(cfg: dict) -> dict | None:
    if is_minimax_provider(cfg):
        return {"reasoning_split": True}
    return None


def build_anthropic_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/anthropic/v1/messages"):
        return url
    if url.endswith("/anthropic"):
        return url + "/v1/messages"
    if url.endswith("/anthropic/v1"):
        return url + "/messages"
    if "/v1" in url:
        return url.rsplit("/v1", 1)[0] + "/anthropic/v1/messages"
    return url + "/anthropic/v1/messages"
