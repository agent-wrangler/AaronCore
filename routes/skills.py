"""技能商店路由：技能列表、启用/禁用、MCP 管理"""
from fastapi import APIRouter, Request
from core import shared as S

router = APIRouter()


@router.get("/skills")
async def get_skills():
    if not S.NOVA_CORE_READY:
        return {"skills": [], "ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        skills_data = S.get_all_skills_for_ui()
        skills = []
        for name, info in skills_data.items():
            skills.append({
                "id": name,
                "name": info.get("name", name),
                "keywords": info.get("keywords", []),
                "description": info.get("description", ""),
                "priority": info.get("priority", 10),
                "status": info.get("status", "ready"),
                "category": info.get("category", "\u901a\u7528"),
                "enabled": info.get("enabled", True),
                "source": info.get("source", "native"),
            })
        skills.sort(key=lambda item: (item.get("priority", 10), item.get("name", "")))
        return {"skills": skills, "ready": True}
    except Exception as exc:
        return {"skills": [], "ready": False, "error": str(exc)}


@router.get("/skills/news/headlines")
async def get_news_headlines():
    try:
        from core.skills.news import _parse_rss, GOOGLE_NEWS_FEEDS
        url = GOOGLE_NEWS_FEEDS.get("top", list(GOOGLE_NEWS_FEEDS.values())[0])
        items, _ = _parse_rss(url, limit=6)
        headlines = [item.get("title", "") for item in items if item.get("title")]
        return {"headlines": headlines}
    except Exception as e:
        return {"headlines": [], "error": str(e)}


@router.post("/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: str):
    if not S.NOVA_CORE_READY:
        return {"ok": False, "error": "core_not_ready"}
    try:
        all_skills = S.get_all_skills_for_ui()
        skill = all_skills.get(skill_id)
        if not skill:
            return {"ok": False, "error": "skill_not_found"}
        new_enabled = not skill.get("enabled", True)
        ok = S.set_skill_enabled(skill_id, new_enabled)
        return {"ok": ok, "enabled": new_enabled}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── MCP 管理端点 ──

@router.get("/skills/mcp/servers")
async def get_mcp_servers():
    try:
        from core import mcp_client
        available = mcp_client.is_available()
        servers = mcp_client.get_server_status() if available else {}
        return {"ok": True, "available": available, "servers": servers}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers")
async def add_mcp_server(request: Request):
    try:
        from core import mcp_client
        body = await request.json()
        name = body.get("name", "").strip()
        command = body.get("command", "").strip()
        args = body.get("args", [])
        transport = body.get("transport", "stdio")
        env = body.get("env")
        if not name or not command:
            return {"ok": False, "error": "\u7f3a\u5c11 name \u6216 command"}
        result = mcp_client.add_server(name, command, args, transport, env)
        if result.get("ok") and body.get("auto_connect", True):
            connect_result = await mcp_client.connect_server(name)
            result["connect"] = connect_result
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/skills/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    try:
        from core import mcp_client
        await mcp_client.disconnect_server(name)
        return mcp_client.remove_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers/{name}/connect")
async def connect_mcp_server(name: str):
    try:
        from core import mcp_client
        return await mcp_client.connect_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers/{name}/disconnect")
async def disconnect_mcp_server(name: str):
    try:
        from core import mcp_client
        return await mcp_client.disconnect_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── MCP 注册表端点 ──

@router.get("/skills/mcp/registry")
async def get_mcp_registry():
    try:
        from core import mcp_registry
        servers = mcp_registry.fetch_registry()
        return {"ok": True, "servers": servers}
    except Exception as exc:
        return {"ok": False, "servers": [], "error": str(exc)}


@router.get("/skills/mcp/registry/search")
async def search_mcp_registry(q: str = ""):
    try:
        from core import mcp_registry
        results = mcp_registry.search_registry(q)
        return {"ok": True, "servers": results}
    except Exception as exc:
        return {"ok": False, "servers": [], "error": str(exc)}


@router.post("/skills/mcp/registry/install")
async def install_from_registry(request: Request):
    try:
        from core import mcp_registry, mcp_client
        body = await request.json()
        name = body.get("name", "").strip()
        env_overrides = body.get("env", {})
        if not name:
            return {"ok": False, "error": "\u7f3a\u5c11\u670d\u52a1\u540d\u79f0"}

        config = mcp_registry.get_install_config(name)
        if not config:
            return {"ok": False, "error": f"\u6ce8\u518c\u8868\u4e2d\u672a\u627e\u5230: {name}"}

        # 合并用户提供的环境变量
        env = config.get("env", {})
        if env_overrides:
            env.update(env_overrides)

        result = mcp_client.add_server(
            name=config["name"],
            command=config["command"],
            args=config["args"],
            transport=config["transport"],
            env=env if env else None,
        )
        if result.get("ok"):
            connect_result = await mcp_client.connect_server(name)
            result["connect"] = connect_result
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
