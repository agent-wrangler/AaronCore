"""Tool schema builders extracted from the legacy tool adapter hotspot."""

import json
import shutil
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[2]
CONFIGS_DIR = ENGINE_DIR / "configs"

_tools_error_count = 0


def normalize_exposure_scope_values(scope) -> set[str]:
    if isinstance(scope, (list, tuple, set)):
        raw_values = scope
    else:
        raw_values = [scope]
    normalized = {
        str(value or "").strip().lower()
        for value in raw_values
        if str(value or "").strip()
    }
    return normalized or {"tool_call"}


def skill_matches_exposure_scope(info: dict | None, scope) -> bool:
    info = info if isinstance(info, dict) else {}
    allowed_scopes = normalize_exposure_scope_values(scope)
    entry_scope = str(info.get("exposure_scope") or "tool_call").strip().lower() or "tool_call"
    return entry_scope in allowed_scopes


def get_exposed_skill_map(get_all_skills, get_exposed_skills, scope) -> dict:
    if callable(get_exposed_skills):
        try:
            skills = get_exposed_skills(scope=scope)
            if isinstance(skills, dict):
                return skills
        except Exception:
            pass
    if not callable(get_all_skills):
        return {}
    try:
        all_skills = get_all_skills()
    except Exception:
        return {}
    return {
        name: info
        for name, info in (all_skills or {}).items()
        if skill_matches_exposure_scope(info, scope)
    }


def build_registered_skill_tool_defs(get_all_skills, get_exposed_skills, scope) -> list[dict]:
    tools = []
    for name, info in get_exposed_skill_map(get_all_skills, get_exposed_skills, scope).items():
        if not info or not callable(info.get("execute")):
            continue
        desc = str(info.get("description") or info.get("name") or name).strip() or name
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
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
        )
    return tools


def build_file_protocol_tool_defs() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Unified file-writing entry for code and file changes. Use this for new files, full rewrites, or instruction-driven updates to an existing file by providing complete content or a precise change_request, instructions, problem, or description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Target file path. Can be workspace-relative or a resolved Desktop/Documents/Downloads path.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete file content to write when you already know the final file.",
                        },
                        "change_request": {
                            "type": "string",
                            "description": "Precise request describing what this file should contain or how it should be rewritten if full content is not provided.",
                        },
                        "instructions": {
                            "type": "string",
                            "description": "Alternate field for file instructions when change_request is not used.",
                        },
                        "problem": {
                            "type": "string",
                            "description": "Observed issue or desired correction that should be resolved in the whole-file output.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Short summary of the intended file change; can also be used as a write request when full content is not provided.",
                        },
                    },
                    "required": ["file_path"],
                },
            },
        },
    ]


COD_TOOL_DEFS_DEFAULT = [
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
]


def load_cod_tool_defs() -> list[dict]:
    global _tools_error_count

    path = CONFIGS_DIR / "tools.json"
    backup = CONFIGS_DIR / "tools.json.bak"
    try:
        cfg = json.loads(path.read_text("utf-8"))
        tools = cfg.get("cod_tools", [])
        if tools:
            _tools_error_count = 0
            return [{"type": "function", "function": item} for item in tools]
    except Exception:
        _tools_error_count += 1
        if _tools_error_count >= 3 and backup.exists():
            try:
                shutil.copy2(backup, path)
                _tools_error_count = 0
                cfg = json.loads(path.read_text("utf-8"))
                tools = cfg.get("cod_tools", [])
                if tools:
                    return [{"type": "function", "function": item} for item in tools]
            except Exception:
                pass
    return COD_TOOL_DEFS_DEFAULT


COD_TOOL_DEFS = load_cod_tool_defs()


def build_sense_environment_tool_def() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "sense_environment",
            "description": "Inspect the current computer environment before desktop actions or when the current state is unclear.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detail_level": {
                        "type": "string",
                        "description": "Environment detail level.",
                        "enum": ["basic", "full"],
                    }
                },
                "required": [],
            },
        },
    }


def build_tools_list(get_all_skills, get_exposed_skills, ask_user_tool_def) -> list[dict]:
    tools = build_registered_skill_tool_defs(get_all_skills, get_exposed_skills, "tool_call")
    tools.extend(build_file_protocol_tool_defs())
    tools.append(ask_user_tool_def())
    return tools


def build_tools_list_cod(get_all_skills, get_exposed_skills, ask_user_tool_def) -> list[dict]:
    tools = build_registered_skill_tool_defs(
        get_all_skills,
        get_exposed_skills,
        {"tool_call", "tool_call_cod"},
    )
    tools.extend(load_cod_tool_defs())
    tools.append(ask_user_tool_def())
    tools.append(build_sense_environment_tool_def())
    tools.extend(build_file_protocol_tool_defs())
    return tools
