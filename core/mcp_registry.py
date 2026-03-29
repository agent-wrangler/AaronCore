"""
MCP Registry — 从官方注册表拉取可用 MCP 服务，缓存到本地，支持搜索和一键安装。
遵循 init(*, debug_write, cache_path) 依赖注入模式。
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── 依赖注入 ──
_debug_write = lambda stage, data: None
_CACHE_PATH: Path | None = None

_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0.1/servers"
_CACHE_TTL = 86400  # 24h


def init(*, debug_write=None, cache_path: Path = None):
    global _debug_write, _CACHE_PATH
    if debug_write:
        _debug_write = debug_write
    if cache_path:
        _CACHE_PATH = cache_path


def _load_cache() -> dict | None:
    if not _CACHE_PATH or not _CACHE_PATH.exists():
        return None
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        fetched = data.get("fetched_at", "")
        if fetched:
            ts = datetime.fromisoformat(fetched).timestamp()
            if time.time() - ts < _CACHE_TTL:
                return data
    except Exception:
        pass
    return None


def _save_cache(servers: list):
    if not _CACHE_PATH:
        return
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "servers": servers,
    }
    _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_npm_stdio(server: dict) -> dict | None:
    """从 registry server 条目中提取 npm+stdio 的 package 信息，不符合返回 None"""
    packages = server.get("packages", [])
    for pkg in packages:
        if pkg.get("registryType") == "npm" and pkg.get("transport", {}).get("type") == "stdio":
            return pkg
    return None


def _simplify(server: dict, pkg: dict) -> dict:
    """将 registry 条目转为简化缓存格式"""
    env_vars = []
    for ev in pkg.get("environmentVariables", []):
        env_vars.append({
            "name": ev.get("name", ""),
            "description": ev.get("description", ""),
            "required": ev.get("isRequired", False),
        })
    icon = None
    icons = server.get("icons", [])
    if icons and isinstance(icons, list):
        icon = icons[0].get("src") if isinstance(icons[0], dict) else None
    return {
        "name": server.get("name", ""),
        "title": server.get("title") or server.get("name", ""),
        "description": server.get("description", ""),
        "npm_package": pkg.get("identifier", ""),
        "version": pkg.get("version", ""),
        "env_vars": env_vars,
        "repo": server.get("repository", {}).get("url", "") if isinstance(server.get("repository"), dict) else server.get("repository", ""),
        "icon": icon,
    }


def fetch_registry(force=False) -> list:
    """拉取注册表，缓存到本地（24h 有效）"""
    if not force:
        cached = _load_cache()
        if cached:
            return cached.get("servers", [])

    all_servers = []
    cursor = None
    for _ in range(3):  # 最多 3 页
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(_REGISTRY_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            _debug_write("mcp_registry_fetch_error", {"error": str(exc)})
            break

        servers = data.get("servers", [])
        for item in servers:
            s = item.get("server", item)  # 解包 {"server": {...}, "_meta": {...}}
            pkg = _extract_npm_stdio(s)
            if pkg:
                all_servers.append(_simplify(s, pkg))

        cursor = data.get("metadata", {}).get("nextCursor")
        if not cursor:
            break

    if all_servers:
        _save_cache(all_servers)
        _debug_write("mcp_registry_fetched", {"count": len(all_servers)})
    else:
        # 拉取失败时尝试返回过期缓存
        if _CACHE_PATH and _CACHE_PATH.exists():
            try:
                return json.loads(_CACHE_PATH.read_text(encoding="utf-8")).get("servers", [])
            except Exception:
                pass
    return all_servers


def search_registry(query: str, limit=20) -> list:
    """在缓存中搜索（名称 + 描述 + npm 包名匹配）"""
    servers = fetch_registry()
    if not query or not query.strip():
        return servers[:limit]

    q = query.lower().strip()
    scored = []
    for s in servers:
        score = 0
        name = (s.get("name") or "").lower()
        title = (s.get("title") or "").lower()
        desc = (s.get("description") or "").lower()
        npm = (s.get("npm_package") or "").lower()

        if q in name:
            score += 10
        if q in title:
            score += 8
        if q in npm:
            score += 6
        if q in desc:
            score += 3

        # 多词匹配
        words = q.split()
        if len(words) > 1:
            for w in words:
                if w in name or w in title or w in desc or w in npm:
                    score += 2

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:limit]]


def get_install_config(server_name: str) -> dict | None:
    """从注册表条目生成 mcp_client.add_server() 所需的配置"""
    servers = fetch_registry()
    target = None
    for s in servers:
        if s.get("name") == server_name:
            target = s
            break
    if not target:
        return None

    npm_pkg = target.get("npm_package", "")
    if not npm_pkg:
        return None

    env = {}
    for ev in target.get("env_vars", []):
        env[ev["name"]] = ""  # 占位，用户需要填

    config = {
        "name": server_name,
        "command": "npx",
        "args": ["-y", npm_pkg],
        "transport": "stdio",
    }
    if env:
        config["env"] = env
    config["_meta"] = {
        "title": target.get("title", ""),
        "description": target.get("description", ""),
        "env_vars": target.get("env_vars", []),
    }
    return config
