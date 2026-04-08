import json

from core import shared as S


def get_tool_call_enabled() -> bool:
    try:
        from core.runtime_state.state_loader import TOOL_CALL_CONFIG_FILE

        cfg = json.loads(TOOL_CALL_CONFIG_FILE.read_text("utf-8"))
        return bool(cfg.get("enabled", True))
    except Exception:
        return True


def get_cod_enabled() -> bool:
    try:
        from core.runtime_state.state_loader import TOOL_CALL_CONFIG_FILE

        cfg = json.loads(TOOL_CALL_CONFIG_FILE.read_text("utf-8"))
        return bool(cfg.get("cod_enabled", False))
    except Exception:
        return False


def is_anthropic_model() -> bool:
    try:
        from brain import LLM_CONFIG

        base_url = str(LLM_CONFIG.get("base_url", "")).lower()
        if "minimaxi.com" in base_url:
            return False
        return "/anthropic" in base_url
    except Exception:
        return False


def get_tool_call_unavailable_reason() -> str | None:
    if not get_tool_call_enabled():
        return "disabled"
    if is_anthropic_model():
        return "unsupported_model"
    if not S.NOVA_CORE_READY:
        return "core_not_ready"
    return None


def build_tool_call_unavailable_reply(reason: str) -> str:
    details = {
        "disabled": "tool_call 开关当前被关闭。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
        "unsupported_model": "当前模型走的是不支持原生 tool_call 的协议。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
        "core_not_ready": "AaronCore 当前未就绪。按照现在的架构，这属于主链事故，不会再静默回退到旧 skill 链。",
    }
    detail = details.get(reason, "tool_call 主链当前不可用，而且系统不会再回退到旧链。")
    return (
        "这一步没接上主链。\n"
        f"{detail}\n"
        "请先恢复 tool_call 主链，再继续当前任务。"
    )
