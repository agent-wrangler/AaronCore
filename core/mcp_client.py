"""
MCP Client 适配器 — 管理 MCP server 连接，发现工具，桥接到技能系统。
遵循 init(*, debug_write, llm_call) 依赖注入模式。
"""
import asyncio
import json
from pathlib import Path
from typing import Any

# ── 依赖注入 ──
_debug_write = lambda stage, data: None
_llm_call = lambda prompt: ""

_MCP_SERVERS_PATH: Path | None = None
_active_sessions: dict[str, Any] = {}
_MCP_AVAILABLE = False

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_AVAILABLE = True
except ImportError:
    pass


def init(*, debug_write=None, llm_call=None, servers_path: Path = None):
    global _debug_write, _llm_call, _MCP_SERVERS_PATH
    if debug_write:
        _debug_write = debug_write
    if llm_call:
        _llm_call = llm_call
    if servers_path:
        _MCP_SERVERS_PATH = servers_path


def is_available() -> bool:
    return _MCP_AVAILABLE


def load_mcp_config() -> dict:
    if _MCP_SERVERS_PATH and _MCP_SERVERS_PATH.exists():
        try:
            return json.loads(_MCP_SERVERS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"servers": {}}


def save_mcp_config(config: dict):
    if _MCP_SERVERS_PATH:
        _MCP_SERVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MCP_SERVERS_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_server_status() -> dict:
    """返回所有 server 的连接状态"""
    config = load_mcp_config()
    result = {}
    for name, cfg in config.get("servers", {}).items():
        result[name] = {
            "enabled": cfg.get("enabled", True),
            "transport": cfg.get("transport", "stdio"),
            "connected": name in _active_sessions,
            "tools": _get_session_tools(name),
        }
    return result


def _get_session_tools(server_name: str) -> list:
    session_info = _active_sessions.get(server_name)
    if not session_info:
        return []
    return session_info.get("tools", [])


async def connect_server(name: str) -> dict:
    """连接一个 MCP server，发现工具，注册到技能系统"""
    if not _MCP_AVAILABLE:
        return {"ok": False, "error": "mcp \u5305\u672a\u5b89\u88c5\uff0c\u8bf7\u8fd0\u884c: pip install mcp"}

    config = load_mcp_config()
    server_cfg = config.get("servers", {}).get(name)
    if not server_cfg:
        return {"ok": False, "error": f"\u672a\u627e\u5230\u670d\u52a1\u5668\u914d\u7f6e: {name}"}

    transport = server_cfg.get("transport", "stdio")
    if transport != "stdio":
        return {"ok": False, "error": f"\u6682\u4e0d\u652f\u6301 {transport} \u4f20\u8f93\u65b9\u5f0f"}

    command = server_cfg.get("command", "")
    args = server_cfg.get("args", [])
    env = server_cfg.get("env")

    if not command:
        return {"ok": False, "error": "\u7f3a\u5c11 command \u914d\u7f6e"}

    try:
        server_params = StdioServerParameters(
            command=command, args=args, env=env
        )
        # 启动 stdio 连接
        read_stream, write_stream = await _start_stdio(server_params)
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = []
            for tool in tools_result.tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                }
                tools.append(tool_info)
                # 注册到技能系统
                _register_tool_as_skill(name, tool_info)

            _active_sessions[name] = {
                "tools": tools,
                "session": session,
            }
            _debug_write("mcp_connect", {"server": name, "tools_count": len(tools)})
            return {"ok": True, "tools": tools}
    except Exception as exc:
        _debug_write("mcp_connect_error", {"server": name, "error": str(exc)})
        return {"ok": False, "error": str(exc)}


async def _start_stdio(params):
    """启动 stdio 传输"""
    return await stdio_client(params).__aenter__()


def _register_tool_as_skill(server_name: str, tool_info: dict):
    """将 MCP tool 注册为 NovaCore 技能"""
    from core.skills import register_mcp_skill

    tool_name = tool_info["name"]
    skill_id = f"mcp_{server_name}_{tool_name}"
    description = tool_info.get("description", "")

    # 用 LLM 生成中文关键词
    keywords = _generate_keywords(tool_name, description)

    register_mcp_skill(skill_id, {
        "name": f"{tool_name} ({server_name})",
        "keywords": keywords,
        "anti_keywords": [],
        "description": description,
        "priority": 15,
        "category": "MCP \u5de5\u5177",
        "status": "ready",
        "enabled": True,
        "source": "mcp",
        "mcp_server": server_name,
        "mcp_tool": tool_name,
        "input_schema": tool_info.get("input_schema", {}),
        "execute": _make_bridge_executor(server_name, tool_name, tool_info),
        "metadata": {"server": server_name, "tool": tool_name},
    })


def _generate_keywords(tool_name: str, description: str) -> list:
    """用 LLM 为 MCP 工具生成中文关键词"""
    keywords = [tool_name]
    if not _llm_call:
        return keywords
    try:
        prompt = (
            f"\u8bf7\u4e3a\u4ee5\u4e0b\u5de5\u5177\u751f\u6210 3-5 \u4e2a\u4e2d\u6587\u5173\u952e\u8bcd\uff0c\u7528\u4e8e\u8def\u7531\u5339\u914d\u3002"
            f"\u5de5\u5177\u540d: {tool_name}\n\u63cf\u8ff0: {description}\n"
            f"\u53ea\u8fd4\u56de\u5173\u952e\u8bcd\uff0c\u7528\u9017\u53f7\u5206\u9694\uff0c\u4e0d\u8981\u5176\u4ed6\u5185\u5bb9\u3002"
        )
        result = _llm_call(prompt)
        if result:
            extra = [k.strip() for k in result.split(",") if k.strip()]
            # 也处理中文逗号
            if len(extra) <= 1 and "\uff0c" in result:
                extra = [k.strip() for k in result.split("\uff0c") if k.strip()]
            keywords.extend(extra[:5])
    except Exception:
        pass
    return keywords


def _make_bridge_executor(server_name: str, tool_name: str, tool_info: dict):
    """创建桥接执行函数：自然语言 → 参数提取 → call_tool → 返回结果"""
    input_schema = tool_info.get("input_schema", {})

    def execute(user_input: str, context: dict = None) -> str:
        # 用 LLM 从自然语言提取参数
        params = _extract_params(user_input, tool_name, input_schema)
        # 调用 MCP tool
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run, _call_tool(server_name, tool_name, params)
                    ).result(timeout=30)
            else:
                result = asyncio.run(_call_tool(server_name, tool_name, params))
            return result
        except Exception as exc:
            return f"MCP \u5de5\u5177\u8c03\u7528\u5931\u8d25: {str(exc)[:100]}"

    return execute


def _extract_params(user_input: str, tool_name: str, schema: dict) -> dict:
    """用 LLM 从用户输入提取工具参数"""
    if not schema.get("properties"):
        return {}
    if not _llm_call:
        return {}
    try:
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        prompt = (
            f"\u7528\u6237\u8bf4\uff1a{user_input}\n"
            f"\u9700\u8981\u8c03\u7528\u5de5\u5177 {tool_name}\uff0c\u53c2\u6570 schema \u5982\u4e0b\uff1a\n{schema_str}\n"
            f"\u8bf7\u4ece\u7528\u6237\u8f93\u5165\u4e2d\u63d0\u53d6\u53c2\u6570\uff0c\u8fd4\u56de\u7eaf JSON \u5bf9\u8c61\uff0c\u4e0d\u8981\u5176\u4ed6\u5185\u5bb9\u3002"
        )
        result = _llm_call(prompt)
        if result:
            # 尝试提取 JSON
            result = result.strip()
            if result.startswith("```"):
                lines = result.split("\n")
                result = "\n".join(lines[1:-1])
            return json.loads(result)
    except Exception:
        pass
    return {}


async def _call_tool(server_name: str, tool_name: str, params: dict) -> str:
    """调用 MCP server 的工具"""
    session_info = _active_sessions.get(server_name)
    if not session_info or not session_info.get("session"):
        return f"MCP \u670d\u52a1\u5668 {server_name} \u672a\u8fde\u63a5"

    session = session_info["session"]
    try:
        result = await session.call_tool(tool_name, arguments=params)
        # 提取文本内容
        texts = []
        for content in result.content:
            if hasattr(content, 'text'):
                texts.append(content.text)
        return "\n".join(texts) if texts else str(result)
    except Exception as exc:
        return f"\u8c03\u7528\u5931\u8d25: {str(exc)[:200]}"


async def disconnect_server(name: str) -> dict:
    """断开 MCP server 连接"""
    session_info = _active_sessions.pop(name, None)
    if not session_info:
        return {"ok": True, "message": "\u672a\u8fde\u63a5"}

    # 移除该 server 注册的技能
    from core.skills import unregister_mcp_skill, get_all_skills_for_ui
    all_skills = get_all_skills_for_ui()
    to_remove = [sid for sid, s in all_skills.items()
                 if s.get("source") == "mcp" and s.get("mcp_server") == name]
    for sid in to_remove:
        unregister_mcp_skill(sid)

    _debug_write("mcp_disconnect", {"server": name, "removed_skills": len(to_remove)})
    return {"ok": True, "removed_tools": len(to_remove)}


def add_server(name: str, command: str, args: list = None,
               transport: str = "stdio", env: dict = None) -> dict:
    """添加 MCP server 配置"""
    config = load_mcp_config()
    servers = config.setdefault("servers", {})
    if name in servers:
        return {"ok": False, "error": f"\u670d\u52a1\u5668 {name} \u5df2\u5b58\u5728"}
    servers[name] = {
        "command": command,
        "args": args or [],
        "enabled": True,
        "transport": transport,
    }
    if env:
        servers[name]["env"] = env
    save_mcp_config(config)
    return {"ok": True}


def remove_server(name: str) -> dict:
    """移除 MCP server 配置"""
    config = load_mcp_config()
    servers = config.get("servers", {})
    if name not in servers:
        return {"ok": False, "error": f"\u670d\u52a1\u5668 {name} \u4e0d\u5b58\u5728"}
    del servers[name]
    save_mcp_config(config)
    # 如果已连接，断开
    if name in _active_sessions:
        asyncio.get_event_loop().create_task(disconnect_server(name))
    return {"ok": True}


async def connect_all_enabled():
    """启动时连接所有已启用的 MCP server"""
    if not _MCP_AVAILABLE:
        return
    config = load_mcp_config()
    for name, cfg in config.get("servers", {}).items():
        if cfg.get("enabled", True):
            try:
                await connect_server(name)
            except Exception as exc:
                _debug_write("mcp_startup_error", {"server": name, "error": str(exc)})
