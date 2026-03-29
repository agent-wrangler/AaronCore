# reply_formatter - 回复格式化、trace 构建、统一回复生成
# 从 agent_final.py 提取

import ast as _ast
import json
import re as _re
from datetime import datetime as _datetime
from pathlib import Path as _Path

from core.context_builder import format_l8_context, render_dialogue_context
from core.feedback_classifier import format_l7_context
from core.fs_protocol import summarize_action_meta
from core.route_resolver import looks_like_news_request

# ── 配置文件化：从 configs/ 读取 prompt 配置 ──
_CONFIGS_DIR = _Path(__file__).resolve().parent.parent / "configs"
_prompt_error_count = 0  # 连续报错计数

def _load_prompt_config() -> dict:
    """加载 prompt 配置（连续 3 次报错自动回滚到 .bak）"""
    global _prompt_error_count
    p = _CONFIGS_DIR / "prompts.json"
    bak = _CONFIGS_DIR / "prompts.json.bak"
    try:
        cfg = json.loads(p.read_text("utf-8"))
        _prompt_error_count = 0
        return cfg
    except Exception:
        _prompt_error_count += 1
        if _prompt_error_count >= 3 and bak.exists():
            try:
                import shutil
                shutil.copy2(bak, p)
                _prompt_error_count = 0
                return json.loads(p.read_text("utf-8"))
            except Exception:
                pass
        return {}

# ── 注入依赖 ──────────────────────────────────────────────
_think = None
_think_stream = None
_llm_call = None        # 裸 llm_call（brain.llm_call），用于 tool_call 模式
_llm_call_stream = None  # 裸 llm_call_stream（brain.llm_call_stream），用于 tool_call 流式

_debug_write = lambda stage, data: None


_LEGACY_TOOL_MARKUP_RE = _re.compile(r'<\s*(?:invoke|function_calls|minimax:tool_call|tool_call)|DSML|\[\s*TOOL_CALL\s*\]', _re.I)
_LEGACY_TOOL_BLOCK_RE = _re.compile(r'\[\s*TOOL_CALL\s*\](.*?)\[\s*/\s*TOOL_CALL\s*\]', _re.I | _re.S)
_LEGACY_MINIMAX_TOOL_RE = _re.compile(r'<\s*minimax:tool_call\s*>(.*?)<\s*/\s*minimax:tool_call\s*>', _re.I | _re.S)
_LEGACY_JSON_TOOL_RE = _re.compile(r'<\s*tool_call\s*>(.*?)<\s*/\s*tool_call\s*>', _re.I | _re.S)


def _extract_json_object_text(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _salvage_string_field(raw: str, key: str) -> str:
    text = str(raw or "")
    patterns = [
        rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"',
        rf"'{key}'\s*:\s*'((?:\\.|[^'\\])*)'",
    ]
    for pattern in patterns:
        m = _re.search(pattern, text, _re.S)
        if not m:
            continue
        value = m.group(1)
        try:
            return bytes(value, "utf-8").decode("unicode_escape")
        except Exception:
            return value
    return ""


def _coerce_tool_args(raw_args, user_input: str = "") -> dict:
    args = {}
    if isinstance(raw_args, dict):
        args = dict(raw_args)
    else:
        raw = str(raw_args or "").strip()
        if raw:
            candidates = [raw]
            object_text = _extract_json_object_text(raw)
            if object_text and object_text not in candidates:
                candidates.append(object_text)
            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        args = parsed
                        break
                except Exception:
                    try:
                        parsed = _ast.literal_eval(candidate)
                        if isinstance(parsed, dict):
                            args = parsed
                            break
                    except Exception:
                        continue
            if not args:
                for key in ("file_path", "path", "target", "filename", "content", "description", "query", "topic"):
                    value = _salvage_string_field(raw, key)
                    if value:
                        args[key] = value

    for nested_key in ("parameters", "args"):
        nested = args.get(nested_key)
        if isinstance(nested, dict):
            merged = dict(nested)
            if "user_input" in args and "user_input" not in merged:
                merged["user_input"] = args["user_input"]
            args = merged

    if user_input and "user_input" not in args:
        args["user_input"] = user_input
    return args


def _sanitize_tool_call_payload(tc: dict, tool_args: dict) -> dict:
    clean_tc = dict(tc or {})
    fn = dict(clean_tc.get("function") or {})
    fn["arguments"] = json.dumps(tool_args or {}, ensure_ascii=False)
    clean_tc["function"] = fn
    return clean_tc


def _extract_recent_file_paths(bundle: dict) -> list[str]:
    paths = []
    seen = set()
    pattern = _re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+\.(?:md|html|txt|json|py|js|css)', _re.I)
    for item in reversed(list(bundle.get("l1") or [])):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        for match in pattern.findall(content):
            norm = match.replace("/", "\\")
            if norm.lower() in seen:
                continue
            seen.add(norm.lower())
            paths.append(norm)
            if len(paths) >= 6:
                return paths
    return paths


def _repair_tool_args_from_context(tool_name: str, tool_args: dict, bundle: dict) -> dict:
    args = dict(tool_args or {})
    user_input = str(bundle.get("user_input") or "")
    if tool_name != "write_file":
        if user_input and "user_input" not in args:
            args["user_input"] = user_input
        return args

    target = str(args.get("file_path") or args.get("path") or args.get("target") or args.get("filename") or "").strip()
    if target and "file_path" not in args:
        args["file_path"] = target

    if not str(args.get("file_path") or "").strip():
        recent_paths = _extract_recent_file_paths(bundle)
        if recent_paths:
            candidate = _Path(recent_paths[0])
            wants_html = any(token in user_input.lower() for token in ("网页", "html", ".html"))
            if wants_html and candidate.suffix.lower() != ".html":
                candidate = candidate.with_suffix(".html")
            args["file_path"] = str(candidate)

    if user_input and "user_input" not in args:
        args["user_input"] = user_input
    return args


def _build_current_time_context() -> str:
    now = _datetime.now()
    weekday_map = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday",
    }
    weekday = weekday_map.get(now.weekday(), "")
    return (
        f"Current local time: {now.strftime('%Y-%m-%d %H:%M')} (Asia/Shanghai, {weekday}).\n"
        f"Current year: {now.year}. Current month: {now.month}.\n"
        "When writing dates, bylines, footers, or time-sensitive summaries, use this current date unless tool results provide a more specific timestamp. "
        "Do not invent older dates."
    )
def _tool_preview(name: str, arguments: dict) -> str:
    if not isinstance(arguments, dict):
        return ""

    candidates_by_tool = {
        "open_target": ("path", "url", "target"),
        "read_file": ("file_path", "path"),
        "list_files": ("path", "file_path"),
        "write_file": ("file_path", "path", "target", "filename"),
        "save_export": ("filename", "destination"),
        "web_search": ("query", "intent"),
        "weather": ("city",),
        "news": ("topic",),
        "sense_environment": ("detail_level",),
        "ui_interaction": ("action", "target"),
        "app_target": ("target", "app", "path"),
        "ask_user": ("question",),
    }
    keys = candidates_by_tool.get(name, ())
    for key in keys:
        value = str(arguments.get(key) or "").strip()
        if value:
            return value[:120]
    return ""


def _tool_action_summary(exec_result: dict) -> str:
    if not isinstance(exec_result, dict):
        return ""
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    summary = summarize_action_meta(meta.get("action"))
    if summary:
        return summary
    response = str(exec_result.get("response") or "").strip()
    if not response:
        return ""
    response = _re.sub(r"\[drift:[^\]]+\]", "", response).strip().replace("`", "")
    lines = [line.strip(" -") for line in response.splitlines() if line.strip()]
    if not lines:
        return ""
    summary = " / ".join(lines[:2]).strip()
    return summary[:160] + ("..." if len(summary) > 160 else "")


def _build_visible_tools_context(tools: list[dict]) -> str:
    visible = []
    for item in tools or []:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "").strip()
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        param_names = [str(k).strip() for k in props.keys() if str(k).strip()]
        if name in {n for n, _, _ in visible}:
            continue
        visible.append((name, desc, param_names))

    if not visible:
        return ""

    lines = [
        f"Visible tools in this turn: {len(visible)}.",
        "When reasoning about capabilities, rely on this visible tool list instead of prior conversation memory.",
        "Do not claim a tool is unavailable unless it is absent from the visible tool list below.",
        "If the user asks for a real action in the environment, you must execute the relevant tool before claiming success.",
        "Do not say an app, file, folder, page, click, input, save, move, or delete action is done unless the tool result confirms it.",
        "Use screen_capture only for visual inspection or verification. Do not use it as a substitute for open_target, app_target, or ui_interaction.",
    ]
    for name, desc, param_names in visible:
        entry = f"- {name}"
        if param_names:
            entry += f"({', '.join(param_names[:6])})"
        if desc:
            entry += f": {desc}"
        lines.append(entry)
    return "\n".join(lines)


def _contains_legacy_tool_markup(text: str) -> bool:
    return bool(_LEGACY_TOOL_MARKUP_RE.search(str(text or '')))


def _parse_legacy_tool_call_text(text: str, user_input: str = "") -> dict | None:
    raw = str(text or "")
    tool_name = ""
    args = {}

    m = _LEGACY_TOOL_BLOCK_RE.search(raw)
    if m:
        block = m.group(1)
        tool_match = _re.search(r'tool\s*=>\s*"([^"]+)"', block, flags=_re.I)
        if tool_match:
            tool_name = str(tool_match.group(1) or "").strip()
            for key, value in _re.findall(r'--([A-Za-z0-9_]+)\s+"([^"]*)"', block):
                args[str(key).strip()] = value

    if not tool_name:
        mm = _LEGACY_MINIMAX_TOOL_RE.search(raw)
        if mm:
            block = mm.group(1)
            invoke_match = _re.search(r'<\s*invoke[^>]*name\s*=\s*"([^"]+)"[^>]*>', block, flags=_re.I)
            if invoke_match:
                tool_name = str(invoke_match.group(1) or "").strip()
                for key, value in _re.findall(
                    r'<\s*parameter[^>]*name\s*=\s*"([^"]+)"[^>]*>\s*(.*?)\s*<\s*/\s*parameter\s*>',
                    block,
                    flags=_re.I | _re.S,
                ):
                    args[str(key).strip()] = _re.sub(r'\s+', ' ', str(value or '')).strip()

    if not tool_name:
        jt = _LEGACY_JSON_TOOL_RE.search(raw)
        if jt:
            block = str(jt.group(1) or "").strip()
            payload = None
            try:
                payload = json.loads(block)
            except Exception:
                try:
                    import ast as _ast
                    payload = _ast.literal_eval(block)
                except Exception:
                    payload = None
            if isinstance(payload, dict):
                tool_name = str(payload.get("name") or payload.get("tool") or "").strip()
                params = payload.get("parameters")
                if not isinstance(params, dict):
                    params = payload.get("args")
                if isinstance(params, dict):
                    args.update(params)

    if not tool_name:
        return None

    if "target" in args and "path" not in args:
        args["path"] = args["target"]
    if "url" in args and "path" not in args:
        args["path"] = args["url"]
    if user_input and "user_input" not in args:
        args["user_input"] = user_input

    return {
        "id": "legacy_tool_call_compat",
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _infer_action_tool_call_from_reply(reply_text: str, user_input: str = "", context: dict | None = None) -> dict | None:
    raw_reply = str(reply_text or "").strip()
    raw_input = str(user_input or "").strip()
    if not raw_input:
        return None

    lowered = raw_input.lower()
    open_verbs = ("打开", "进入", "访问", "启动", "open ", "open:", "launch ", "visit ")
    if not any(v in raw_input or v in lowered for v in open_verbs):
        return None

    args = {"user_input": raw_input}
    tool_name = ""

    url_match = _re.search(r'https?://[^\s`<>"\]]+', raw_reply, flags=_re.I)
    if url_match:
        tool_name = "open_target"
        args["path"] = url_match.group(0).rstrip(".,)")
    else:
        if any(marker in raw_reply for marker in ("已打开应用", "已启动应用", "已找到并聚焦应用窗口", "窗口：")):
            return {
                "id": "inferred_action_tool_call",
                "type": "function",
                "function": {
                    "name": "app_target",
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            }
        try:
            from core.target_protocol import resolve_local_app_reference, resolve_target_reference
            local_resolved = resolve_local_app_reference(raw_input, context if isinstance(context, dict) else None) or {}
            if str(local_resolved.get("target_type") or "").strip().lower() in {"app", "window"}:
                resolved = local_resolved
            else:
                resolved = resolve_target_reference(raw_input, context if isinstance(context, dict) else None) or {}
        except Exception:
            resolved = {}

        target_type = str(resolved.get("target_type") or "").strip().lower()
        value = str(resolved.get("value") or "").strip()
        if target_type in {"url", "path"} and value:
            tool_name = "open_target"
            args["path"] = value
        elif target_type == "app" and value:
            tool_name = "app_target"
            args["target"] = value
            args["path"] = value
        elif tool_name == "app_target":
            app_label = str(resolved.get("label") or resolved.get("value") or "").strip()
            if app_label:
                args["target"] = app_label

    if not tool_name:
        return None

    return {
        "id": "inferred_action_tool_call",
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def _force_app_tool_call_from_reply(reply_text: str, user_input: str = "") -> dict | None:
    raw_reply = str(reply_text or "").strip()
    raw_input = str(user_input or "").strip()
    if not raw_input:
        return None
    open_verbs = ("打开", "进入", "访问", "启动", "open ", "open:", "launch ", "visit ")
    if not any(v in raw_input or v in raw_input.lower() for v in open_verbs):
        return None
    if not any(marker in raw_reply for marker in ("已打开应用", "已启动应用", "已找到并聚焦应用窗口", "窗口：")):
        return None
    return {
        "id": "inferred_action_tool_call",
        "type": "function",
        "function": {
            "name": "app_target",
            "arguments": json.dumps({"user_input": raw_input}, ensure_ascii=False),
        },
    }


def _tool_has_unresolved_drift(exec_result: dict) -> bool:
    if not isinstance(exec_result, dict):
        return False
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    drift = meta.get("drift") if isinstance(meta.get("drift"), dict) else {}
    post = meta.get("post_condition") if isinstance(meta.get("post_condition"), dict) else {}
    if str(drift.get("reason") or "").strip():
        return True
    if post and not bool(post.get("ok", True)):
        return True
    return False


def _append_drift_note(tool_response: str, exec_result: dict) -> str:
    text = str(tool_response or "")
    if "[drift:" in text:
        return text
    if not isinstance(exec_result, dict):
        return text
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    state = meta.get("state") if isinstance(meta.get("state"), dict) else {}
    drift = meta.get("drift") if isinstance(meta.get("drift"), dict) else {}
    reason = str(drift.get("reason") or "").strip()
    if not reason:
        post = meta.get("post_condition") if isinstance(meta.get("post_condition"), dict) else {}
        reason = str(post.get("drift") or "").strip()
        if post.get("expected") and not state.get("expected_state"):
            state["expected_state"] = str(post.get("expected"))
        if post.get("observed") and not state.get("observed_state"):
            state["observed_state"] = str(post.get("observed"))
        if post.get("hint") and not drift.get("repair_hint"):
            drift["repair_hint"] = str(post.get("hint"))
    if not reason:
        return text
    expected = str(state.get("expected_state") or "unknown").strip()
    observed = str(state.get("observed_state") or "unknown").strip()
    hint = str(drift.get("repair_hint") or "retry").strip()
    suffix = f"[drift: expected={expected} observed={observed} hint={hint}]"
    return f"{text}\n{suffix}" if text else suffix


def _tool_requires_user_takeover(exec_result: dict) -> bool:
    if not isinstance(exec_result, dict):
        return False
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    drift = meta.get("drift") if isinstance(meta.get("drift"), dict) else {}
    post = meta.get("post_condition") if isinstance(meta.get("post_condition"), dict) else {}
    reason = str(drift.get("reason") or post.get("drift") or "").strip().lower()
    hint = str(drift.get("repair_hint") or post.get("hint") or "").strip().lower()
    return reason in {"auth_required", "login_required", "verification_required", "captcha_required"} or hint in {"user_login_required", "user_verification_required"}


def _build_l1_messages(bundle: dict, limit: int = 10) -> list[dict]:
    """\u4ece bundle['l1'] \u53d6\u6700\u8fd1 N \u8f6e\u5bf9\u8bdd\uff0c\u8f6c\u6210 user/assistant \u4ea4\u66ff\u7684 messages \u6570\u7ec4"""
    l1 = bundle.get("l1") or []
    if not l1:
        return []
    # l1 \u662f [{"role": "user"/"nova"/"assistant", "content": "...", "time": "..."}]
    # \u53d6\u6700\u8fd1 limit*2 \u6761\uff08\u6bcf\u8f6e = user + assistant\uff09
    recent = l1[-(limit * 2):]
    messages = []
    for item in recent:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        # \u7edf\u4e00 role \u4e3a OpenAI \u683c\u5f0f
        if role == "user":
            api_role = "user"
        elif role in ("nova", "assistant"):
            api_role = "assistant"
        else:
            continue
        if api_role == "assistant" and _contains_legacy_tool_markup(content):
            continue
        # \u622a\u65ad\u8d85\u957f\u56de\u590d\uff08\u4fdd\u7559\u524d 800 \u5b57\uff09
        if len(content) > 800:
            content = content[:800] + "\u2026"
        # \u907f\u514d\u8fde\u7eed\u540c role\uff08OpenAI API \u8981\u6c42\u4ea4\u66ff\uff09
        if messages and messages[-1]["role"] == api_role:
            messages[-1]["content"] += "\n" + content
        else:
            messages.append({"role": api_role, "content": content})

    # 去掉最后一条 user 消息（它会作为独立的 user prompt 再发一次，避免 LLM 以为用户说了两遍）
    current_input = str(bundle.get("user_input") or "").strip()
    if current_input and messages and messages[-1]["role"] == "user":
        last_content = messages[-1]["content"].strip()
        if last_content == current_input or current_input in last_content:
            messages = messages[:-1]

    return messages


def _build_recent_dialogue_text(bundle: dict, limit: int = 6) -> str:
    """把最近几轮 L1 对话压成简短文本，供普通聊天 prompt 使用。"""
    messages = _build_l1_messages(bundle, limit=limit)
    if not messages:
        return ""

    lines = []
    for item in messages[-limit:]:
        role = "用户" if item.get("role") == "user" else "Nova"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if len(content) > 180:
            content = content[:180] + "…"
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


def _build_active_task_context(bundle: dict, recent_attempts: list[dict] | None = None) -> str:
    task_plan = bundle.get("task_plan") if isinstance(bundle.get("task_plan"), dict) else {}
    if not task_plan:
        return ""

    goal = str(task_plan.get("goal") or bundle.get("user_input") or "").strip()
    if not goal:
        return ""

    lines = [f"Current task goal in this turn: {goal}"]

    phase = str(task_plan.get("phase") or "").strip()
    summary = str(task_plan.get("summary") or "").strip()
    current_item_id = str(task_plan.get("current_item_id") or "").strip()
    if phase:
        lines.append(f"Current phase: {phase}")
    if summary:
        lines.append(f"Plan summary: {summary}")
    if current_item_id:
        lines.append(f"Current plan item: {current_item_id}")

    success_paths = bundle.get("l5_success_paths") if isinstance(bundle.get("l5_success_paths"), list) else []
    if success_paths:
        lines.append("Reusable successful approaches for similar tasks:")
        for item in success_paths[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("核心技能") or "").strip()
            summary = str(item.get("summary") or item.get("应用示例") or "").strip()
            if name and summary:
                lines.append(f"- {name}: {summary}")
            elif name:
                lines.append(f"- {name}")

    attempts = recent_attempts or []
    if attempts:
        lines.append("Recent attempts in this turn:")
        for item in attempts[-4:]:
            tool_name = str(item.get("tool") or "").strip()
            status = "success" if item.get("success") else "failed"
            summary = str(item.get("summary") or "").strip()
            if tool_name and summary:
                lines.append(f"- {tool_name}: {status} | {summary}")
            elif tool_name:
                lines.append(f"- {tool_name}: {status}")

    lines.append("Keep advancing the same user goal unless a tool result clearly changes it.")
    lines.append("Do not restart the search from scratch after every tool call.")
    lines.append("Use the latest tool result to choose the next closest action.")
    return "\n".join(lines)


def _build_style_hints_from_l4(l4: dict, *, is_skill: bool = False) -> str:
    """从 L4 人格数据动态生成风格提示文本，不再硬编码任何具体风格"""
    modes = l4.get("persona_modes") or {}
    active = str(l4.get("active_mode") or "").strip()
    mode_data = modes.get(active) or {}

    style = str(mode_data.get("style_prompt") or l4.get("style_prompt") or "").strip()
    tone = mode_data.get("tone") or (l4.get("speech_style") or {}).get("tone") or []
    particles = mode_data.get("particles") or (l4.get("speech_style") or {}).get("particles") or []
    avoid = mode_data.get("avoid") or (l4.get("speech_style") or {}).get("avoid") or []
    expression = str(mode_data.get("expression") or "").strip()
    interaction = str(mode_data.get("interaction_style") or "").strip()

    lines = []
    if style:
        lines.append(style)
    if expression:
        lines.append(expression)
    if interaction:
        lines.append(interaction)
    if tone:
        lines.append("\u8bed\u6c14\u5173\u952e\u8bcd\uff1a" + "\u3001".join(tone))
    if particles:
        lines.append("\u5e38\u7528\u8bed\u6c14\u8bcd\uff1a" + "\u3001".join(particles))
    if is_skill:
        lines.append("\u5de5\u5177\u7ed3\u679c\u53ea\u662f\u7d20\u6750\uff0c\u4f60\u8981\u4ee5 Nova \u7684\u4eba\u683c\u548c\u4e3b\u4eba\u8bf4\u8bdd\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u64ad\u62a5\u3002")
        lines.append("\u5373\u4f7f\u662f\u67e5\u8be2\u7ed3\u679c\u3001\u6267\u884c\u7ed3\u679c\u6216\u4e8b\u5b9e\u4fe1\u606f\uff0c\u4e5f\u8981\u4fdd\u6301 L4 \u7684\u6e29\u5ea6\u3001\u966a\u4f34\u611f\u548c\u8bf4\u8bdd\u4e60\u60ef\u3002")
        lines.append("\u5148\u81ea\u7136\u63a5\u4f4f\u4e3b\u4eba\u8fd9\u53e5\u8bdd\uff0c\u518d\u628a\u5de5\u5177\u7ed3\u679c\u878d\u8fdb\u56de\u590d\u91cc\u3002")

    avoid_block = ""
    if avoid:
        avoid_lines = "\n".join("- " + a for a in avoid)
        avoid_block = "\n\n\u7981\u6b62\uff1a\n" + avoid_lines

    return "\n".join(lines) + avoid_block
_debug_write = lambda stage, data: None
_nova_core_ready = False
_get_all_skills = lambda: {}
_nova_execute = lambda route_result, skill_input: {"success": False}
_evolve = lambda user_input, skill_name: None
_load_autolearn_config = lambda: {}
_load_self_repair_reports = lambda: []
_find_feedback_rule = lambda msg, history: None


def init(*, think=None, think_stream=None, debug_write=None, nova_core_ready=False,
         get_all_skills=None, nova_execute=None, evolve=None,
         load_autolearn_config=None, load_self_repair_reports=None,
         find_feedback_rule=None, llm_call=None, llm_call_stream=None):
    global _think, _think_stream, _debug_write, _nova_core_ready, _get_all_skills
    global _nova_execute, _evolve, _load_autolearn_config
    global _load_self_repair_reports, _find_feedback_rule
    global _llm_call, _llm_call_stream
    if think:
        _think = think
    if think_stream:
        _think_stream = think_stream
    if debug_write:
        _debug_write = debug_write
    _nova_core_ready = nova_core_ready
    if get_all_skills:
        _get_all_skills = get_all_skills
    if nova_execute:
        _nova_execute = nova_execute
    if evolve:
        _evolve = evolve
    if load_autolearn_config:
        _load_autolearn_config = load_autolearn_config
    if load_self_repair_reports:
        _load_self_repair_reports = load_self_repair_reports
    if find_feedback_rule:
        _find_feedback_rule = find_feedback_rule
    if llm_call:
        _llm_call = llm_call
    if llm_call_stream:
        _llm_call_stream = llm_call_stream


# ── 学习/修复状态摘要 ────────────────────────────────────

def _build_learning_summary(config: dict) -> str:
    if not bool(config.get("enabled", True)):
        return "自动学习已关闭，反馈只会停留在当前会话里。"
    if bool(config.get("allow_feedback_relearn", True)):
        if bool(config.get("allow_web_search", True)) and bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，必要时补学并写回知识库。"
        if bool(config.get("allow_knowledge_write", True)):
            return "会先记住负反馈，并把纠偏结论沉淀到知识库。"
        return "会先记住负反馈，但暂时不会长期沉淀到知识库。"
    return "现在不会把负反馈沉淀成纠偏记录。"


def _build_repair_summary(config: dict) -> str:
    planning_enabled = bool(config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"

    if not planning_enabled:
        return "目前只做学习纠偏，不会主动整理修复方案。"
    if not test_run_enabled:
        return "会先整理修法，但动手前还不会自动自查。"
    if not auto_apply_enabled:
        return "会先整理修法并自己检查，真正动手前先停下来给你看。"
    if apply_mode == "suggest":
        return "低风险会自己继续，中高风险先给你看方案。"
    return "低风险会自己继续，中高风险只确认一次。"


def _build_latest_status_summary(latest: dict, latest_preview: dict, latest_apply: dict) -> str:
    apply_status = str((latest_apply or {}).get("status") or "").strip()
    if apply_status:
        if apply_status in {"applied", "applied_without_validation"} and bool(latest_apply.get("auto_applied")):
            return "最近一次反馈已经在后台自动落成修改。"
        if apply_status == "applied":
            return "最近一次反馈已经真正动手修改并通过了自查。"
        if apply_status == "applied_without_validation":
            return "最近一次反馈已经动手修改，但还没有跑自查。"
        if apply_status.startswith("rolled_back"):
            return "最近一次尝试已经自动回滚，没有把坏补丁留在源码里。"
        return "最近一次反馈已经走到动手阶段，但结果还需要进一步确认。"

    preview_status = str((latest_preview or {}).get("status") or "").strip()
    if preview_status == "preview_ready":
        if bool(latest_preview.get("auto_apply_ready")):
            return "最近一次反馈已经整理成低风险补丁，会继续在后台往下处理。"
        if bool(latest_preview.get("confirmation_required", True)):
            return "最近一次反馈已经整理出改法，只等一次确认。"
        return "最近一次反馈已经整理出改法，这次不用额外确认。"

    latest_status = str((latest or {}).get("status") or "").strip()
    if latest_status:
        return "最近一次反馈已经被记进纠偏链路，后面会沿着这条线继续学习或修正。"
    return "最近还没有新的纠偏记录。"


def build_self_repair_status() -> dict:
    l8_config = _load_autolearn_config()
    all_reports = _load_self_repair_reports()
    latest = all_reports[0] if all_reports else {}
    latest_preview = latest.get("patch_preview") or {}
    latest_apply = latest.get("apply_result") or {}
    planning_enabled = bool(l8_config.get("allow_self_repair_planning", True))
    test_run_enabled = bool(l8_config.get("allow_self_repair_test_run", True))
    auto_apply_enabled = bool(l8_config.get("allow_self_repair_auto_apply", True))
    apply_mode = str(l8_config.get("self_repair_apply_mode") or "confirm").strip() or "confirm"
    learning_summary = _build_learning_summary(l8_config)
    repair_summary = _build_repair_summary(l8_config)

    return {
        "stage": "controlled_patch_loop" if planning_enabled else "feedback_learning_only",
        "feedback_learning": bool(l8_config.get("allow_feedback_relearn", True)),
        "web_learning": bool(l8_config.get("allow_web_search", True)),
        "knowledge_write": bool(l8_config.get("allow_knowledge_write", True)),
        "planning_enabled": planning_enabled,
        "test_run_enabled": test_run_enabled,
        "auto_apply_enabled": auto_apply_enabled,
        "skill_generation": bool(l8_config.get("allow_skill_generation", False)),
        "apply_mode": apply_mode,
        "report_count": len(all_reports),
        "latest_report_id": str(latest.get("id") or ""),
        "latest_report_status": str(latest.get("status") or ""),
        "latest_summary": str(latest.get("summary") or ""),
        "latest_apply_status": str(latest_apply.get("status") or ""),
        "latest_risk_level": str(latest_preview.get("risk_level") or latest.get("risk_level") or ""),
        "latest_auto_apply_ready": bool(latest_preview.get("auto_apply_ready")),
        "latest_confirmation_required": bool(latest_preview.get("confirmation_required", True)),
        "learning_summary": learning_summary,
        "repair_summary": repair_summary,
        "autonomy_summary": f"{learning_summary.rstrip('。')}；{repair_summary}",
        "latest_status_summary": _build_latest_status_summary(latest, latest_preview, latest_apply),
        "can_patch_source_code": True,
        "can_plan_repairs": planning_enabled,
        "can_run_source_tests": test_run_enabled,
        "can_auto_apply_fixes": planning_enabled and test_run_enabled and auto_apply_enabled,
    }
# PLACEHOLDER_CAPABILITIES

def list_primary_capabilities() -> list[str]:
    if not _nova_core_ready:
        return ["陪你聊天"]

    preferred = ["weather", "story", "stock", "draw", "run_code"]
    skills = _get_all_skills()
    labels = []
    for name in preferred:
        info = skills.get(name)
        if not info:
            continue
        label = str(info.get("name") or name).strip()
        if label and label not in labels:
            labels.append(label)
    return labels or ["陪你聊天"]


def get_skill_display_name(skill_name: str) -> str:
    name = str(skill_name or "").strip()
    if not name:
        return "技能"
    if _nova_core_ready:
        try:
            skill_info = _get_all_skills().get(name, {})
            return str(skill_info.get("name") or name)
        except Exception:
            pass
    return name


# ── 特殊意图回复 ──────────────────────────────────────────

def build_capability_chat_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    status = build_self_repair_status()

    if intent == "self_repair_capability":
        return (
            "我现在已经接上更省心的自修正啦。现在这套能走到“收到负反馈 -> 生成修正提案 -> 列候选文件 -> 跑最小测试”这一步。\n\n"
            "如果只是低风险的小修小补，我会在后台直接尝试落补丁；只要改动碰到更核心的链路，我就先问你一次。"
            "如果补丁后的最小验证没过，我会自动回滚，不把坏改动留在源码里。"
        )

    if intent == "missing_skill":
        missing_skill = str(route.get("missing_skill") or route.get("skill") or "技能").strip() or "技能"
        label = get_skill_display_name(missing_skill)
        prompt = str(route.get("rewritten_input") or "").strip()
        if missing_skill == "news" or looks_like_news_request(prompt):
            return f"我本来想按「{label}」这条路接住你这句，但这项能力现在没接上，所以我先不乱报“今天”的新闻，免得把旧信息当成现在。"
        return f"我本来想按「{label}」这条能力接住你这句，不过它现在没接上，所以先不拿一条失效结果糊弄你。"

    skills = "、".join(list_primary_capabilities())
    tail = "源码自修这边现在是：低风险小改动会先自己修，碰到更核心的链路再问你一次；如果验证不过，我会自动回滚。"
    if status["feedback_learning"]:
        return f"我现在能陪你聊天，也能做这些：{skills}。{tail}"
    return f"我现在能陪你聊天，也能做这些：{skills}。"
# PLACEHOLDER_META_REPLIES

def build_meta_bug_report_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()

    if status.get("can_auto_apply_fixes"):
        return (
            "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
            f"排查后会继续走自修复链路：生成修复提案、跑最小验证，低风险补丁会自动落地。{latest}"
        )

    return (
        "我会先进入排查模式，把这类话当成界面异常或路由误触发，不再直接跳去小游戏。\n\n"
        f"排查后会继续走修复链路：先生成修复提案和验证计划，不过不是每种情况都会自动改源码。{latest}"
    )


def build_answer_correction_reply(route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    status = build_self_repair_status()
    latest = str(status.get("latest_status_summary") or "").strip()
    latest_tail = f" {latest}" if latest else ""
    return (
        "这句我会直接当成你在纠正我上一轮答偏了，不再往天气之类的技能上联想。\n\n"
        f"我先停掉错误路由，回到你刚才真正指出的那件事继续排查；这次纠偏也会记进修复链路里。{latest_tail}"
    )


# ── 统一聊天回复 ──────────────────────────────────────────

def unified_chat_reply(bundle: dict, route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        return build_capability_chat_reply(route)
    if intent == "meta_bug_report":
        return build_meta_bug_report_reply(route)
    if intent == "answer_correction":
        return build_answer_correction_reply(route)

    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l5_success_paths = bundle.get("l5_success_paths", [])
    l7 = bundle.get("l7", [])
    l7_context = format_l7_context(l7)
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    l2_memories = bundle.get("l2_memories", [])
    l2_context = ""
    if l2_memories:
        lines = []
        for mem in l2_memories:
            user_text = str(mem.get("user_text", ""))[:80]
            importance = mem.get("importance", 0)
            marker = "\u2605" if importance >= 0.7 else "\u00b7"
            lines.append(f"{marker} {user_text}")
        l2_context = "\n".join(lines)
    dialogue_context = render_dialogue_context(bundle.get("dialogue_context", ""))
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    search_summary = bundle.get("search_summary", "")
    current_model = bundle.get("current_model", "")

    # 如果有实时搜索结果，构建增强 prompt
    search_block = ""
    if search_context:
        search_block = f"""
实时联网搜索结果（刚刚搜到的，必须基于这些真实内容回复，不要编造）：
{search_context}
搜索摘要：{search_summary}

重要：你刚刚真的去联网搜索了，请基于上面的搜索结果整理回复。不要说"我去查一下"之类的话，你已经查完了，直接告诉用户你学到了什么。
"""

    style_hints = _build_style_hints_from_l4(l4, is_skill=True)

    # 时间回忆区块
    recall_context = bundle.get("recall_context", "")
    recall_block = ""
    if recall_context:
        recall_block = (
            "\n时间回忆（用户在回忆之前的对话，请根据下面的记录回答）：\n"
            f"{recall_context}\n\n"
            "重要：用户在问之前聊过什么，请直接根据上面的对话记录整理回答，"
            "不要说\u201c我不记得\u201d或\u201c我只能看到最近的对话\u201d。\n"
        )

    prompt = f"""
用户输入：{msg}
{search_block}
{recall_block}
你的底层模型：{current_model}

L2持久记忆（之前对话中的重要片段）：
{l2_context or "暂无"}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L5知识：
{json.dumps(l5, ensure_ascii=False)}

L7经验教训（之前犯过的错，务必避免重犯）：
{l7_context or "暂无"}

L8已学知识：
{l8_context or "暂无命中的已学知识"}

回复要求（优先级最高，必须遵守）：
1. 这是普通聊天，直接自然回复。
2. 你拥有完整的记忆系统（L1-L8），上面的对话历史和记忆数据都是你真实拥有的记忆。禁止说"我没有记忆""我记不住""每次对话都是全新的""我看不到之前的对话"之类的话。如果用户问你记不记得，直接根据上面的对话历史和记忆数据回答，不要自我否定。
3. 如果 L8 已经学过和当前问题有关的知识，优先吸收后再回答，不要像第一次见到这个问题。
4. 如果 L2 持久记忆中有和当前话题相关的内容，自然地接上，体现你记得之前聊过的事。
5. 如果用户这句话是承接上一轮的追问（例如"那什么时候有啊""然后呢""为什么""这个呢"），默认沿着最近对话的话题直接接上，不要反问"你指什么"。
6. 当用户问你是什么模型、用的什么大模型、底层是什么时，必须直接告诉用户你的底层模型是 {current_model}，不要回避、不要模糊。
7. 不要输出思考过程，只输出最终回复。
8. \u56de\u590d\u65f6\u53ef\u4ee5\u81ea\u7531\u4f7f\u7528 Markdown \u8bed\u6cd5\uff08# \u6807\u9898\u3001**\u52a0\u7c97**\u3001`\u4ee3\u7801`\u3001- \u5217\u8868\u7b49\uff09\uff0c\u8ba9\u5185\u5bb9\u66f4\u6709\u5c42\u6b21\u611f\u3002

最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：
L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

{style_hints}
""".strip()
    result = _think(prompt, dialogue_context, image=bundle.get("image"), images=bundle.get("images"))
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("\ufffd" in str(reply)) or len(str(reply).strip()) < 2:
        return "我在呢，你直接说，我会认真接着你的话聊。"
    return str(reply).strip()


def unified_chat_reply_stream(bundle: dict, route: dict | None = None):
    """流式版 unified_chat_reply，yield delta token (str)。
    对于非聊天意图（能力查询等），直接 yield 完整回复。"""
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    # 特殊意图不走流式
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        yield build_capability_chat_reply(route)
        return
    if intent == "meta_bug_report":
        yield build_meta_bug_report_reply(route)
        return
    if intent == "answer_correction":
        yield build_answer_correction_reply(route)
        return

    if not _think_stream:
        # fallback: 没有注入流式函数，走非流式
        yield unified_chat_reply(bundle, route)
        return

    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l7 = bundle.get("l7", [])
    l7_context = format_l7_context(l7)
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    l2_memories = bundle.get("l2_memories", [])
    l2_context = ""
    if l2_memories:
        lines = []
        for mem in l2_memories:
            user_text = str(mem.get("user_text", ""))[:80]
            importance = mem.get("importance", 0)
            marker = "\u2605" if importance >= 0.7 else "\u00b7"
            lines.append(f"{marker} {user_text}")
        l2_context = "\n".join(lines)
    dialogue_context = render_dialogue_context(bundle.get("dialogue_context", ""))
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    search_summary = bundle.get("search_summary", "")
    current_model = bundle.get("current_model", "")
    search_block = ""
    if search_context:
        search_block = f"""
实时联网搜索结果（刚刚搜到的，必须基于这些真实内容回复，不要编造）：
{search_context}
搜索摘要：{search_summary}

重要：你刚刚真的去联网搜索了，请基于上面的搜索结果整理回复。不要说"我去查一下"之类的话，你已经查完了，直接告诉用户你学到了什么。
"""
    style_hints = _build_style_hints_from_l4(l4)
    recall_context = bundle.get("recall_context", "")
    recall_block = ""
    if recall_context:
        recall_block = (
            "\n时间回忆（用户在回忆之前的对话，请根据下面的记录回答）：\n"
            f"{recall_context}\n\n"
            "重要：用户在问之前聊过什么，请直接根据上面的对话记录整理回答，"
            "不要说\u201c我不记得\u201d或\u201c我只能看到最近的对话\u201d。\n"
        )
    prompt = f"""
用户输入：{msg}
{search_block}
{recall_block}
你的底层模型：{current_model}

L2持久记忆（之前对话中的重要片段）：
{l2_context or "暂无"}

L3长期记忆：
{json.dumps(l3, ensure_ascii=False)}

L5知识：
{json.dumps(l5, ensure_ascii=False)}

L7经验教训（之前犯过的错，务必避免重犯）：
{l7_context or "暂无"}

L8已学知识：
{l8_context or "暂无命中的已学知识"}

回复要求（优先级最高，必须遵守）：
1. 这是普通聊天，直接自然回复。
2. 你拥有完整的记忆系统（L1-L8），上面的对话历史和记忆数据都是你真实拥有的记忆。禁止说"我没有记忆""我记不住""每次对话都是全新的""我看不到之前的对话"之类的话。如果用户问你记不记得，直接根据上面的对话历史和记忆数据回答，不要自我否定。
3. 如果 L8 已经学过和当前问题有关的知识，优先吸收后再回答，不要像第一次见到这个问题。
4. 如果 L2 持久记忆中有和当前话题相关的内容，自然地接上，体现你记得之前聊过的事。
5. 如果用户这句话是承接上一轮的追问（例如"那什么时候有啊""然后呢""为什么""这个呢"），默认沿着最近对话的话题直接接上，不要反问"你指什么"。
6. 当用户问你是什么模型、用的什么大模型、底层是什么时，必须直接告诉用户你的底层模型是 {current_model}，不要回避、不要模糊。
7. 不要输出思考过程，只输出最终回复。
8. \u56de\u590d\u65f6\u53ef\u4ee5\u81ea\u7531\u4f7f\u7528 Markdown \u8bed\u6cd5\uff08# \u6807\u9898\u3001**\u52a0\u7c97**\u3001`\u4ee3\u7801`\u3001- \u5217\u8868\u7b49\uff09\uff0c\u8ba9\u5185\u5bb9\u66f4\u6709\u5c42\u6b21\u611f\u3002

最后，用下面的人格风格润色你的回复（只影响语气和措辞，不能覆盖上面的事实性要求）：
L4人格信息：
{json.dumps(l4, ensure_ascii=False)}

{style_hints}
""".strip()

    # 闪回 hint
    flashback = bundle.get("flashback_hint")
    if flashback:
        prompt += f"\n\n{flashback}"

    for chunk in _think_stream(prompt, dialogue_context, image=bundle.get("image"), images=bundle.get("images")):
        if isinstance(chunk, dict):
            if chunk.get("_done"):
                break
            yield chunk  # pass through signals like _thinking
        else:
            yield chunk


# ── tool_call 模式回复 ─────────────────────────────────────

# ── CoD (Context-on-Demand) 精简 prompt ──

def _condense_l4(l4: dict) -> str:
    """\u4ece L4 \u5b8c\u6574 JSON \u63d0\u53d6\u6838\u5fc3\u8eab\u4efd\u4fe1\u606f\uff0c\u538b\u7f29\u5230 ~200 \u5b57"""
    lp = l4.get("local_persona") or l4
    parts = []
    ai = lp.get("ai_profile") or {}
    identity = ai.get("identity", "")
    if identity:
        parts.append(identity)
    boundary = ai.get("boundary", "")
    if boundary:
        parts.append(boundary)
    up = lp.get("user_profile") or {}
    user_id = up.get("identity", "")
    if user_id:
        parts.append(f"\u7528\u6237\uff1a{user_id}")
    city = up.get("city", "")
    if city:
        parts.append(f"\u7528\u6237\u6240\u5728\u57ce\u5e02\uff1a{city}")
    rp = lp.get("relationship_profile") or {}
    rel = rp.get("relationship", "")
    if rel:
        parts.append(f"\u5173\u7cfb\uff1a{rel}")
    rules = lp.get("interaction_rules") or []
    if rules:
        parts.append("\u4ea4\u4e92\u89c4\u5219\uff1a" + "\uff1b".join(str(r) for r in rules[-5:]))
    return "\n".join(parts)


def _build_session_context_text(l2_session: dict) -> str:
    if not isinstance(l2_session, dict):
        return ""
    parts = []
    topic_sep = "\u3001"
    topics = [str(t).strip() for t in (l2_session.get("topics") or []) if str(t).strip()]
    if topics and topics != ["\u95f2\u804a"]:
        parts.append(f"\u5f53\u524d\u8bdd\u9898\uff1a{topic_sep.join(topics[:4])}")
    mood = str(l2_session.get("mood") or "").strip()
    if mood:
        parts.append(f"\u7528\u6237\u60c5\u7eea\uff1a{mood}")
    intent = str(l2_session.get("intent") or "").strip()
    if intent and intent != "\u95f2\u804a":
        parts.append(f"\u4f1a\u8bdd\u610f\u56fe\uff1a{intent}")
    user_state = str(l2_session.get("user_state") or "").strip()
    if user_state:
        parts.append(f"\u7528\u6237\u72b6\u6001\uff1a{user_state}")
    return "\n".join(parts)


def _build_light_chat_prompt(bundle: dict) -> str:
    """普通聊天轻量 prompt：只带 L1/L2 session/L4/dialogue hint/flashback/L7。"""
    l4 = bundle["l4"]
    l7 = bundle.get("l7", [])
    l2_session = bundle.get("l2", {})
    current_model = bundle.get("current_model", "")
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    search_summary = bundle.get("search_summary", "")
    recall_context = bundle.get("recall_context", "")
    flashback = bundle.get("flashback_hint")

    l1_text = _build_recent_dialogue_text(bundle, limit=6) or "\u6682\u65e0"
    l2_text = _build_session_context_text(l2_session) or "\u6682\u65e0"
    l4_text = _condense_l4(l4) or "\u6682\u65e0"
    l7_text = format_l7_context(l7) or "\u6682\u65e0"
    style_hints = _build_style_hints_from_l4(l4)
    time_context = _build_current_time_context()

    sections = [
        time_context,
        f"\u5f53\u524d\u7528\u6237\u8f93\u5165\uff1a{msg}",
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}",
        f"L1 \u6700\u8fd1\u5bf9\u8bdd\uff1a\n{l1_text}",
        f"L2 session_context\uff1a\n{l2_text}",
        f"L4 persona\uff1a\n{l4_text}",
        f"L7 relevant rules\uff1a\n{l7_text}",
    ]

    if search_context:
        search_block = f"\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\uff1a\n{search_context}"
        if search_summary:
            search_block += f"\n\u641c\u7d22\u6458\u8981\uff1a{search_summary}"
        sections.append(search_block)

    if recall_context:
        sections.append(f"\u65f6\u95f4\u56de\u5fc6\uff1a\n{recall_context}")

    if flashback:
        sections.append(str(flashback))

    sections.append(
        "\u56de\u590d\u8981\u6c42\uff1a\n"
        "1. \u8fd9\u662f\u666e\u901a\u804a\u5929\uff0c\u76f4\u63a5\u81ea\u7136\u63a5\u8bdd\uff0c\u4e0d\u8981\u5148\u505a\u957f\u7bc7\u94fa\u57ab\u3002\n"
        "2. \u76f4\u63a5\u57fa\u4e8e\u4e0a\u9762\u7684 L1/L2/L4/L7 \u56de\u7b54\uff0c\u4e0d\u8981\u8bf4\u81ea\u5df1\u6ca1\u6709\u8bb0\u5fc6\u3002\n"
        "3. \u7528\u6237\u8ffd\u95ee\u65f6\u9ed8\u8ba4\u6cbf\u7740\u6700\u8fd1\u8bdd\u9898\u63a5\u4e0a\uff0c\u4e0d\u8981\u53cd\u95ee\u201c\u4f60\u6307\u4ec0\u4e48\u201d\u3002\n"
        f"4. \u5982\u679c\u7528\u6237\u95ee\u6a21\u578b\u4fe1\u606f\uff0c\u76f4\u63a5\u56de\u7b54\u5e95\u5c42\u6a21\u578b\u662f {current_model}\u3002\n"
        "5. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\uff0c\u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002\n"
        "6. \u4e8b\u5b9e\u4fe1\u606f\u4f18\u5148\u51c6\u786e\uff0c\u8bed\u6c14\u518d\u6309\u4eba\u683c\u98ce\u683c\u81ea\u7136\u8868\u8fbe\u3002"
    )
    sections.append(f"\u98ce\u683c\u63d0\u793a\uff1a\n{style_hints}")
    return "\n\n".join(part for part in sections if part).strip()


def unified_chat_reply(bundle: dict, route: dict | None = None) -> str:
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        return build_capability_chat_reply(route)
    if intent == "meta_bug_report":
        return build_meta_bug_report_reply(route)
    if intent == "answer_correction":
        return build_answer_correction_reply(route)

    prompt = _build_light_chat_prompt(bundle)
    # 普通聊天轻链路已经携带 L1 最近对话，这里不再重复注入 dialogue_context。
    result = _think(prompt, "", image=bundle.get("image"), images=bundle.get("images"))
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("\ufffd" in str(reply)) or len(str(reply).strip()) < 2:
        return "\u6211\u5728\u5440\uff0c\u4f60\u76f4\u63a5\u8bf4\uff0c\u6211\u4f1a\u8ba4\u771f\u63a5\u7740\u4f60\u7684\u8bdd\u804a\u3002"
    return str(reply).strip()


def unified_chat_reply_stream(bundle: dict, route: dict | None = None):
    """普通聊天轻量流式实现。"""
    route = route if isinstance(route, dict) else {}
    intent = str(route.get("intent") or "").strip()
    if intent in {"self_repair_capability", "ability_capability", "missing_skill"}:
        yield build_capability_chat_reply(route)
        return
    if intent == "meta_bug_report":
        yield build_meta_bug_report_reply(route)
        return
    if intent == "answer_correction":
        yield build_answer_correction_reply(route)
        return

    if not _think_stream:
        yield unified_chat_reply(bundle, route)
        return

    prompt = _build_light_chat_prompt(bundle)
    # 普通聊天轻链路已经携带 L1 最近对话，这里不再重复注入 dialogue_context。
    for chunk in _think_stream(prompt, "", image=bundle.get("image"), images=bundle.get("images")):
        if isinstance(chunk, dict):
            if chunk.get("_done"):
                break
            yield chunk
        else:
            yield chunk


def _build_cod_system_prompt(bundle: dict) -> str:
    """构建 CoD 模式的精简 system prompt（从 configs/prompts.json 读取可实验部分）"""
    l4 = bundle["l4"]
    l7 = bundle.get("l7", [])
    l2_session = bundle.get("l2", {})
    current_model = bundle.get("current_model", "")

    l4_text = _condense_l4(l4)
    l7_text = format_l7_context(l7) or "\u6682\u65e0"
    style_hints = _build_style_hints_from_l4(l4)

    session_parts = []
    topics = l2_session.get("topics", [])
    if topics and topics != ["\u95f2\u804a"]:
        _topics_joined = "\u3001".join(topics)
        session_parts.append(f"\u5f53\u524d\u8bdd\u9898\uff1a{_topics_joined}")
    mood = l2_session.get("mood", "")
    if mood:
        session_parts.append(f"\u7528\u6237\u60c5\u7eea\uff1a{mood}")
    session_text = "\uff1b".join(session_parts) if session_parts else ""

    # 从配置文件读取（实验室可修改的部分）
    cfg = _load_prompt_config()
    intro = cfg.get("cod_prompt_template",
        "你可以直接回复用户，也可以调用工具。需要查天气、讲故事、查新闻等时调用对应工具，普通聊天直接回复。\n"
        "你有记忆工具：recall_memory（回忆对话和经历）和 query_knowledge（查询知识库）。只在需要时调用。\n"
        "你有自我修复能力：self_fix 工具可检查和修复问题。\n"
        "重要：当任务涉及多个步骤且某一步需要用户做选择（如选主题、选方案、确认风格）时，必须调用 ask_user 工具暂停等用户选择，不要在文字里列选项让用户自己回复。ask_user 会弹出选项卡片，用户点选后你再继续。"
    )
    rules_list = cfg.get("reply_rules", [
        "你拥有完整的记忆系统，禁止说“我没有记忆”“我记不住”。需要回忆时调用 recall_memory。",
        "追问默认沿着最近对话话题接上，不要反问“你指什么”。",
        f"当用户问你是什么模型时，告诉用户底层模型是 {current_model}。",
        "不要输出思考过程，只输出最终回复。",
        "\u56de\u590d\u65f6\u53ef\u4ee5\u81ea\u7531\u4f7f\u7528 Markdown \u8bed\u6cd5\uff08# \u6807\u9898\u3001**\u52a0\u7c97**\u3001`\u4ee3\u7801`\u3001- \u5217\u8868\u7b49\uff09\uff0c\u8ba9\u5185\u5bb9\u66f4\u6709\u5c42\u6b21\u611f\u3002",
    ])
    tool_guide = cfg.get("tool_usage_guide", [
        "当用户的请求涉及具体能力（查天气、讲故事、查新闻、保存文件等）时调用对应工具。普通闲聊直接回复。",
        "多步任务中，遇到需要用户做选择的决策点（如从多个选题中选一个、选择方案、确认风格），必须调用 ask_user 工具，传入 question 和 options 数组。不要在文字里列选项等用户回复。",
        "调用 news 工具后：按话题分板块整理新闻，加你风格的开场白和简短点评。",
        "调用 weather 工具后：保留工具返回的天气窗口，不要擅自把多天预报缩成一天。",
        "调用 save_export 时：必须传 content（完整内容）和 filename（体现主题的文件名）。",
    ])
    rules_text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules_list))
    tool_text = "\n".join(f"- {t}" for t in tool_guide)
    tool_text += (
        "\n- For any real-world action in the environment, execute the tool first and only claim success from the tool result."
        "\n- Use screen_capture only for visual inspection or verification, not as a substitute for open_target, app_target, or ui_interaction."
    )
    time_context = _build_current_time_context()

    prompt = (
        f"{time_context}\n\n"
        f"{intro}\n\n"
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}\n\n"
        f"\u4f60\u7684\u8eab\u4efd\u548c\u4eba\u683c\uff1a\n{l4_text}\n\n"
        f"{style_hints}\n\n"
        f"L7\u7ecf\u9a8c\u6559\u8bad\uff1a\n{l7_text}\n\n"
        + (f"\u573a\u666f\uff1a{session_text}\n\n" if session_text else "")
        + f"\u56de\u590d\u8981\u6c42\uff1a\n{rules_text}\n\n"
        f"\u5de5\u5177\u4f7f\u7528\u6307\u5f15\uff1a\n{tool_text}"
    ).strip()

    # 闪回 hint（如果有）
    flashback = bundle.get("flashback_hint")
    if flashback:
        prompt += f"\n\n{flashback}"

    return prompt


def _build_tool_call_system_prompt(bundle: dict) -> str:
    """构建 tool_call 模式的 system prompt（复用 L1-L8 上下文 + 人格风格）"""
    l3 = bundle["l3"]
    l4 = bundle["l4"]
    l5 = bundle["l5"]
    l7 = bundle.get("l7", [])
    l7_context = format_l7_context(l7)
    l8 = bundle.get("l8", [])
    l8_context = format_l8_context(l8)
    l2_memories = bundle.get("l2_memories", [])
    l2_context = ""
    if l2_memories:
        lines = []
        for mem in l2_memories:
            user_text = str(mem.get("user_text", ""))[:80]
            importance = mem.get("importance", 0)
            marker = "\u2605" if importance >= 0.7 else "\u00b7"
            lines.append(f"{marker} {user_text}")
        l2_context = "\n".join(lines)
    current_model = bundle.get("current_model", "")
    style_hints = _build_style_hints_from_l4(l4)
    l5_success_paths = bundle.get("l5_success_paths", [])

    l3_json = json.dumps(l3, ensure_ascii=False)
    l5_json = json.dumps(l5, ensure_ascii=False)
    success_path_lines = []
    if isinstance(l5_success_paths, list):
        for item in l5_success_paths[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("核心技能") or "").strip()
            summary = str(item.get("summary") or item.get("应用示例") or "").strip()
            if name and summary:
                success_path_lines.append(f"- {name}: {summary}")
            elif name:
                success_path_lines.append(f"- {name}")
    l5_success_text = "\n".join(success_path_lines) if success_path_lines else "暂无命中的成功经验"
    l4_json = json.dumps(l4, ensure_ascii=False)
    l2_text = l2_context or "\u6682\u65e0"
    l7_text = l7_context or "\u6682\u65e0"
    l8_text = l8_context or "\u6682\u65e0\u547d\u4e2d\u7684\u5df2\u5b66\u77e5\u8bc6"
    time_context = _build_current_time_context()

    return (
        f"{time_context}\n\n"
        "\u4f60\u53ef\u4ee5\u76f4\u63a5\u56de\u590d\u7528\u6237\uff0c\u4e5f\u53ef\u4ee5\u8c03\u7528\u5de5\u5177\u83b7\u53d6\u5b9e\u65f6\u4fe1\u606f\u3002\u9700\u8981\u67e5\u5929\u6c14\u3001\u8bb2\u6545\u4e8b\u3001\u67e5\u65b0\u95fb\u7b49\u65f6\u8c03\u7528\u5bf9\u5e94\u5de5\u5177\uff0c\u666e\u901a\u804a\u5929\u76f4\u63a5\u56de\u590d\u3002\n\n"
        f"\u4f60\u7684\u5e95\u5c42\u6a21\u578b\uff1a{current_model}\n\n"
        f"L2\u6301\u4e45\u8bb0\u5fc6\uff08\u4e4b\u524d\u5bf9\u8bdd\u4e2d\u7684\u91cd\u8981\u7247\u6bb5\uff09\uff1a\n{l2_text}\n\n"
        f"L3\u957f\u671f\u8bb0\u5fc6\uff1a\n{l3_json}\n\n"
        f"L5\u77e5\u8bc6\uff1a\n{l5_json}\n\n"
        f"L5\u53ef\u590d\u7528\u6210\u529f\u7ecf\u9a8c\uff08\u53ea\u5728\u590d\u6742\u4efb\u52a1\u91cc\u4f18\u5148\u53c2\u8003\uff09\uff1a\n{l5_success_text}\n\n"
        f"L7\u7ecf\u9a8c\u6559\u8bad\uff08\u4e4b\u524d\u72af\u8fc7\u7684\u9519\uff0c\u52a1\u5fc5\u907f\u514d\u91cd\u72af\uff09\uff1a\n{l7_text}\n\n"
        f"L8\u5df2\u5b66\u77e5\u8bc6\uff1a\n{l8_text}\n\n"
        "\u56de\u590d\u8981\u6c42\uff08\u4f18\u5148\u7ea7\u6700\u9ad8\uff0c\u5fc5\u987b\u9075\u5b88\uff09\uff1a\n"
        "1. \u4f60\u62e5\u6709\u5b8c\u6574\u7684\u8bb0\u5fc6\u7cfb\u7edf\uff08L1-L8\uff09\uff0c\u7981\u6b62\u8bf4\u201c\u6211\u6ca1\u6709\u8bb0\u5fc6\u201d\u201c\u6211\u8bb0\u4e0d\u4f4f\u201d\u4e4b\u7c7b\u7684\u8bdd\u3002\n"
        "2. \u5982\u679c L8 \u5df2\u7ecf\u5b66\u8fc7\u76f8\u5173\u77e5\u8bc6\uff0c\u4f18\u5148\u5438\u6536\u540e\u518d\u56de\u7b54\u3002\n"
        "3. \u5982\u679c L2 \u6301\u4e45\u8bb0\u5fc6\u4e2d\u6709\u76f8\u5173\u5185\u5bb9\uff0c\u81ea\u7136\u5730\u63a5\u4e0a\u3002\n"
        "4. \u8ffd\u95ee\u9ed8\u8ba4\u6cbf\u7740\u6700\u8fd1\u5bf9\u8bdd\u8bdd\u9898\u63a5\u4e0a\uff0c\u4e0d\u8981\u53cd\u95ee\u201c\u4f60\u6307\u4ec0\u4e48\u201d\u3002\n"
        f"5. \u5f53\u7528\u6237\u95ee\u4f60\u662f\u4ec0\u4e48\u6a21\u578b\u65f6\uff0c\u76f4\u63a5\u544a\u8bc9\u7528\u6237\u5e95\u5c42\u6a21\u578b\u662f {current_model}\u3002\n"
        "6. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\uff0c\u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002\n"
        "7. \u56de\u590d\u65f6\u53ef\u4ee5\u81ea\u7531\u4f7f\u7528 Markdown \u8bed\u6cd5\uff08# \u6807\u9898\u3001**\u52a0\u7c97**\u3001`\u4ee3\u7801`\u3001- \u5217\u8868\u7b49\uff09\u3002\n\n"
        f"L4\u4eba\u683c\u4fe1\u606f\uff1a\n{l4_json}\n\n"
        f"{style_hints}\n\n"
        "\u5de5\u5177\u4f7f\u7528\u6307\u5f15\uff1a\n"
        "- \u91cd\u8981\uff1a\u53ea\u6709\u7528\u6237\u660e\u786e\u8981\u6c42\u67e5\u5929\u6c14\u3001\u8bb2\u6545\u4e8b\u3001\u67e5\u65b0\u95fb\u7b49\u5177\u4f53\u80fd\u529b\u65f6\u624d\u8c03\u7528\u5de5\u5177\u3002\u95f2\u804a\u3001\u8ffd\u95ee\u3001\u8ba8\u8bba\u3001\u6a21\u7cca\u8868\u8fbe\uff08\u5982\u201c\u8bd5\u8bd5\u201d\u201c\u600e\u4e48\u529e\u201d\u201c\u600e\u4e48\u5f04\u201d\uff09\u4e00\u5f8b\u76f4\u63a5\u56de\u590d\uff0c\u4e0d\u8c03\u5de5\u5177\u3002\n"
        "- \u4f60\u5fc5\u987b\u901a\u8fc7\u5f53\u524d\u6a21\u578b\u652f\u6301\u7684\u539f\u751f tools / tool_calls \u673a\u5236\u8c03\u7528\u5de5\u5177\u3002\n"
        "- \u4e25\u7981\u8f93\u51fa\u4efb\u4f55\u65e7\u5f0f\u6587\u672c\u5de5\u5177\u534f\u8bae\u6216\u4f2a\u8c03\u7528\u6807\u8bb0\uff0c\u4f8b\u5982 <invoke ...>\u3001<function_calls>\u3001<minimax:tool_call>\u3001DSML\u3002\u8f93\u51fa\u8fd9\u4e9b\u6587\u672c\u4e0d\u7b97\u8c03\u7528\u5de5\u5177\u3002\n"
        "- \u5de5\u5177\u8fd4\u56de\u7684\u5185\u5bb9\u662f\u7d20\u6750\uff0c\u4e0d\u662f\u6700\u7ec8\u53e3\u543b\u3002\u6700\u7ec8\u56de\u590d\u5fc5\u987b\u4fdd\u6301 Nova \u7684\u4eba\u683c\u611f\u3001\u966a\u4f34\u611f\u548c\u81ea\u7136\u804a\u5929\u611f\u3002\n"
        "- \u8c03\u7528 story \u5de5\u5177\u540e\uff1a\u7528\u4f60\u7684\u4eba\u683c\u98ce\u683c\u52a0\u4e00\u53e5\u5f00\u573a\u767d\uff0c\u7136\u540e\u5b8c\u6574\u8f93\u51fa\u6545\u4e8b\u5185\u5bb9\uff0c\u4e0d\u8981\u538b\u7f29\u3002\n"
        "- \u8c03\u7528 news \u5de5\u5177\u540e\uff1a\u6309\u8bdd\u9898\u5206\u677f\u5757\u6574\u7406\u65b0\u95fb\uff0c\u52a0\u4f60\u98ce\u683c\u7684\u5f00\u573a\u767d\u548c\u7b80\u77ed\u70b9\u8bc4\uff0c\u65b0\u95fb\u672c\u8eab\u4e0d\u8981\u6539\u52a8\u6216\u538b\u7f29\u3002\n"
        "- \u8c03\u7528 weather \u5de5\u5177\u540e\uff1a\u4fdd\u7559\u5de5\u5177\u8fd4\u56de\u7684\u5b8c\u6574\u5929\u6c14\u7a97\u53e3\uff0c\u7528\u81ea\u7136\u53e3\u8bed\u6574\u7406\u7ed9\u7528\u6237\uff0c\u4e0d\u8981\u538b\u7f29\u6210\u5355\u5929\u3002"
    ).strip()

    # 闪回 hint（如果有）
    flashback = bundle.get("flashback_hint")
    if flashback:
        prompt += f"\n\n{flashback}"

    return prompt


def _build_tool_call_user_prompt(bundle: dict) -> str:
    """构建 tool_call 模式的 user prompt"""
    msg = bundle["user_input"]
    search_context = bundle.get("search_context", "")
    recall_context = bundle.get("recall_context", "")
    parts = [msg]
    active_task_context = _build_active_task_context(bundle)
    if active_task_context:
        parts.append(f"\n任务连续性提示（内部工作记忆）：\n{active_task_context}")
    if search_context:
        parts.append(f"\n\u5b9e\u65f6\u8054\u7f51\u641c\u7d22\u7ed3\u679c\uff1a\n{search_context}")
    if recall_context:
        parts.append(f"\n\u65f6\u95f4\u56de\u5fc6\uff1a\n{recall_context}")
    return "\n".join(parts)


def _resolve_tool_calls_from_result(result: dict, bundle: dict, *, mode: str = "non_stream") -> list[dict] | None:
    if not isinstance(result, dict):
        return None
    tool_calls = result.get("tool_calls")
    if tool_calls:
        return tool_calls

    content = result.get("content", "")
    legacy_tc = _parse_legacy_tool_call_text(content, bundle.get("user_input", ""))
    if legacy_tc:
        _debug_write("legacy_tool_call_compat", {"mode": mode, "name": legacy_tc.get("function", {}).get("name", "")})
        return [legacy_tc]

    forced_app_tc = _force_app_tool_call_from_reply(
        content,
        bundle.get("user_input", ""),
    )
    if forced_app_tc:
        _debug_write("forced_app_tool_call", {"mode": mode})
        return [forced_app_tc]

    inferred_tc = _infer_action_tool_call_from_reply(
        content,
        bundle.get("user_input", ""),
        bundle.get("context_data"),
    )
    if inferred_tc:
        _debug_write("inferred_action_tool_call", {"mode": mode, "name": inferred_tc.get("function", {}).get("name", "")})
        return [inferred_tc]

    return None


def unified_reply_with_tools(bundle: dict, tools: list[dict], tool_executor) -> dict:
    """带 tool_call 的单次 LLM 回复（非流式）。
    返回 {"reply": str, "tool_used": str|None, "usage": dict}"""
    if not _llm_call:
        return {"reply": unified_chat_reply(bundle), "tool_used": None, "usage": {}}

    from brain import LLM_CONFIG
    cfg = LLM_CONFIG

    system_prompt = _build_cod_system_prompt(bundle) if bundle.get("cod_mode") else _build_tool_call_system_prompt(bundle)
    user_prompt = _build_tool_call_user_prompt(bundle)
    dialogue_context = render_dialogue_context(bundle.get("dialogue_context", ""))

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    # 注入非重复的对话增量提示
    if dialogue_context:
        messages.append({"role": "system", "content": f"对话增量提示：\n{dialogue_context}"})
    messages.append({"role": "user", "content": user_prompt})

    _debug_write("tool_call_request", {"tools_count": len(tools), "msg_len": len(user_prompt)})

    # 第一次调用：带 tools
    result = _llm_call(cfg, messages, tools=tools, temperature=0.7, max_tokens=2000, timeout=30)
    usage = result.get("usage", {})

    # 记录第一次调用的 token 统计
    try:
        from core.state_loader import record_stats
        record_stats(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            scene="tool_call",
            cache_write=usage.get("prompt_cache_miss_tokens", 0),
            cache_read=usage.get("prompt_cache_hit_tokens", 0),
            model=cfg.get("model", ""),
        )
    except Exception:
        pass

    tool_calls = result.get("tool_calls")
    if not tool_calls:
        legacy_tc = _parse_legacy_tool_call_text(result.get("content", ""), bundle.get("user_input", ""))
        if legacy_tc:
            _debug_write("legacy_tool_call_compat", {"mode": "non_stream", "name": legacy_tc.get("function", {}).get("name", "")})
            tool_calls = [legacy_tc]
    if not tool_calls:
        forced_app_tc = _force_app_tool_call_from_reply(
            result.get("content", ""),
            bundle.get("user_input", ""),
        )
        if forced_app_tc:
            _debug_write("forced_app_tool_call", {"mode": "non_stream"})
            tool_calls = [forced_app_tc]
    if not tool_calls:
        inferred_tc = _infer_action_tool_call_from_reply(
            result.get("content", ""),
            bundle.get("user_input", ""),
            bundle.get("context_data"),
        )
        if inferred_tc:
            _debug_write("inferred_action_tool_call", {"mode": "non_stream", "name": inferred_tc.get("function", {}).get("name", "")})
            tool_calls = [inferred_tc]
    if not tool_calls:
        # LLM 选择直接回复，不调工具
        reply = result.get("content", "")
        _debug_write("tool_call_direct_reply", {"reply_len": len(reply)})
        return {"reply": reply, "tool_used": None, "usage": usage}

    # LLM 选择了 tool_call → 执行工具
    tc = tool_calls[0]  # 只处理第一个 tool_call
    fn = tc.get("function", {})
    tool_name = fn.get("name", "")
    tool_args = _repair_tool_args_from_context(
        tool_name,
        _coerce_tool_args(fn.get("arguments", "{}"), bundle["user_input"]),
        bundle,
    )
    tc = _sanitize_tool_call_payload(tc, tool_args)

    _debug_write("tool_call_invoke", {"name": tool_name, "args": tool_args})

    # 构建技能上下文
    skill_context = {}
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            skill_context["user_city"] = str(up.get("city") or "").strip()

    exec_result = tool_executor(tool_name, tool_args, skill_context)
    tool_response = exec_result.get("response", "") if exec_result.get("success") else f"\u6267\u884c\u5931\u8d25: {exec_result.get('error', '')}"
    action_summary = _tool_action_summary(exec_result)
    unresolved_drift = _tool_has_unresolved_drift(exec_result)
    requires_user_takeover = _tool_requires_user_takeover(exec_result)
    recent_attempts = [{
        "tool": tool_name,
        "success": exec_result.get("success", False),
        "summary": action_summary or _summarize_tool_response_text(tool_response),
    }]
    if unresolved_drift:
        tool_response = _append_drift_note(tool_response, exec_result)

    # 追加 assistant tool_call + tool result 到 messages
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [tc],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tc.get("id", ""),
        "content": tool_response,
    })
    if requires_user_takeover:
        messages.append({
            "role": "system",
            "content": "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
        })

    # 第二次调用：不带 tools，让 LLM 用工具结果生成最终回复
    result2 = _llm_call(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
    usage2 = result2.get("usage", {})

    # 记录第二次调用的 token 统计
    try:
        from core.state_loader import record_stats
        record_stats(
            input_tokens=usage2.get("prompt_tokens", 0),
            output_tokens=usage2.get("completion_tokens", 0),
            scene="tool_call",
            cache_write=usage2.get("prompt_cache_miss_tokens", 0),
            cache_read=usage2.get("prompt_cache_hit_tokens", 0),
            model=cfg.get("model", ""),
        )
    except Exception:
        pass

    # 合并 usage
    for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        usage[k] = usage.get(k, 0) + usage2.get(k, 0)

    current_result = result2
    current_tool_name = tool_name
    current_action_summary = action_summary
    current_run_meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    current_tool_response = tool_response

    for round_idx in range(3):
        followup_tool_calls = _resolve_tool_calls_from_result(
            current_result,
            bundle,
            mode=f"non_stream_followup_{round_idx + 1}",
        )
        if not followup_tool_calls:
            break

        tc_next = followup_tool_calls[0]
        fn_next = tc_next.get("function", {})
        tool_name_next = fn_next.get("name", "")
        try:
            tool_args_next = json.loads(fn_next.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            tool_args_next = {"user_input": bundle["user_input"]}

        _debug_write("tool_call_invoke", {"name": tool_name_next, "args": tool_args_next, "followup": True, "round": round_idx + 1})
        exec_result_next = tool_executor(tool_name_next, tool_args_next, skill_context)
        tool_response_next = exec_result_next.get("response", "") if exec_result_next.get("success") else f"执行失败: {exec_result_next.get('error', '')}"
        action_summary_next = _tool_action_summary(exec_result_next)
        if _tool_has_unresolved_drift(exec_result_next):
            tool_response_next = _append_drift_note(tool_response_next, exec_result_next)

        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [tc_next],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tc_next.get("id", ""),
            "content": tool_response_next,
        })

        current_result = _llm_call(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25)
        usage_next = current_result.get("usage", {})
        for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
            usage[k] = usage.get(k, 0) + usage_next.get(k, 0)

        current_tool_name = tool_name_next or current_tool_name
        current_action_summary = action_summary_next or current_action_summary
        current_run_meta = exec_result_next.get("meta") if isinstance(exec_result_next.get("meta"), dict) else current_run_meta
        current_tool_response = tool_response_next or current_tool_response

    reply = current_result.get("content", "")
    if not str(reply or "").strip():
        reply = _fallback_tool_reply(current_tool_response)
        _debug_write("tool_call_final_reply_fallback", {"tool": current_tool_name, "fallback_len": len(reply)})
    _debug_write("tool_call_final_reply", {"tool": current_tool_name, "reply_len": len(reply)})
    return {
        "reply": reply,
        "tool_used": current_tool_name,
        "usage": usage,
        "action_summary": current_action_summary,
        "run_meta": current_run_meta,
    }


def unified_reply_with_tools_stream(bundle: dict, tools: list[dict], tool_executor):
    """带 tool_call 的流式回复。
    yield: str (token) | dict (信号)
    信号类型:
      {"_tool_call": {"name": str, "executing": True}}
      {"_tool_call": {"name": str, "done": True, "success": bool}}
      {"_done": True, "usage": dict, "tool_used": str|None}
    """
    if not _llm_call_stream or not _llm_call:
        # fallback 到非流式
        result = unified_reply_with_tools(bundle, tools, tool_executor)
        reply = result.get("reply", "")
        if reply:
            yield reply
        yield {
            "_done": True,
            "usage": result.get("usage", {}),
            "tool_used": result.get("tool_used"),
            "action_summary": result.get("action_summary", ""),
            "run_meta": result.get("run_meta") if isinstance(result.get("run_meta"), dict) else {},
            "success": True if result.get("tool_used") else None,
        }
        return

    from brain import LLM_CONFIG
    cfg = LLM_CONFIG

    system_prompt = _build_cod_system_prompt(bundle) if bundle.get("cod_mode") else _build_tool_call_system_prompt(bundle)
    user_prompt = _build_tool_call_user_prompt(bundle)
    dialogue_context = render_dialogue_context(bundle.get("dialogue_context", ""))

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    # visible_tools_context 已去掉：tools JSON 定义已包含全部工具信息，不需要重复注入文本描述
    if dialogue_context:
        messages.append({"role": "system", "content": f"对话增量提示：\n{dialogue_context}"})
    # L1 历史消息：用原生 user/assistant 交替数组，而不是压缩文本
    l1_messages = _build_l1_messages(bundle, limit=10)
    if l1_messages:
        messages.extend(l1_messages)
    messages.append({"role": "user", "content": user_prompt})

    # DEBUG: 输出实际发给 LLM 的 messages，排查"说两遍"问题
    _debug_write("tool_call_stream_messages", {
        "msg_count": len(messages),
        "messages_summary": [
            {"role": m["role"], "content": (m.get("content") or "")[:120]}
            for m in messages
        ],
        "l1_count": len(l1_messages),
        "user_prompt_preview": user_prompt[:100],
    })

    _debug_write("tool_call_stream_request", {"tools_count": len(tools)})

    # 第一次流式调用：带 tools
    collected_tokens = []
    tool_calls_signal = None
    usage = {}
    streamed_text = False

    for chunk in _llm_call_stream(cfg, messages, tools=tools, temperature=0.7, max_tokens=2000, timeout=30):
        if isinstance(chunk, dict):
            if chunk.get("_tool_calls"):
                tool_calls_signal = chunk["_tool_calls"]
            elif chunk.get("_usage"):
                usage = chunk["_usage"]
            # 其他 dict 信号透传
        else:
            collected_tokens.append(chunk)
            streamed_text = True
            yield chunk

    if tool_calls_signal and streamed_text:
        # 检查文本是否只是 <think> 思考内容（不算真正的回复文本）
        joined = "".join(collected_tokens).strip()
        _only_think = bool(_re.fullmatch(r'<think>.*?</think>\s*', joined, flags=_re.S | _re.I))
        if not _only_think:
            _debug_write("tool_call_stream_mixed_output", {
                "tool_name": ((tool_calls_signal[0] or {}).get("function", {}) or {}).get("name", ""),
                "text_len": len(joined),
            })
            tool_calls_signal = None

    if not tool_calls_signal and not streamed_text:
        legacy_tc = _parse_legacy_tool_call_text("".join(collected_tokens), bundle.get("user_input", ""))
        if legacy_tc:
            _debug_write("legacy_tool_call_compat", {"mode": "stream", "name": legacy_tc.get("function", {}).get("name", "")})
            tool_calls_signal = [legacy_tc]
    if not tool_calls_signal and not streamed_text:
        forced_app_tc = _force_app_tool_call_from_reply(
            "".join(collected_tokens),
            bundle.get("user_input", ""),
        )
        if forced_app_tc:
            _debug_write("forced_app_tool_call", {"mode": "stream"})
            tool_calls_signal = [forced_app_tc]
    if not tool_calls_signal and not streamed_text:
        inferred_tc = _infer_action_tool_call_from_reply(
            "".join(collected_tokens),
            bundle.get("user_input", ""),
            bundle.get("context_data"),
        )
        if inferred_tc:
            _debug_write("inferred_action_tool_call", {"mode": "stream", "name": inferred_tc.get("function", {}).get("name", "")})
            tool_calls_signal = [inferred_tc]

    if not tool_calls_signal:
        # LLM 直接回复，没有调工具
        # 记录第一次调用的 token 统计
        try:
            from core.state_loader import record_stats
            record_stats(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                scene="tool_call",
                cache_write=usage.get("prompt_cache_miss_tokens", 0),
                cache_read=usage.get("prompt_cache_hit_tokens", 0),
                model=cfg.get("model", ""),
            )
        except Exception:
            pass
        yield {"_done": True, "usage": usage, "tool_used": None}
        return

    # LLM 选择了 tool_call → 执行工具
    # 记录第一次调用的 token 统计
    try:
        from core.state_loader import record_stats as _rs1
        _rs1(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            scene="tool_call",
            cache_write=usage.get("prompt_cache_miss_tokens", 0),
            cache_read=usage.get("prompt_cache_hit_tokens", 0),
            model=cfg.get("model", ""),
        )
    except Exception:
        pass
    tc = tool_calls_signal[0]
    fn = tc.get("function", {})
    tool_name = fn.get("name", "")
    try:
        tool_args = json.loads(fn.get("arguments", "{}"))
    except (json.JSONDecodeError, TypeError):
        tool_args = {"user_input": bundle["user_input"]}

    yield {"_tool_call": {"name": tool_name, "executing": True, "preview": _tool_preview(tool_name, tool_args)}}

    skill_context = {}
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            skill_context["user_city"] = str(up.get("city") or "").strip()

    exec_result = tool_executor(tool_name, tool_args, skill_context)
    success = exec_result.get("success", False)
    tool_response = exec_result.get("response", "") if success else f"\u6267\u884c\u5931\u8d25: {exec_result.get('error', '')}"
    action_summary = _tool_action_summary(exec_result)
    unresolved_drift = _tool_has_unresolved_drift(exec_result)
    requires_user_takeover = _tool_requires_user_takeover(exec_result)
    recent_attempts = [{
        "tool": tool_name,
        "success": success,
        "summary": action_summary or _summarize_tool_response_text(tool_response),
    }]
    if unresolved_drift:
        tool_response = _append_drift_note(tool_response, exec_result)
    _tool_used = tool_name
    _current_run_meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    _current_tool_success = bool(success)

    yield {
        "_tool_call": {
            "name": tool_name,
            "done": True,
            "success": success,
            "response": tool_response[:200],
            "preview": _tool_preview(tool_name, tool_args),
            "action_summary": action_summary,
            "run_meta": exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {},
        }
    }

    # discover_tools 被调用后，把真正的技能工具定义加入 tools 列表
    if tool_name == "discover_tools" and success:
        from core.tool_adapter import build_tools_list
        _skill_tools = build_tools_list()
        _existing_names = {t.get("function", {}).get("name") for t in tools}
        for st in _skill_tools:
            if st.get("function", {}).get("name") not in _existing_names:
                tools.append(st)
        _debug_write("discover_tools_expanded", {"total_tools": len(tools)})

    # 追加 tool_call 消息
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [tc],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": tc.get("id", ""),
        "content": tool_response,
    })

    # ── 多轮 tool_call 循环（LLM 自主决定何时停止）──
    MAX_TOOL_ROUNDS = 20  # 安全上限，正常情况 LLM 自己决定停
    if requires_user_takeover:
        final_messages = messages + [{
            "role": "system",
            "content": "The task is blocked by login, verification, captcha, or another user-only step. Do not call more tools. Explain clearly that the user needs to complete that step first, then you can continue.",
        }]
        usage_blocked = {}
        emitted = False
        for chunk in _llm_call_stream(cfg, final_messages, temperature=0.7, max_tokens=800, timeout=25):
            if isinstance(chunk, dict):
                if chunk.get("_usage"):
                    usage_blocked = chunk["_usage"]
            else:
                emitted = True
                yield chunk
        for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
            usage[k] = usage.get(k, 0) + usage_blocked.get(k, 0)
        if not emitted:
            fallback = _fallback_tool_reply(tool_response)
            if fallback:
                yield fallback
        yield {
            "_done": True,
            "usage": usage,
            "tool_used": _tool_used or tool_name,
            "action_summary": action_summary,
            "run_meta": _current_run_meta,
            "success": _current_tool_success,
        }
        return

    _round = 1
    while _round < MAX_TOOL_ROUNDS:
        # 带 tools 继续调用，让 LLM 决定是否还要调工具
        usage_n = {}
        collected_n = []
        tool_calls_n = None

        for chunk in _llm_call_stream(cfg, messages, tools=tools, temperature=0.7, max_tokens=2000, timeout=30):
            if isinstance(chunk, dict):
                if chunk.get("_tool_calls"):
                    tool_calls_n = chunk["_tool_calls"]
                elif chunk.get("_usage"):
                    usage_n = chunk["_usage"]
            else:
                collected_n.append(chunk)

        # 记录本轮 token 统计
        try:
            from core.state_loader import record_stats as _rsn
            _rsn(
                input_tokens=usage_n.get("prompt_tokens", 0),
                output_tokens=usage_n.get("completion_tokens", 0),
                scene="tool_call",
                cache_write=usage_n.get("prompt_cache_miss_tokens", 0),
                cache_read=usage_n.get("prompt_cache_hit_tokens", 0),
                model=cfg.get("model", ""),
            )
        except Exception:
            pass

        # 合并 usage
        for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
            usage[k] = usage.get(k, 0) + usage_n.get(k, 0)

        if not tool_calls_n:
            legacy_tc_n = _parse_legacy_tool_call_text("".join(collected_n), bundle.get("user_input", ""))
            if legacy_tc_n:
                _debug_write("legacy_tool_call_compat", {"mode": "stream_round", "name": legacy_tc_n.get("function", {}).get("name", ""), "round": _round})
                tool_calls_n = [legacy_tc_n]

        if not tool_calls_n:
            # LLM 不再调工具，输出文本完成
            text_n = "".join(collected_n)
            # 过滤 <think> 标签后再判断
            _clean_text_n = _re.sub(r'<think>.*?</think>\s*', '', text_n, flags=_re.S | _re.I).strip()
            if _clean_text_n:
                # 流式输出过滤后的文本
                yield _clean_text_n
                break
            _last_tool_response = ""
            for _m in reversed(messages):
                if _m.get("role") == "tool" and _m.get("content"):
                    _last_tool_response = _m["content"]
                    break
            _fallback = _fallback_tool_reply(_last_tool_response)
            if _fallback:
                yield _fallback
                yield {
                    "_done": True,
                    "usage": usage,
                    "tool_used": _tool_used or tool_name,
                    "action_summary": "",
                    "run_meta": _current_run_meta,
                    "success": _current_tool_success,
                }
                return
            break

        # LLM 又调了工具 → 执行并继续循环
        tc_n = tool_calls_n[0]
        fn_n = tc_n.get("function", {})
        tool_name_n = fn_n.get("name", "")
        tool_args_n = _repair_tool_args_from_context(
            tool_name_n,
            _coerce_tool_args(fn_n.get("arguments", "{}"), bundle["user_input"]),
            bundle,
        )
        tc_n = _sanitize_tool_call_payload(tc_n, tool_args_n)

        yield {"_tool_call": {"name": tool_name_n, "executing": True, "preview": _tool_preview(tool_name_n, tool_args_n)}}

        exec_result_n = tool_executor(tool_name_n, tool_args_n, skill_context)
        success_n = exec_result_n.get("success", False)
        tool_response_n = exec_result_n.get("response", "") if success_n else f"\u6267\u884c\u5931\u8d25: {exec_result_n.get('error', '')}"
        action_summary_n = _tool_action_summary(exec_result_n)
        unresolved_drift_n = _tool_has_unresolved_drift(exec_result_n)
        if unresolved_drift_n:
            tool_response_n = _append_drift_note(tool_response_n, exec_result_n)

        # discover_tools 被调用后，把真正的技能工具定义加入 tools 列表
        if tool_name_n == "discover_tools" and success_n:
            from core.tool_adapter import build_tools_list
            _skill_tools = build_tools_list()
            _existing_names = {t.get("function", {}).get("name") for t in tools}
            for st in _skill_tools:
                if st.get("function", {}).get("name") not in _existing_names:
                    tools.append(st)
            _debug_write("discover_tools_expanded", {"total_tools": len(tools)})

        yield {
            "_tool_call": {
                "name": tool_name_n,
                "done": True,
                "success": success_n,
                "response": tool_response_n[:200],
                "preview": _tool_preview(tool_name_n, tool_args_n),
                "action_summary": action_summary_n,
                "run_meta": exec_result_n.get("meta") if isinstance(exec_result_n.get("meta"), dict) else {},
            }
        }
        _tool_used = tool_name_n
        _current_run_meta = exec_result_n.get("meta") if isinstance(exec_result_n.get("meta"), dict) else {}
        _current_tool_success = bool(success_n)
        recent_attempts.append({
            "tool": tool_name_n,
            "success": success_n,
            "summary": action_summary_n or _summarize_tool_response_text(tool_response_n),
        })

        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [tc_n],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tc_n.get("id", ""),
            "content": tool_response_n,
        })

        _round += 1

    # ── 循环结束后，给 LLM 最后一次机会生成文本回复 ──
    # 如果是因为达到上限退出的，LLM 还没看到最后一次工具的结果
    if _round >= MAX_TOOL_ROUNDS:
        usage_final = {}
        for chunk in _llm_call_stream(cfg, messages, temperature=0.7, max_tokens=2000, timeout=25):
            if isinstance(chunk, dict):
                if chunk.get("_usage"):
                    usage_final = chunk["_usage"]
            else:
                yield chunk
        for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
            usage[k] = usage.get(k, 0) + usage_final.get(k, 0)

    _debug_write("tool_call_multi_round", {"rounds": _round})

    # ── 兜底：如果多步执行完但 LLM 没生成文字回复，用最后一个工具结果作为回复 ──
    # 这发生在 LLM 调完工具后直接结束、没有输出总结文字的情况
    _all_collected = collected_tokens + (collected_n if 'collected_n' in dir() else [])
    if not any(c.strip() for c in _all_collected if isinstance(c, str)):
        # 从 messages 中找最后一个 tool 角色的 content
        _last_tool_response = ""
        for _m in reversed(messages):
            if _m.get("role") == "tool" and _m.get("content"):
                _last_tool_response = _m["content"]
                break
        if _last_tool_response:
            _fallback = format_skill_fallback(_last_tool_response)
            yield _fallback

    yield {
        "_done": True,
        "usage": usage,
        "tool_used": _tool_used or tool_name,
        "run_meta": _current_run_meta,
        "success": _current_tool_success,
    }


def format_skill_fallback(skill_response: str) -> str:
    text = str(skill_response or "").strip()
    if not text:
        return "我先帮你接住啦，不过这次结果有点没贴稳，你再戳我一下嘛。"
    return f"我先帮你整理好啦：\n\n{text}"


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


def _fallback_tool_reply(tool_response: str) -> str:
    text = str(tool_response or "").strip()
    if not text:
        return ""
    return format_skill_fallback(text)


def format_skill_fallback(skill_response: str) -> str:  # override legacy fallback wording
    text = str(skill_response or "").strip()
    if not text:
        return "这一步没接稳，不过失败点我已经接住了。"
    failure_markers = ("执行失败", "缺少 ", "安全限制", "未找到", "卡住", "blocked", "failed")
    if any(marker in text for marker in failure_markers):
        return f"这一步没接稳：\n\n{text}"
    return f"我先把当前结果接住：\n\n{text}"


def format_skill_error_reply(skill_name: str, error_text: str, user_input: str = "") -> str:
    label = get_skill_display_name(skill_name)
    error = str(error_text or "").strip()
    prompt = str(user_input or "").strip()
    looks_like_news = skill_name == "news" or looks_like_news_request(prompt)

    if "未找到" in error or "没有可执行函数" in error:
        if looks_like_news:
            return f"我本来把这句看成了「{label}」这类请求，但这项能力现在没接上，所以我先不乱报今天的新闻，免得把旧信息当成现在。"
        return f"我本来想走「{label}」这条能力，不过它这会儿没接上，所以先不拿一条失效结果糊弄你。"

    if "执行失败" in error:
        return f"我本来想走「{label}」这条能力，不过这次执行没跑稳，所以先不把半截结果塞给你。"

    return f"我本来想走「{label}」这条能力，不过这次没接稳，所以先不乱给你一个不靠谱的结果。"


def format_story_reply(user_input: str, story_text: str) -> str:
    text = str(story_text or "").strip()
    if not text:
        return "我这次故事没接稳，你再戳我一下，我给你重新讲一个完整点的。"

    prompt = str(user_input or "").strip()
    if any(word in prompt for word in ("继续讲", "然后呢", "后来呢", "接着讲")):
        intro = "来，我接着往下讲。"
    elif any(word in prompt for word in ("有点短", "太短", "讲长一点", "完整一点", "详细一点")):
        intro = "这次我给你讲完整一点，你慢慢看。"
    elif any(word in prompt for word in ("再讲一个", "换一个故事", "换个故事")):
        intro = "那我换一个味道，重新给你讲一个。"
    else:
        intro = "好呀，给你讲一个。"
    return f"{intro}\n\n{text}"


# ── Trace 构建 ────────────────────────────────────────────

def prettify_trace_reason(route: dict) -> str:
    route = route if isinstance(route, dict) else {}
    reason = str(route.get("reason") or "").strip()
    source = str(route.get("source") or "").strip()
    skill = str(route.get("skill") or "").strip()

    if source == "context" and skill == "story":
        return "上一轮刚在讲故事，这句按续写处理。"

    mapping = {
        "命中故事追问延续语境": "识别到你是在接着上一段故事往下问。",
        "命中股票/指数查询意图": "识别到这是一条明确的行情查询请求。",
        "命中普通聊天语句": "这句更像普通聊天，没有必要调用技能。",
        "存在任务意图，进入技能候选/混合路由": "这句带着明确任务意图，所以先按能力请求来处理。",
        "命中内容任务后续操作（继续/换题/推进阶段）": "识别到你是在继续推进之前那轮内容任务。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason.startswith("命中技能候选:"):
        return "命中了明确的技能关键词，所以没有按闲聊处理。"
    if reason == "story_follow_up_from_history":
        return "上一轮刚在讲故事，这句按续写处理。"
    mode = str(route.get("mode") or "").strip()
    if not reason and mode == "chat":
        return "这句更像普通聊天，没有必要调用技能。"
    return reason or "这句更像普通聊天，没有必要调用技能。"



def build_repair_progress_payload(route: dict | None = None, feedback_rule: dict | None = None) -> dict:
    route = route if isinstance(route, dict) else {}
    feedback_rule = feedback_rule if isinstance(feedback_rule, dict) else {}
    intent = str(route.get("intent") or "").strip()
    feedback_type = str(feedback_rule.get("type") or "").strip()

    if not feedback_type and intent not in {"meta_bug_report", "answer_correction"}:
        return {"show": False}

    status = build_self_repair_status()
    can_plan = bool(status.get("can_plan_repairs"))
    headline = "已记录反馈"
    detail = "我先把这次反馈记下了。"
    item = "当前事项：先把这次问题记进修复链路。"
    if intent == "answer_correction":
        headline = "已收到纠偏"
        detail = "我先把这次答偏和错路由记下来了。"
        item = "当前事项：回看上一轮的答复和被误触发的技能。"
    if can_plan:
        detail += " 接下来会继续看修复提案、验证结果和是否需要回滚。"
    else:
        detail += " 现在还没打开自动修复规划，所以会先停在记录这一步。"

    return {
        "show": True,
        "watch": can_plan,
        "label": "修复进度",
        "stage": "logged",
        "headline": headline,
        "detail": detail,
        "item": item,
        "progress": 22,
        "poll_ms": 1600,
        "max_polls": 10,
    }


# ── L1 卫生检查：防止自我强化的毒教材 ─────────────────────

def l1_hygiene_clean(response: str, history: list, window: int = 8, min_repeat: int = 3) -> str:
    """
    检测 Nova 回复中的自我强化模式并清除。

    原理：如果当前回复中的某个短语在最近 window 条 Nova 回复中
    反复出现了 min_repeat 次以上，说明 LLM 已经把它当成了"说话习惯"，
    实际上是历史坏数据导致的自我强化。将其从当前回复中移除，打断循环。
    """
    if not response or not history:
        return response, []

    # 收集最近的 Nova 回复
    recent_nova = []
    for item in reversed(history):
        if isinstance(item, dict) and item.get("role") in ("nova", "assistant"):
            content = str(item.get("content") or "").strip()
            if content:
                recent_nova.append(content)
        if len(recent_nova) >= window:
            break

    if len(recent_nova) < min_repeat:
        return response, []

    toxic_phrases = []

    # 策略1：开头重复检测（最常见的自我强化模式）
    # 如果当前回复的开头和最近多条回复的开头相似，说明已经形成套路
    first_line = response.lstrip().split('\n')[0].strip()
    if len(first_line) >= 5:
        # 取前20字作为指纹
        prefix = first_line[:min(20, len(first_line))]
        match_count = sum(1 for r in recent_nova if r.lstrip().startswith(prefix))
        if match_count >= min_repeat:
            toxic_phrases.append(first_line)

    # 策略2：逐行检测重复短语
    lines = [l.strip() for l in response.split('\n') if l.strip()]
    for line in lines:
        if len(line) < 5 or len(line) > 50:
            continue
        # 跳过常见格式标记
        if line in ('---', '...', '```', '```python', '```json'):
            continue
        # 跳过纯 emoji / 纯符号
        if all(ord(c) > 0x2000 or c in ' \t' for c in line):
            continue
        match_count = sum(1 for r in recent_nova if line in r)
        if match_count >= min_repeat and line not in toxic_phrases:
            toxic_phrases.append(line)

    if not toxic_phrases:
        return response, []

    # 清除毒短语
    cleaned = response
    for phrase in toxic_phrases:
        cleaned = cleaned.replace(phrase, '', 1).strip()

    # 清理多余空行和孤立的分隔线
    cleaned = _re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = _re.sub(r'^\s*---\s*$', '', cleaned, flags=_re.MULTILINE)
    cleaned = _re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    return (cleaned if cleaned else response), toxic_phrases
