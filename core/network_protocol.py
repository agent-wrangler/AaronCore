import os
import re
import socket
import time
from urllib.parse import urlparse

import requests

_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
_LOCAL_PROXY_HOSTS = {"127.0.0.1", "localhost", "::1"}
_REACHABILITY_CACHE = {}


def _debug_write(stage: str, data: dict):
    try:
        from core.shared import debug_write as _dw
        _dw(stage, data)
    except Exception:
        pass


def get_proxy_env_values() -> dict:
    values = {}
    for key in _PROXY_ENV_KEYS:
        value = str(os.environ.get(key) or "").strip()
        if value:
            values[key] = value
    return values


def _normalize_url(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if re.match(r"^[\w.-]+\.[A-Za-z]{2,}(/.*)?$", text) and "://" not in text:
        return "https://" + text
    return text


def _parse_proxy_endpoint(proxy_url: str) -> tuple[str, int] | tuple[None, None]:
    raw = str(proxy_url or "").strip()
    if not raw:
        return None, None
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return None, None
    port = parsed.port
    if port is None:
        if parsed.scheme in {"https"}:
            port = 443
        elif parsed.scheme.startswith("socks"):
            port = 1080
        else:
            port = 80
    return host, int(port)


def _is_local_proxy_value(proxy_url: str) -> bool:
    host, _ = _parse_proxy_endpoint(proxy_url)
    return bool(host and host in _LOCAL_PROXY_HOSTS)


def _probe_tcp(host: str, port: int, timeout_sec: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except Exception:
        return False


def _can_resolve_host(host: str) -> bool | None:
    normalized = str(host or "").strip()
    if not normalized:
        return None
    try:
        socket.getaddrinfo(normalized, None)
        return True
    except Exception:
        return False


def classify_remote_target(target: str) -> dict:
    normalized = _normalize_url(target)
    if not normalized:
        return {
            "target_type": "unknown",
            "host": "",
            "url": "",
            "requires_external_network": False,
        }

    parsed = urlparse(normalized)
    host = str(parsed.hostname or "").strip().lower()
    lowered = normalized.lower()

    if "/chat/completions" in lowered or lowered.endswith("/messages") or "/anthropic/v1" in lowered:
        target_type = "model_api"
    elif "api." in host or "/api/" in lowered or re.search(r"/v\d+(?:/|$)", lowered):
        target_type = "api_endpoint"
    else:
        target_type = "website"

    return {
        "target_type": target_type,
        "host": host,
        "url": normalized,
        "requires_external_network": bool(host),
    }


def sense_network_environment(*, target_url: str = "", model_base_url: str = "") -> dict:
    proxy_env = get_proxy_env_values()
    local_proxy_values = {k: v for k, v in proxy_env.items() if _is_local_proxy_value(v)}

    local_proxy_alive = None
    if local_proxy_values:
        probe_results = []
        for value in local_proxy_values.values():
            host, port = _parse_proxy_endpoint(value)
            if host and port:
                probe_results.append(_probe_tcp(host, port))
        if probe_results:
            local_proxy_alive = any(probe_results)

    target = classify_remote_target(target_url)
    model_target = classify_remote_target(model_base_url)
    target_dns_ok = _can_resolve_host(target.get("host", ""))
    model_dns_ok = _can_resolve_host(model_target.get("host", ""))

    known_dns = [flag for flag in (target_dns_ok, model_dns_ok) if flag is not None]
    internet_reachable = any(known_dns) if known_dns else None

    preferred_route = "direct"
    if proxy_env and not (local_proxy_values and local_proxy_alive is False):
        preferred_route = "proxy"

    return {
        "has_proxy_env": bool(proxy_env),
        "proxy_env": proxy_env,
        "has_local_proxy": bool(local_proxy_values),
        "local_proxy_alive": local_proxy_alive,
        "internet_reachable": internet_reachable,
        "target_host": target.get("host", ""),
        "target_dns_ok": target_dns_ok,
        "model_host": model_target.get("host", ""),
        "model_dns_ok": model_dns_ok,
        "preferred_route": preferred_route,
    }


def decide_network_route(target: dict, env_status: dict) -> dict:
    target = target if isinstance(target, dict) else {}
    env_status = env_status if isinstance(env_status, dict) else {}

    if not target.get("requires_external_network"):
        return {"route": "direct", "reason": "no_external_network_required"}

    has_proxy_env = bool(env_status.get("has_proxy_env"))
    has_local_proxy = bool(env_status.get("has_local_proxy"))
    local_proxy_alive = env_status.get("local_proxy_alive")
    target_dns_ok = env_status.get("target_dns_ok")

    if has_local_proxy and local_proxy_alive is False:
        if target_dns_ok is False:
            return {"route": "fail_fast", "reason": "dead_local_proxy_and_target_unresolved"}
        return {"route": "direct", "reason": "dead_local_proxy_fallback_direct"}

    if has_proxy_env:
        return {"route": "proxy", "reason": "proxy_env_available"}

    if target_dns_ok is False:
        return {"route": "fail_fast", "reason": "target_host_unresolved"}

    return {"route": "direct", "reason": "direct_default"}


def format_network_failure(reason: str, target: dict, env_status: dict) -> dict:
    target = target if isinstance(target, dict) else {}
    env_status = env_status if isinstance(env_status, dict) else {}
    host = target.get("host") or target.get("url") or "目标地址"

    if reason == "dead_local_proxy_and_target_unresolved":
        return {
            "error_type": reason,
            "message": f"当前环境里的本地代理不可用，且系统无法直接解析或访问 `{host}`。",
            "user_safe_message": f"当前环境中的本地代理已失效，暂时也无法直接访问 `{host}`。",
        }
    if reason == "target_host_unresolved":
        return {
            "error_type": reason,
            "message": f"当前环境无法解析或访问 `{host}`。",
            "user_safe_message": f"当前环境暂时访问不了 `{host}`，可能是本地网络或外网条件限制。",
        }
    if reason == "model_api_unreachable":
        return {
            "error_type": reason,
            "message": f"当前默认模型 API `{host}` 不可达。",
            "user_safe_message": f"当前云模型暂时不可用，可能是网络环境或模型服务不可达。",
        }
    return {
        "error_type": reason or "network_unavailable",
        "message": f"当前环境无法访问 `{host}`。",
        "user_safe_message": f"当前环境暂时访问不了 `{host}`。",
    }


def _should_retry_without_proxy(exc: Exception, env_status: dict) -> bool:
    text = str(exc or "").lower()
    retry_signals = (
        "proxyerror",
        "failed to establish a new connection",
        "connection refused",
        "actively refused",
        "cannot connect to proxy",
    )
    return bool(env_status.get("has_local_proxy")) and env_status.get("local_proxy_alive") is False and any(sig in text for sig in retry_signals)


def _request_direct(method: str, url: str, **kwargs):
    session = requests.Session()
    session.trust_env = False
    return session.request(method=str(method or "GET").upper(), url=url, **kwargs)


def request_with_network_strategy(method: str, url: str, **kwargs):
    target = classify_remote_target(url)
    env_status = sense_network_environment(target_url=url)
    decision = decide_network_route(target, env_status)
    method_name = str(method or "GET").upper()

    _debug_write("network_route_decision", {
        "url": url,
        "method": method_name,
        "target_type": target.get("target_type"),
        "decision": decision,
        "env": {
            "has_proxy_env": env_status.get("has_proxy_env"),
            "has_local_proxy": env_status.get("has_local_proxy"),
            "local_proxy_alive": env_status.get("local_proxy_alive"),
            "target_dns_ok": env_status.get("target_dns_ok"),
        },
    })

    if decision["route"] == "fail_fast":
        failure = format_network_failure(decision["reason"], target, env_status)
        _REACHABILITY_CACHE[url] = {
            "ok": False,
            "checked_at": time.time(),
            "error_type": failure.get("error_type"),
            "message": failure.get("message"),
            "user_safe_message": failure.get("user_safe_message"),
        }
        raise RuntimeError(failure["message"])

    if decision["route"] == "direct":
        resp = _request_direct(method_name, url, **kwargs)
        _REACHABILITY_CACHE[url] = {
            "ok": True,
            "checked_at": time.time(),
            "error_type": "",
            "message": "",
            "user_safe_message": "",
        }
        return resp

    try:
        resp = requests.request(method_name, url, **kwargs)
        _REACHABILITY_CACHE[url] = {
            "ok": True,
            "checked_at": time.time(),
            "error_type": "",
            "message": "",
            "user_safe_message": "",
        }
        return resp
    except Exception as exc:
        if _should_retry_without_proxy(exc, env_status):
            _debug_write("network_retry_direct", {
                "url": url,
                "reason": str(exc),
                "proxy_env": env_status.get("proxy_env", {}),
            })
            resp = _request_direct(method_name, url, **kwargs)
            _REACHABILITY_CACHE[url] = {
                "ok": True,
                "checked_at": time.time(),
                "error_type": "",
                "message": "",
                "user_safe_message": "",
            }
            return resp
        failure = format_network_failure("model_api_unreachable" if target.get("target_type") == "model_api" else "network_unavailable", target, env_status)
        _REACHABILITY_CACHE[url] = {
            "ok": False,
            "checked_at": time.time(),
            "error_type": failure.get("error_type"),
            "message": failure.get("message"),
            "user_safe_message": failure.get("user_safe_message"),
        }
        raise


def post_with_network_strategy(url: str, **kwargs):
    return request_with_network_strategy("POST", url, **kwargs)


def get_with_network_strategy(url: str, **kwargs):
    return request_with_network_strategy("GET", url, **kwargs)


def preflight_remote_access(target_url: str, ttl_sec: float = 20.0) -> dict:
    target = classify_remote_target(target_url)
    env_status = sense_network_environment(target_url=target_url)
    decision = decide_network_route(target, env_status)

    cached = _REACHABILITY_CACHE.get(target_url)
    now = time.time()
    if cached and (now - float(cached.get("checked_at") or 0)) <= ttl_sec:
        return {
            "available": bool(cached.get("ok")),
            "source": "cache",
            "error_type": cached.get("error_type", ""),
            "message": cached.get("message", ""),
            "user_safe_message": cached.get("user_safe_message", ""),
            "route": decision.get("route", ""),
        }

    if decision.get("route") == "fail_fast":
        failure = format_network_failure(decision.get("reason", ""), target, env_status)
        payload = {
            "available": False,
            "source": "env",
            "error_type": failure.get("error_type", ""),
            "message": failure.get("message", ""),
            "user_safe_message": failure.get("user_safe_message", ""),
            "route": decision.get("route", ""),
        }
        _REACHABILITY_CACHE[target_url] = {
            "ok": False,
            "checked_at": now,
            "error_type": payload["error_type"],
            "message": payload["message"],
            "user_safe_message": payload["user_safe_message"],
        }
        return payload

    return {
        "available": True,
        "source": "optimistic",
        "error_type": "",
        "message": "",
        "user_safe_message": "",
        "route": decision.get("route", ""),
    }


def preflight_model_access(model_base_url: str, ttl_sec: float = 20.0) -> dict:
    target = classify_remote_target(model_base_url)
    env_status = sense_network_environment(target_url=model_base_url, model_base_url=model_base_url)
    decision = decide_network_route(target, env_status)

    cached = _REACHABILITY_CACHE.get(model_base_url)
    now = time.time()
    if cached and (now - float(cached.get("checked_at") or 0)) <= ttl_sec:
        return {
            "available": bool(cached.get("ok")),
            "source": "cache",
            "error_type": cached.get("error_type", ""),
            "message": cached.get("message", ""),
            "user_safe_message": cached.get("user_safe_message", ""),
            "route": decision.get("route", ""),
        }

    if decision.get("route") == "fail_fast":
        failure = format_network_failure(decision.get("reason", ""), target, env_status)
        payload = {
            "available": False,
            "source": "env",
            "error_type": failure.get("error_type", ""),
            "message": failure.get("message", ""),
            "user_safe_message": failure.get("user_safe_message", ""),
            "route": decision.get("route", ""),
        }
        _REACHABILITY_CACHE[model_base_url] = {
            "ok": False,
            "checked_at": now,
            "error_type": payload["error_type"],
            "message": payload["message"],
            "user_safe_message": payload["user_safe_message"],
        }
        return payload

    return {
        "available": True,
        "source": "optimistic",
        "error_type": "",
        "message": "",
        "user_safe_message": "",
        "route": decision.get("route", ""),
    }
