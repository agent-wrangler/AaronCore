# tool_adapter - skill 注册表 → OpenAI function calling tools 格式转换
# 以及 tool_call 执行桥接

import json
import time
import threading
import re as _re
from pathlib import Path as _Path

from core.executor import execute as _execute
from core.fs_protocol import (
    execute_write_file_action as _execute_write_file_protocol,
    load_export_state as _load_export_state,
    normalize_user_special_path as _normalize_user_special_path,
)

# ── ask_user 共享状态 ──
_ask_user_lock = threading.Lock()
_ask_user_pending = None   # {"question": str, "options": [...], "id": str}
_ask_user_answer = None    # 用户选择的结果

def ask_user_submit(question_id: str, answer: str) -> bool:
    """前端提交用户的选择"""
    global _ask_user_answer
    with _ask_user_lock:
        if _ask_user_pending and _ask_user_pending.get("id") == question_id:
            _ask_user_answer = answer
            return True
    return False

def get_ask_user_pending() -> dict | None:
    """获取当前待回答的问题（前端轮询或 SSE 推送用）"""
    with _ask_user_lock:
        return dict(_ask_user_pending) if _ask_user_pending else None

# ── 配置文件路径 ──
_CONFIGS_DIR = _Path(__file__).resolve().parent.parent / "configs"

# ── 注入依赖 ──
_get_all_skills = lambda: {}
_debug_write = lambda stage, data: None
_l2_search_relevant = lambda q, **kw: []
_load_l3_long_term = lambda **kw: []
_find_relevant_knowledge = lambda q, **kw: []


def _summarize_tool_response_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    text = text.replace("`", "")
    text = text.replace("\r", "\n")
    lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:140] + ("..." if len(summary) > 140 else "")


def _resolve_user_file_target(file_path: str):
    raw = _normalize_user_special_path(str(file_path or "").replace("\\", "/").strip())
    if not raw:
        return None
    root = _Path(__file__).resolve().parent.parent
    target = _Path(raw)
    if not target.is_absolute():
        target = (root / raw.lstrip("./")).resolve()

        # 如果只是裸文件名，且刚保存过同主题文件，优先落在最近保存目录旁边。
        if "/" not in raw and "\\" not in raw:
            state = _load_export_state()
            last_dir = _normalize_user_special_path(str(state.get("last_export_dir") or "").strip())
            last_path = _normalize_user_special_path(str(state.get("last_export_path") or "").strip())
            if last_dir:
                last_dir_path = _Path(last_dir)
                candidate = (last_dir_path / raw).resolve()

                def _norm_stem(p: str) -> str:
                    stem = _Path(str(p or "")).stem
                    stem = _re.sub(r'^\d{4}-\d{2}-\d{2}_\d{6}_', '', stem)
                    return stem.strip().lower()

                raw_stem = _norm_stem(raw)
                last_stem = _norm_stem(last_path)
                same_topic = bool(raw_stem and last_stem and (raw_stem == last_stem or raw_stem in last_stem or last_stem in raw_stem))
                if candidate.exists() or same_topic:
                    return candidate

        return target
    return target.resolve()


_PROTOCOL_CONTEXT_SKILLS = {
    "folder_explore",
    "open_target",
    "save_export",
    "file_copy",
    "file_move",
    "file_delete",
    "app_target",
    "ui_interaction",
    "write_file",
}
_PROTOCOL_DEFAULT_OPTIONS = {
    "folder_explore": "inspect",
    "open_target": "open",
    "save_export": "save",
    "file_copy": "copy",
    "file_move": "move",
    "file_delete": "delete",
    "write_file": "write_file",
    "app_target": "launch",
    "ui_interaction": "ui_interact",
}
_PROTOCOL_CONTEXT_MANIFESTS = {
    "folder_explore": {"context_need": ["Desktop_Files"]},
    "open_target": {"context_need": ["Desktop_Files"]},
}


def _merge_context_dict(base: dict | None, extra: dict | None) -> dict:
    merged = dict(base) if isinstance(base, dict) else {}
    extra = extra if isinstance(extra, dict) else {}
    for key, value in extra.items():
        if key not in merged or not merged.get(key):
            merged[key] = value
            continue
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            nested = dict(value)
            nested.update(existing)
            merged[key] = nested
    return merged


def _normalize_protocol_fs_target(target: dict | None, *, default_option: str = "inspect") -> dict | None:
    target = target if isinstance(target, dict) else {}
    path = str(target.get("path") or "").strip()
    if not path:
        return None
    normalized = dict(target)
    normalized["path"] = path
    normalized["option"] = str(normalized.get("option") or default_option).strip() or default_option
    return normalized


def _extract_recent_context_paths(context: dict | None) -> list[str]:
    context = context if isinstance(context, dict) else {}
    recent_history = context.get("recent_history") if isinstance(context.get("recent_history"), list) else []
    patterns = (
        _re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+\.(?:md|html|txt|json|py|js|css)', _re.I),
        _re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+', _re.I),
    )
    paths = []
    seen = set()
    for item in reversed(recent_history):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        for pattern in patterns:
            for match in pattern.findall(content):
                value = str(match).strip().strip(".,;:()[]{}<>\"'")
                if not value:
                    continue
                lowered = value.replace("/", "\\").lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                paths.append(value)
                if len(paths) >= 8:
                    return paths
    return paths


def _infer_recent_directory_from_context(context: dict | None) -> str:
    scores: dict[str, int] = {}
    for raw in _extract_recent_context_paths(context):
        try:
            path_obj = _Path(str(raw).replace("\\", "/"))
        except Exception:
            continue
        base = path_obj if not path_obj.suffix else path_obj.parent
        weight = 4
        current = base
        for _ in range(3):
            current_str = str(current).strip()
            if not current_str or current_str in {".", "/"}:
                break
            scores[current_str] = scores.get(current_str, 0) + weight
            parent = current.parent
            if parent == current:
                break
            current = parent
            weight = max(1, weight - 1)
    if not scores:
        return ""
    ranked = sorted(scores.items(), key=lambda item: (-item[1], -len(item[0])))
    return ranked[0][0]


def _apply_protocol_context(name: str, ctx: dict, user_input: str) -> dict:
    if name not in _PROTOCOL_CONTEXT_SKILLS:
        return ctx

    default_option = _PROTOCOL_DEFAULT_OPTIONS.get(name, "inspect")
    context_data = ctx.get("context_data") if isinstance(ctx.get("context_data"), dict) else {}
    fs_target = _normalize_protocol_fs_target(ctx.get("fs_target"), default_option=default_option)
    if not fs_target:
        fs_target = _normalize_protocol_fs_target(context_data.get("fs_target"), default_option=default_option)

    candidate_path = ""
    if name == "write_file":
        candidate_path = str(ctx.get("file_path") or ctx.get("path") or ctx.get("target") or "").strip()
    elif name in {"file_copy", "file_move", "file_delete", "save_export", "folder_explore", "open_target"}:
        candidate_path = str(ctx.get("path") or ctx.get("source") or ctx.get("file_path") or ctx.get("target") or "").strip()
    elif name == "app_target":
        candidate_path = str(ctx.get("path") or ctx.get("target") or ctx.get("app") or "").strip()
    elif name == "ui_interaction":
        candidate_path = str(ctx.get("target") or ctx.get("window_title") or "").strip()

    if candidate_path and not fs_target and not candidate_path.startswith(("http://", "https://")):
        fs_target = {"path": candidate_path, "option": default_option, "source": "tool_args"}

    if not fs_target:
        try:
            from core.context_pull import pull_context_data

            pulled = pull_context_data(user_input or candidate_path, _PROTOCOL_CONTEXT_MANIFESTS.get(name, {}))
        except Exception:
            pulled = {}
        if isinstance(pulled, dict):
            context_data = _merge_context_dict(context_data, pulled)
            fs_target = _normalize_protocol_fs_target(context_data.get("fs_target"), default_option=default_option)

    if not fs_target:
        inferred_dir = _infer_recent_directory_from_context(ctx)
        if inferred_dir:
            fs_target = {"path": inferred_dir, "option": default_option, "source": "recent_history"}

    if not fs_target:
        try:
            from core.task_store import get_latest_structured_fs_target

            latest_fs_target = get_latest_structured_fs_target()
        except Exception:
            latest_fs_target = None
        fs_target = _normalize_protocol_fs_target(latest_fs_target, default_option=default_option)

    if fs_target:
        ctx["fs_target"] = fs_target
        ctx["path"] = str(ctx.get("path") or fs_target.get("path") or "").strip()
        context_data = _merge_context_dict(context_data, {"fs_target": fs_target})

    if context_data:
        ctx["context_data"] = context_data
    if user_input and "last_user_input" not in ctx:
        ctx["last_user_input"] = user_input
    return ctx


def _remember_protocol_target(name: str, ctx: dict, result: dict) -> None:
    if name not in _PROTOCOL_CONTEXT_SKILLS:
        return
    if not isinstance(ctx, dict) or not isinstance(result, dict) or not result.get("success"):
        return

    default_option = _PROTOCOL_DEFAULT_OPTIONS.get(name, "inspect")
    current_target = ctx.get("fs_target") if isinstance(ctx.get("fs_target"), dict) else {}
    path = str(
        current_target.get("path")
        or ctx.get("path")
        or ctx.get("file_path")
        or ctx.get("source")
        or ctx.get("target")
        or ""
    ).strip()
    if not path or path.startswith(("http://", "https://")):
        return

    fs_target = {"path": path, "option": default_option, "source": "tool_runtime"}
    ctx["fs_target"] = fs_target
    ctx["path"] = path
    context_data = ctx.get("context_data") if isinstance(ctx.get("context_data"), dict) else {}
    ctx["context_data"] = _merge_context_dict(context_data, {"fs_target": fs_target})


def _is_allowed_user_target(target) -> bool:
    if not target:
        return False
    try:
        target_path = _Path(target).resolve()
    except Exception:
        return False
    target_str = str(target_path).replace("\\", "/")
    protected_prefixes = (
        "C:/Windows",
        "C:/Program Files",
        "C:/Program Files (x86)",
        "C:/ProgramData",
    )
    return not any(target_str.startswith(prefix) for prefix in protected_prefixes)


def _is_system_protected_target(target) -> bool:
    if not target:
        return True
    target_str = str(target).replace("\\", "/")
    protected_prefixes = (
        "C:/Windows",
        "C:/Program Files",
        "C:/Program Files (x86)",
        "C:/ProgramData",
    )
    return any(target_str.startswith(prefix) for prefix in protected_prefixes)


def _is_novacore_protected_write_target(target) -> bool:
    if not target:
        return True
    try:
        root = (_Path(__file__).resolve().parent.parent).resolve()
        target_path = _Path(target).resolve()
    except Exception:
        return True

    try:
        rel = target_path.relative_to(root)
    except Exception:
        return False

    protected_roots = {
        _Path("brain"),
        _Path("core"),
        _Path("routes"),
        _Path("shell"),
        _Path("static/js"),
        _Path("static/css"),
        _Path("configs"),
    }
    protected_files = {
        _Path("agent_final.py"),
        _Path("output.html"),
        _Path("start_nova.bat"),
        _Path("AGENTS.md"),
        _Path("CLAUDE.md"),
    }
    if rel in protected_files:
        return True
    return any(rel == p or p in rel.parents for p in protected_roots)


def _is_allowed_read_target(target) -> bool:
    if not target:
        return False
    try:
        return _Path(target).exists() and not _is_system_protected_target(target)
    except Exception:
        return False


def _is_allowed_write_target(target) -> bool:
    if not target:
        return False
    return not _is_system_protected_target(target) and not _is_novacore_protected_write_target(target)


def init(*, get_all_skills=None, debug_write=None,
         l2_search_relevant=None, load_l3_long_term=None, find_relevant_knowledge=None):
    global _get_all_skills, _debug_write
    global _l2_search_relevant, _load_l3_long_term, _find_relevant_knowledge
    if get_all_skills:
        _get_all_skills = get_all_skills
    if debug_write:
        _debug_write = debug_write
    if l2_search_relevant:
        _l2_search_relevant = l2_search_relevant
    if load_l3_long_term:
        _load_l3_long_term = load_l3_long_term
    if find_relevant_knowledge:
        _find_relevant_knowledge = find_relevant_knowledge


def build_tools_list() -> list[dict]:
    """从 get_all_skills() 构建 OpenAI tools 定义列表"""
    tools = []
    try:
        all_skills = _get_all_skills()
    except Exception:
        return tools

    for name, info in all_skills.items():
        if not info or not callable(info.get("execute")):
            continue
        desc = str(info.get("description") or info.get("name") or name).strip()
        if not desc:
            desc = name
        # 优先使用 skill JSON 里定义的 parameters，否则 fallback 到 user_input only
        meta_params = info.get("parameters")
        if isinstance(meta_params, dict) and meta_params.get("properties"):
            params = meta_params
        else:
            params = {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "Original user request.",
                    }
                },
                "required": ["user_input"],
            }
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": params,
            },
        })
    # 加入 ask_user 工具（agent 决策暂停点）
    tools.append(get_ask_user_tool_def())
    return tools


# ── 记忆工具（CoD）——从 configs/tools.json 加载 ──

_MEMORY_TOOLS = {"recall_memory", "query_knowledge", "web_search", "self_fix", "read_file", "list_files", "discover_tools", "sense_environment"}

_tools_error_count = 0  # 连续报错计数

def _load_cod_tool_defs() -> list:
    """从配置文件加载工具定义，连续 3 次报错自动回滚到 .bak"""
    global _tools_error_count
    p = _CONFIGS_DIR / "tools.json"
    bak = _CONFIGS_DIR / "tools.json.bak"
    try:
        cfg = json.loads(p.read_text("utf-8"))
        tools = cfg.get("cod_tools", [])
        if tools:
            _tools_error_count = 0
            return [{"type": "function", "function": t} for t in tools]
    except Exception:
        _tools_error_count += 1
        if _tools_error_count >= 3 and bak.exists():
            try:
                import shutil
                shutil.copy2(bak, p)
                _tools_error_count = 0
                cfg = json.loads(p.read_text("utf-8"))
                tools = cfg.get("cod_tools", [])
                if tools:
                    return [{"type": "function", "function": t} for t in tools]
            except Exception:
                pass
    # fallback：硬编码默认值
    return _COD_TOOL_DEFS_DEFAULT

_COD_TOOL_DEFS_DEFAULT = [
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Retrieve prior dialogue or stored experience when earlier context is required for a correct reply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Memory retrieval query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge",
            "description": "Query learned knowledge when stored facts, concepts, or prior conclusions are needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Knowledge topic to retrieve."}
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web when current or external information is required and local context is insufficient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Concise search query."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "self_fix",
            "description": "Apply a targeted fix when the issue and affected file are already clear. Use for safe local repairs, not core-engine rewrites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Target file path to update."},
                    "problem": {"type": "string", "description": "Expected fix or observed deviation."}
                },
                "required": ["file_path", "problem"],
            },
        },
    },
]

# 兼容：其他模块 import _COD_TOOL_DEFS 时拿到动态加载版
_COD_TOOL_DEFS = _load_cod_tool_defs()


def build_tools_list_cod() -> list[dict]:
    """构建 CoD 模式的 tools 列表：真实技能工具 + CoD 工具 + ask_user，discover_tools 仅作兜底"""
    # ① 真实技能工具（首轮直接暴露，不需要先 discover）
    tools = []
    try:
        all_skills = _get_all_skills()
    except Exception:
        all_skills = {}
    for name, info in all_skills.items():
        if not info or not callable(info.get("execute")):
            continue
        desc = str(info.get("description") or info.get("name") or name).strip()
        if not desc:
            desc = name
        meta_params = info.get("parameters")
        if isinstance(meta_params, dict) and meta_params.get("properties"):
            params = meta_params
        else:
            params = {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "Original user request.",
                    }
                },
                "required": ["user_input"],
            }
        tools.append({
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": params},
        })

    # ② CoD 工具（记忆 / 知识 / 搜索 / 自修复 / 文件读写）
    tools.extend(_load_cod_tool_defs())

    # ③ ask_user
    tools.append(get_ask_user_tool_def())

    # ④ sense_environment
    tools.append({
        "type": "function",
        "function": {
            "name": "sense_environment",
            "description": "Inspect the current computer environment before desktop actions or when the current state is unclear.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detail_level": {"type": "string", "description": "Environment detail level.", "enum": ["basic", "full"]}
                },
                "required": [],
            },
        },
    })

    # ⑤ write_file
    tools.append({
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a workspace file with complete content. Use when the target path and final file content are already determined.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Target file path. Can be workspace-relative or a resolved Desktop/Documents/Downloads path."},
                    "content": {"type": "string", "description": "Complete file content to write."},
                    "description": {"type": "string", "description": "Short summary of the intended file change."}
                },
                "required": ["file_path", "content"],
            },
        },
    })

    # ⑥ discover_tools 降级为兜底（技能注册表为空时仍可用）
    tools.append({
        "type": "function",
        "function": {
            "name": "discover_tools",
            "description": "Fallback tool for discovering additional registered capabilities when the visible toolset is insufficient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "description": "Current goal that needs a capability lookup."}
                },
                "required": ["intent"],
            },
        },
    })

    return tools


def execute_tool_call(name: str, arguments: dict, context: dict = None) -> dict:
    """\u6267\u884c tool_call\uff0c\u6620\u5c04\u5230 core/executor.py:execute() \u6216\u8bb0\u5fc6\u5de5\u5177"""
    # ask_user: 暂停执行，等用户选择
    if name == "ask_user":
        return _execute_ask_user(arguments)
    # CoD 记忆工具走独立路径
    if name in _MEMORY_TOOLS:
        return _execute_memory_tool(name, arguments)
    user_input = str(arguments.get("user_input") or "").strip()
    skill_route = {"skill": name}
    # 把 LLM 传的额外参数（如 city、topic）合并到 context
    ctx = context if isinstance(context, dict) else {}
    for k, v in arguments.items():
        if k != "user_input" and v:
            ctx[k] = v
    ctx = _apply_protocol_context(name, ctx, user_input)
    _debug_write("tool_call_execute", {"name": name, "user_input": user_input[:100], "extra_args": {k: v for k, v in arguments.items() if k != "user_input"}})
    result = _execute(skill_route, user_input, ctx)
    _remember_protocol_target(name, ctx, result)
    _debug_write("tool_call_result", {
        "name": name, "success": result.get("success"),
        "response_len": len(result.get("response", "")),
    })
    return result


# ── 记忆工具执行 ──

def _format_recall(l2_results, l3_events):
    lines = []
    if l2_results:
        lines.append("\u3010\u5bf9\u8bdd\u8bb0\u5fc6\u3011")
        for m in l2_results:
            text = str(m.get("user_text", ""))[:100]
            imp = m.get("importance", 0)
            marker = "\u2605" if imp >= 0.7 else "\u00b7"
            lines.append(f"{marker} {text}")
    if l3_events:
        lines.append("\u3010\u5171\u540c\u7ecf\u5386\u3011")
        for e in l3_events:
            # load_l3_long_term \u8fd4\u56de\u7684\u662f\u5b57\u7b26\u4e32\u5217\u8868\uff08event_text \u7684\u7ed3\u679c\uff09
            if isinstance(e, str):
                summary = e[:100]
            else:
                summary = str(e.get("summary") or e.get("event") or "")[:100]
            if summary:
                lines.append(f"\u00b7 {summary}")
    return "\n".join(lines) if lines else "\u6ca1\u6709\u627e\u5230\u76f8\u5173\u8bb0\u5fc6\u3002"


def _execute_web_search(query: str) -> dict:
    """执行联网搜索，返回结构化结果给 LLM"""
    query = _normalize_time_sensitive_search_query(query)
    _debug_write("web_search_execute", {"query": query})
    try:
        from core.l8_learn import search_web_results
        results = search_web_results(query, max_results=5, timeout_sec=8)
        if not results:
            return {"success": False, "error": "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c"}

        lines = ["\u3010\u8054\u7f51\u641c\u7d22\u7ed3\u679c\u3011"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if link:
                lines.append(f"   \u6765\u6e90: {link}")

        # 如果 Tavily 返回了 AI answer，附上
        if results[0].get("tavily_answer"):
            lines.append(f"\nAI\u6458\u8981: {results[0]['tavily_answer']}")

        resp = "\n".join(lines)
        _debug_write("web_search_result", {"query": query, "count": len(results)})
        return {"success": True, "response": resp}
    except Exception as e:
        _debug_write("web_search_error", {"query": query, "error": str(e)})
        return {"success": False, "error": f"\u641c\u7d22\u5931\u8d25: {e}"}


def _normalize_time_sensitive_search_query(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return text
    lowered = text.lower()
    latest_markers = ("最新", "最近", "current", "latest", "today", "this year", "今年")
    history_markers = ("历史", "回顾", "复盘", "盘点", "年度", "往年", "去年", "previous", "past")
    if not any(marker in lowered for marker in latest_markers):
        return text
    if any(marker in lowered for marker in history_markers):
        return text
    current_year = time.localtime().tm_year
    years = [int(m.group(0)) for m in _re.finditer(r"20\d{2}", text)]
    if years and max(years) < current_year:
        return _re.sub(r"20\d{2}", str(current_year), text, count=1)
    if not years and any(marker in lowered for marker in latest_markers):
        prefix = f"{current_year}年" if _re.search(r"[\u4e00-\u9fff]", text) else f"{current_year} "
        return f"{prefix}{text}"
    return text


# ── self_fix：对话中即时自我修复 ──

# 安全白名单：允许读写的目录
_SELF_FIX_ALLOWED = ["static/", "configs/", "core/skills/", "memory_db/"]

def _execute_self_fix(arguments: dict) -> dict:
    """读文件 → LLM 生成最小修复 → 写回"""
    from pathlib import Path
    import traceback

    file_path = str(arguments.get("file_path", "")).strip()
    # 兼容 LLM 可能传的别名参数
    problem = str(arguments.get("problem", "") or arguments.get("fix_description", "") or "").strip()

    # 路径标准化：反斜杠→正斜杠，去掉 ./ 前缀
    file_path = file_path.replace("\\", "/").lstrip("./")

    _debug_write("self_fix_call", {"file_path": file_path, "problem": problem})

    if not file_path or not problem:
        return {"success": False, "response":
                f"缺少文件路径或问题描述。可修改的目录：{', '.join(_SELF_FIX_ALLOWED)}"}

    # 路径纠错：常见错误路径映射到正确路径
    _PATH_FIXES = {
        "frontend/css/": "static/css/",
        "frontend/js/": "static/js/",
        "css/": "static/css/",
        "js/": "static/js/",
    }
    for wrong, right in _PATH_FIXES.items():
        if file_path.startswith(wrong):
            file_path = file_path.replace(wrong, right, 1)
            break

    # 安全检查：只能改白名单内的文件
    if not any(file_path.startswith(prefix) for prefix in _SELF_FIX_ALLOWED):
        return {"success": False, "response":
                f"安全限制：只能修改 {', '.join(_SELF_FIX_ALLOWED)} 下的文件"}

    root = Path(__file__).resolve().parent.parent
    target = root / file_path
    if not target.exists():
        # 尝试模糊匹配：搜索文件名
        fname = Path(file_path).name
        candidates = []
        for prefix in _SELF_FIX_ALLOWED:
            prefix_dir = root / prefix
            if prefix_dir.exists():
                candidates.extend(prefix_dir.rglob(fname))
        if len(candidates) == 1:
            target = candidates[0]
            file_path = str(target.relative_to(root)).replace("\\", "/")
            _debug_write("self_fix_path_corrected", {"corrected_to": file_path})
        elif candidates:
            options = [str(c.relative_to(root)).replace("\\", "/") for c in candidates[:5]]
            return {"success": False, "response":
                    f"文件不存在: {file_path}\n找到类似文件：{', '.join(options)}"}
        else:
            return {"success": False, "response": f"文件不存在: {file_path}"}

    # 读取当前内容
    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "response": f"读取失败: {e}"}

    content_lines = content.split("\n")
    is_large_file = len(content_lines) > 300

    # 用 LLM 生成修复（流式，避免阻塞超时）
    try:
        from brain import LLM_CONFIG
        from brain import llm_call_stream
        cfg = dict(LLM_CONFIG)

        if is_large_file:
            # ── 大文件模式：补丁式修复 ──
            # 只发送前50行 + 后50行 + 问题相关的上下文
            preview_lines = []
            preview_lines.append(f"=== 文件前50行 ===")
            preview_lines.extend(f"{i+1}: {l}" for i, l in enumerate(content_lines[:50]))
            preview_lines.append(f"\n=== 文件后50行（第{len(content_lines)-49}行起）===")
            preview_lines.extend(f"{len(content_lines)-49+i}: {l}" for i, l in enumerate(content_lines[-50:]))
            preview = "\n".join(preview_lines)

            prompt = (
                f"你是代码修复专家。文件很大（{len(content_lines)}行），请用补丁方式修复。\n\n"
                f"文件: {file_path}\n"
                f"问题: {problem}\n\n"
                f"文件概览:\n{preview}\n\n"
                f"请输出修复指令，严格使用以下格式（可以有多组）：\n\n"
                f"===APPEND===\n"
                f"（要追加到文件末尾的新代码）\n"
                f"===END===\n\n"
                f"或者：\n\n"
                f"===FIND===\n"
                f"（要替换的原始代码片段，必须能在文件中精确匹配）\n"
                f"===REPLACE===\n"
                f"（替换后的新代码）\n"
                f"===END===\n\n"
                f"要求：\n"
                f"1. 只修复描述的问题\n"
                f"2. 不要加解释，只输出修复指令\n"
                f"3. 如果是添加新样式/功能，用 APPEND\n"
                f"4. 如果是修改已有代码，用 FIND/REPLACE，FIND 内容必须精确匹配原文"
            )
        else:
            # ── 小文件模式：全量重写 ──
            prompt = (
                f"你是代码修复专家。请修复以下文件中的问题。\n\n"
                f"文件: {file_path}\n"
                f"问题: {problem}\n\n"
                f"当前内容:\n```\n{content}\n```\n\n"
                f"要求:\n"
                f"1. 只修复描述的问题，不做其他改动\n"
                f"2. 直接输出修复后的完整文件内容\n"
                f"3. 不要加解释，不要加 markdown 标记\n"
                f"4. 保持代码可运行"
            )

        chunks = []
        for token in llm_call_stream(
            cfg, [{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=4096, timeout=60
        ):
            if isinstance(token, str):
                chunks.append(token)
        llm_output = "".join(chunks).strip()

        # 去掉可能的 markdown 包裹
        if llm_output.startswith("```"):
            lines = llm_output.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            llm_output = "\n".join(lines)

    except Exception as e:
        return {"success": False, "response": f"LLM 调用失败: {type(e).__name__}: {e}"}

    if not llm_output or len(llm_output) < 5:
        return {"success": False, "response": "LLM 返回为空，修复失败"}

    # ── 应用修复 ──
    if is_large_file:
        new_content = content
        applied = []

        # 解析 APPEND 指令
        import re
        for m in re.finditer(r'===APPEND===\s*\n(.*?)\n===END===', llm_output, re.DOTALL):
            append_code = m.group(1).strip()
            if append_code:
                new_content = new_content.rstrip() + "\n\n" + append_code + "\n"
                applied.append(f"追加 {len(append_code)} 字符")

        # 解析 FIND/REPLACE 指令
        for m in re.finditer(r'===FIND===\s*\n(.*?)\n===REPLACE===\s*\n(.*?)\n===END===', llm_output, re.DOTALL):
            find_str = m.group(1).strip()
            replace_str = m.group(2).strip()
            if find_str and find_str in new_content:
                new_content = new_content.replace(find_str, replace_str, 1)
                applied.append(f"替换 '{find_str[:30]}...'")
            elif find_str:
                applied.append(f"未匹配 '{find_str[:30]}...'（跳过）")

        if not applied:
            return {"success": False, "response":
                    f"LLM 返回了修复指令但无法应用。原始输出:\n{llm_output[:500]}"}

        _debug_write("self_fix_patch", {"applied": applied})
    else:
        new_content = llm_output

        # 安全检查：新内容不能比原内容短太多
        if len(new_content) < len(content) * 0.5:
            return {"success": False, "response": "修复结果异常（内容大幅缩短），已拒绝"}

    # 备份 + 写入
    try:
        backup_path = target.with_suffix(target.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")
        target.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "response": f"写入失败: {e}"}

    _debug_write("self_fix", {"file": file_path, "problem": problem,
                              "old_len": len(content), "new_len": len(new_content)})
    return {"success": True, "response":
            f"已修复 {file_path}（备份: {backup_path.name}），刷新页面生效。"}


# ── read_file：让 Nova 先看再修 ──

def _execute_read_file(arguments: dict) -> dict:
    """读取白名单内的文件内容，供 Nova 诊断问题"""
    file_path = str(arguments.get("file_path", "")).strip()
    file_path = file_path.replace("\\", "/").lstrip("./")

    # 路径纠错
    _PATH_FIXES = {
        "frontend/css/": "static/css/",
        "frontend/js/": "static/js/",
        "css/": "static/css/",
        "js/": "static/js/",
    }
    for wrong, right in _PATH_FIXES.items():
        if file_path.startswith(wrong):
            file_path = file_path.replace(wrong, right, 1)
            break

    if not file_path:
        return {"success": False, "response":
                f"请提供文件路径。可读取的目录：{', '.join(_SELF_FIX_ALLOWED)}"}

    target = _resolve_user_file_target(file_path)
    if not target:
        return {"success": False, "response":
                f"请提供文件路径。可读取的目录：{', '.join(_SELF_FIX_ALLOWED)}"}

    # 模糊匹配
    if not target.exists():
        root = _Path(__file__).resolve().parent.parent
        fname = _Path(file_path).name
        candidates = []
        for prefix in _SELF_FIX_ALLOWED:
            prefix_dir = root / prefix
            if prefix_dir.exists():
                candidates.extend(prefix_dir.rglob(fname))
        if len(candidates) == 1:
            target = candidates[0]
            file_path = str(target.relative_to(root)).replace("\\", "/")
        elif candidates:
            options = [str(c.relative_to(root)).replace("\\", "/") for c in candidates[:5]]
            return {"success": False, "response":
                    f"文件不存在: {file_path}\n找到类似文件：{', '.join(options)}"}
        else:
            return {"success": False, "response": f"文件不存在: {file_path}"}

    if not _is_allowed_user_target(target):
        return {"success": False, "response":
                "安全限制：只能读取工作区、桌面、文档或下载目录中的文件"}

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "response": f"读取失败: {e}"}

    # 截断超长文件，只返回前 200 行
    lines = content.split("\n")
    total = len(lines)
    if total > 200:
        content = "\n".join(lines[:200])
        content += f"\n\n... (共 {total} 行，已截断前 200 行)"

    _debug_write("read_file", {"file": file_path, "lines": total})
    return {"success": True, "response":
            f"【{file_path}】({total} 行)\n{content}"}


# ── list_files：让 Nova 知道有哪些文件 ──

def _execute_list_files(arguments: dict) -> dict:
    """列出白名单目录下的文件，供 Nova 定位目标"""
    from pathlib import Path

    directory = str(arguments.get("directory", "")).strip()
    directory = directory.replace("\\", "/").lstrip("./").rstrip("/")

    # 默认列出所有白名单目录的顶层
    if not directory:
        root = Path(__file__).resolve().parent.parent
        lines = ["可访问的目录："]
        for prefix in _SELF_FIX_ALLOWED:
            d = root / prefix
            if d.exists():
                files = sorted([f.name for f in d.iterdir() if f.is_file()])
                dirs = sorted([f.name + "/" for f in d.iterdir() if f.is_dir()])
                lines.append(f"\n📁 {prefix}")
                for dn in dirs:
                    lines.append(f"  📁 {dn}")
                for fn in files:
                    lines.append(f"  📄 {fn}")
        return {"success": True, "response": "\n".join(lines)}

    if not any(directory.startswith(prefix.rstrip("/")) for prefix in _SELF_FIX_ALLOWED):
        return {"success": False, "response":
                f"安全限制：只能浏览 {', '.join(_SELF_FIX_ALLOWED)} 下的目录"}

    root = Path(__file__).resolve().parent.parent
    target = root / directory
    if not target.exists() or not target.is_dir():
        return {"success": False, "response": f"目录不存在: {directory}"}

    files = sorted([f.name for f in target.iterdir() if f.is_file()])
    dirs = sorted([f.name + "/" for f in target.iterdir() if f.is_dir()])
    lines = [f"📁 {directory}/"]
    for dn in dirs:
        lines.append(f"  📁 {dn}")
    for fn in files:
        lines.append(f"  📄 {fn}")
    return {"success": True, "response": "\n".join(lines)}


def _execute_list_files_v2(arguments: dict) -> dict:
    """List files from the workspace or user-safe folders so Nova can inspect targets."""
    from pathlib import Path

    raw_directory = str(arguments.get("directory", "")).strip()
    normalized_directory = _normalize_user_special_path(raw_directory).replace("\\", "/").strip().rstrip("/")
    directory = normalized_directory.lstrip("./")

    if not directory:
        root = Path(__file__).resolve().parent.parent
        lines = ["可访问的目录："]
        for prefix in _SELF_FIX_ALLOWED:
            d = root / prefix
            if d.exists():
                files = sorted([f.name for f in d.iterdir() if f.is_file()])
                dirs = sorted([f.name + "/" for f in d.iterdir() if f.is_dir()])
                lines.append(f"\n📁 {prefix}")
                for dn in dirs:
                    lines.append(f"  📁 {dn}")
                for fn in files:
                    lines.append(f"  📄 {fn}")
        for special_name in ("Desktop", "Documents", "Downloads"):
            special_dir = Path.home() / special_name
            if special_dir.exists():
                lines.append(f"\n📁 {special_dir}")
        return {"success": True, "response": "\n".join(lines)}

    root = Path(__file__).resolve().parent.parent
    target = _resolve_user_file_target(directory)
    if target is None:
        target = root / directory

    if not _is_allowed_user_target(target):
        return {"success": False, "response": "安全限制：只能浏览工作区、桌面、文档或下载目录中的文件夹"}

    if not target.exists() or not target.is_dir():
        return {"success": False, "response": f"目录不存在: {raw_directory or directory}"}

    files = sorted([f.name for f in target.iterdir() if f.is_file()])
    dirs = sorted([f.name + "/" for f in target.iterdir() if f.is_dir()])
    display_dir = str(target).replace("\\", "/")
    lines = [f"📁 {display_dir}/"]
    for dn in dirs:
        lines.append(f"  📁 {dn}")
    for fn in files:
        lines.append(f"  📄 {fn}")
    return {"success": True, "response": "\n".join(lines)}


def _execute_list_files_v3(arguments: dict) -> dict:
    """List files from the full workspace root or user-safe folders."""
    from pathlib import Path

    raw_directory = str(arguments.get("directory", "")).strip()
    normalized_directory = _normalize_user_special_path(raw_directory).replace("\\", "/").strip().rstrip("/")
    directory = normalized_directory.lstrip("./")
    root = Path(__file__).resolve().parent.parent

    if not directory:
        lines = ["可访问的目录：", f"\n📁 {root}"]
        root_dirs = sorted([f.name + "/" for f in root.iterdir() if f.is_dir()])
        root_files = sorted([f.name for f in root.iterdir() if f.is_file()])
        for dn in root_dirs:
            lines.append(f"  📁 {dn}")
        for fn in root_files:
            lines.append(f"  📄 {fn}")
        for special_name in ("Desktop", "Documents", "Downloads"):
            special_dir = Path.home() / special_name
            if special_dir.exists():
                lines.append(f"\n📁 {special_dir}")
        return {"success": True, "response": "\n".join(lines)}

    target = _resolve_user_file_target(directory)
    if target is None:
        target = root / directory

    if not _is_allowed_user_target(target):
        return {"success": False, "response": "安全限制：只能浏览工作区、桌面、文档或下载目录中的文件夹"}

    if not target.exists() or not target.is_dir():
        return {"success": False, "response": f"目录不存在: {raw_directory or directory}"}

    files = sorted([f.name for f in target.iterdir() if f.is_file()])
    dirs = sorted([f.name + "/" for f in target.iterdir() if f.is_dir()])
    display_dir = str(target).replace("\\", "/")
    lines = [f"📁 {display_dir}/"]
    for dn in dirs:
        lines.append(f"  📁 {dn}")
    for fn in files:
        lines.append(f"  📄 {fn}")
    return {"success": True, "response": "\n".join(lines)}


def _execute_discover_tools(arguments: dict) -> dict:
    """返回当前可用的技能工具列表，供 LLM 选择后发起第二轮 tool_call"""
    intent = str(arguments.get("intent", "")).strip()
    _debug_write("discover_tools", {"intent": intent})
    try:
        all_skills = _get_all_skills()
    except Exception:
        return {"success": False, "error": "技能系统未就绪"}
    if not all_skills:
        return {"success": True, "response": "当前没有已注册的技能工具。"}

    lines = ["以下是当前可用的技能工具："]
    for name, info in all_skills.items():
        if not info or not callable(info.get("execute")):
            continue
        desc = str(info.get("description") or info.get("name") or name).strip()
        lines.append(f"- {name}：{desc}")
    lines.append("\n请根据用户意图选择合适的工具，用 tool_call 调用它。")
    return {"success": True, "response": "\n".join(lines)}


def _execute_sense_environment(arguments: dict) -> dict:
    """统一环境感知：汇总已有的窗口、屏幕、应用、浏览器感知能力"""
    detail_level = str(arguments.get("detail_level", "basic")).strip()
    if detail_level in {"high", "full", "detailed", "detail"}:
        detail_level = "full"
    elif detail_level in {"low", "normal", "default", "basic"}:
        detail_level = "basic"
    else:
        detail_level = "basic"
    _debug_write("sense_environment", {"detail_level": detail_level})

    lines = []

    # 1. 活跃窗口
    active_title = ""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active and getattr(active, "title", None):
            active_title = str(active.title).strip()
    except Exception:
        pass
    lines.append(f"当前活跃窗口：{active_title or '未知'}")

    # 2. 窗口类型判断
    _browser_hints = ["chrome", "edge", "firefox", "brave", "opera", "safari", "浏览器"]
    _is_browser = any(h in active_title.lower() for h in _browser_hints) if active_title else False
    lines.append(f"窗口类型：{'浏览器' if _is_browser else '桌面应用'}")

    # 3. 已打开窗口列表
    try:
        import pygetwindow as gw
        all_wins = [w.title for w in gw.getAllWindows() if w.title.strip()]
        lines.append(f"已打开窗口（{len(all_wins)}个）：")
        for w in all_wins[:15]:
            lines.append(f"  - {w}")
        if len(all_wins) > 15:
            lines.append(f"  ...还有 {len(all_wins) - 15} 个窗口")
    except Exception:
        lines.append("窗口列表：获取失败")

    # 4. full 模式：屏幕信息
    if detail_level == "full":
        try:
            import pyautogui
            screen_size = pyautogui.size()
            mouse_pos = pyautogui.position()
            lines.append(f"屏幕分辨率：{screen_size.width}x{screen_size.height}")
            lines.append(f"鼠标位置：({mouse_pos.x}, {mouse_pos.y})")
        except Exception:
            pass

        # 5. full 模式：如果是浏览器，尝试获取当前页面信息
        if _is_browser:
            try:
                from core.vision import get_vision_context
                vc = get_vision_context()
                if vc.get("description"):
                    lines.append(f"视觉感知：{vc['description']}")
            except Exception:
                pass

    return {"success": True, "response": "\n".join(lines)}


def _execute_write_file(arguments: dict) -> dict:
    return _execute_write_file_protocol(arguments)
    """写入文件到工作区或用户常用目录。"""
    file_path = str(
        arguments.get("file_path", "")
        or arguments.get("path", "")
        or arguments.get("target", "")
        or arguments.get("filename", "")
        or ""
    ).strip()
    content = str(arguments.get("content", "") or "")
    description = str(arguments.get("description", "") or "").strip()
    if not file_path:
        return {"success": False, "error": "缺少 file_path"}
    if not content:
        return {"success": False, "error": "缺少 content"}

    target = _resolve_user_file_target(file_path)
    if not target:
        return {"success": False, "error": "缺少 file_path"}
    if not _is_allowed_user_target(target):
        return {"success": False, "error": "安全限制：只能写入工作区、桌面、文档或下载目录"}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"写入失败: {e}"}

    summary = description or f"已写入文件：{target}"
    return {
        "success": True,
        "response": f"{summary}\n路径：{target}",
        "meta": {
            "action": {
                "action_kind": "write_file",
                "target_kind": "file",
                "outcome": "written",
                "display_hint": f"已写入文件：{target.name}",
            },
            "verification": {
                "verified": target.exists(),
                "observed_state": "file_written" if target.exists() else "unknown",
            },
        },
    }


def _execute_write_file_v2(arguments: dict) -> dict:
    return _execute_write_file_protocol(arguments)
    """Write files broadly, but keep Windows system dirs and Nova core files protected."""
    file_path = str(
        arguments.get("file_path", "")
        or arguments.get("path", "")
        or arguments.get("target", "")
        or arguments.get("filename", "")
        or ""
    ).strip()
    content = str(arguments.get("content", "") or "")
    description = str(arguments.get("description", "") or "").strip()
    if not file_path:
        return {"success": False, "error": "缺少 file_path"}
    if not content:
        return {"success": False, "error": "缺少 content"}

    target = _resolve_user_file_target(file_path)
    if not target:
        return {"success": False, "error": "缺少 file_path"}
    if not _is_allowed_user_target(target):
        return {"success": False, "error": "系统目录不可写入"}
    if _is_novacore_protected_write_target(target):
        return {"success": False, "error": "Nova 核心文件受保护，不能直接写入"}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"写入失败: {e}"}

    summary = description or f"已写入文件：{target}"
    return {
        "success": True,
        "response": f"{summary}\n路径：{target}",
        "meta": {
            "action": {
                "action_kind": "write_file",
                "target_kind": "file",
                "outcome": "written",
                "display_hint": f"已写入文件：{target.name}",
            },
            "verification": {
                "verified": target.exists(),
                "observed_state": "file_written" if target.exists() else "unknown",
            },
        },
    }


def _format_knowledge(hits):
    if not hits:
        return "\u77e5\u8bc6\u5e93\u4e2d\u6ca1\u6709\u76f8\u5173\u5185\u5bb9\u3002"
    lines = ["\u3010\u5df2\u5b66\u77e5\u8bc6\u3011"]
    for h in hits:
        title = str(h.get("query") or h.get("name") or "").strip()
        summary = str(h.get("summary") or "").strip()
        if summary:
            lines.append(f"- {title}\uff1a{summary}")
    return "\n".join(lines)


def _execute_memory_tool(name: str, arguments: dict) -> dict:
    _debug_write("memory_tool_execute", {"name": name, "args": arguments})
    if name == "recall_memory":
        query = str(arguments.get("query", "")).strip()
        l2 = _l2_search_relevant(query, limit=5)
        l3 = _load_l3_long_term(limit=5)
        resp = _format_recall(l2, l3)
        _debug_write("memory_tool_result", {"name": name, "l2_hits": len(l2), "l3_hits": len(l3)})
        return {"success": True, "response": resp}
    elif name == "query_knowledge":
        topic = str(arguments.get("topic", "")).strip()
        hits = _find_relevant_knowledge(topic, limit=3, touch=True)
        resp = _format_knowledge(hits)
        _debug_write("memory_tool_result", {"name": name, "hits": len(hits)})
        return {"success": True, "response": resp}
    elif name == "web_search":
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"success": False, "error": "\u641c\u7d22\u5173\u952e\u8bcd\u4e0d\u80fd\u4e3a\u7a7a"}
        return _execute_web_search(query)
    elif name == "self_fix":
        return _execute_self_fix(arguments)
    elif name == "read_file":
        return _execute_read_file(arguments)
    elif name == "list_files":
        return _execute_list_files_v3(arguments)
    elif name == "discover_tools":
        return _execute_discover_tools(arguments)
    elif name == "sense_environment":
        return _execute_sense_environment(arguments)
    return {"success": False, "error": f"\u672a\u77e5\u8bb0\u5fc6\u5de5\u5177: {name}"}


# ── ask_user 工具 ──

def _execute_ask_user(arguments: dict) -> dict:
    """暂停 agent 循环，等待用户选择。阻塞直到用户回答或超时。"""
    global _ask_user_pending, _ask_user_answer
    question = str(arguments.get("question", "")).strip()
    options = arguments.get("options", [])
    if not question:
        return {"success": False, "response": "ask_user: 缺少 question 参数"}
    if not isinstance(options, list) or len(options) < 2:
        return {"success": False, "response": "ask_user: options 至少需要 2 个选项"}

    question_id = f"ask_{int(time.time()*1000)}"

    with _ask_user_lock:
        _ask_user_pending = {"question": question, "options": options, "id": question_id}
        _ask_user_answer = None

    _debug_write("ask_user_waiting", {"id": question_id, "question": question, "options": options})

    # 阻塞等待用户回答，最多 120 秒
    timeout = 120
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        with _ask_user_lock:
            if _ask_user_answer is not None:
                answer = _ask_user_answer
                _ask_user_pending = None
                _ask_user_answer = None
                _debug_write("ask_user_answered", {"id": question_id, "answer": answer})
                return {"success": True, "response": f"用户选择了：{answer}"}
        time.sleep(0.3)

    # 超时
    with _ask_user_lock:
        _ask_user_pending = None
        _ask_user_answer = None
    _debug_write("ask_user_timeout", {"id": question_id})
    return {"success": False, "response": "用户未在规定时间内回答，任务暂停。"}


def get_ask_user_tool_def() -> dict:
    """返回 ask_user 的 OpenAI function calling 格式定义"""
    return {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "暂停当前任务，向用户提问并等待选择。用于需要用户决策的场景（如选题、确认方案、选择风格等）。用户回答后任务继续。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "向用户提出的问题"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "给用户的选项列表，至少 2 个，用户会从中选一个"
                    }
                },
                "required": ["question", "options"]
            }
        }
    }
