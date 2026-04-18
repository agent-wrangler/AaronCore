"""Protocol-context helpers for post-LLM tool runtime."""

from pathlib import Path
import re as _re


PROTOCOL_CONTEXT_SKILLS = {
    "folder_explore",
    "open_target",
    "save_export",
    "file_copy",
    "file_move",
    "file_delete",
    "app_target",
    "ui_interaction",
    "apply_unified_diff",
    "edit_file",
    "search_replace",
    "write_file",
}

PROTOCOL_DEFAULT_OPTIONS = {
    "folder_explore": "inspect",
    "open_target": "open",
    "save_export": "save",
    "file_copy": "copy",
    "file_move": "move",
    "file_delete": "delete",
    "apply_unified_diff": "apply_unified_diff",
    "edit_file": "edit_file",
    "search_replace": "search_replace",
    "write_file": "write_file",
    "app_target": "launch",
    "ui_interaction": "ui_interact",
}

PROTOCOL_CONTEXT_MANIFESTS = {
    "folder_explore": {"context_need": ["Desktop_Files"]},
    "open_target": {"context_need": ["Desktop_Files"]},
}

_FILE_LIKE_TOOLS = {"write_file", "edit_file", "search_replace", "apply_unified_diff"}
_GENERIC_SHELL_TAILS = {"desktop", "documents", "downloads"}
_DIRECT_FOLLOWUP_COMMANDS = {
    "continue",
    "resume",
    "again",
    "\u7ee7\u7eed",
    "\u63a5\u7740",
}
_FOLLOWUP_RESUME_CUES = (
    "continue",
    "resume",
    "again",
    "\u7ee7\u7eed",
    "\u63a5\u7740",
)
_FOLLOWUP_REFERENCE_CUES = (
    "same",
    "previous",
    "that",
    "this",
    "it",
    "there",
    "\u4e4b\u524d",
    "\u521a\u624d",
    "\u4e0a\u6b21",
    "\u90a3\u4e2a",
    "\u8fd9\u4e2a",
    "\u5b83",
    "\u90a3\u91cc",
)
_FOLLOWUP_FS_FOCUS_CUES = (
    "where",
    "open",
    "show",
    "check",
    "look",
    "browse",
    "inside",
    "path",
    "folder",
    "directory",
    "file",
    "\u5728\u54ea",
    "\u54ea",
    "\u8def\u5f84",
    "\u6253\u5f00",
    "\u770b",
    "\u68c0\u67e5",
    "\u91cc\u9762",
    "\u6587\u4ef6",
    "\u6587\u4ef6\u5939",
    "\u76ee\u5f55",
)
_RECENT_PATH_PATTERNS = (
    _re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+\.(?:md|html|txt|json|py|js|css)', _re.I),
    _re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+', _re.I),
)


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


def _normalize_protocol_remember_path(
    raw_path: str,
    *,
    prefer_file_resolution: bool = False,
    resolve_user_file_target,
    is_allowed_user_target,
) -> str:
    path = str(raw_path or "").strip()
    if not path or path.startswith(("http://", "https://")):
        return ""
    try:
        resolved = resolve_user_file_target(path) if prefer_file_resolution else Path(path).resolve()
    except Exception:
        resolved = None
    if resolved and is_allowed_user_target(resolved):
        return str(resolved)
    return path


def _extract_protocol_result_fs_target(
    name: str,
    ctx: dict,
    result: dict,
    *,
    default_option: str,
    resolve_user_file_target,
    is_allowed_user_target,
) -> dict | None:
    ctx = ctx if isinstance(ctx, dict) else {}
    result = result if isinstance(result, dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    action = meta.get("action") if isinstance(meta.get("action"), dict) else {}
    action_target = str(action.get("target") or "").strip()
    action_target_kind = str(action.get("target_kind") or "").strip().lower()
    prefer_file_resolution = name in _FILE_LIKE_TOOLS or action_target_kind == "file"

    candidates = []
    if action_target and action_target_kind in {"file", "folder", "directory"}:
        candidates.append(action_target)
    if prefer_file_resolution:
        candidates.extend(
            [
                str(ctx.get("file_path") or "").strip(),
                str(ctx.get("path") or "").strip(),
                str(ctx.get("target") or "").strip(),
                str(ctx.get("filename") or "").strip(),
            ]
        )
    else:
        current_target = ctx.get("fs_target") if isinstance(ctx.get("fs_target"), dict) else {}
        candidates.extend(
            [
                str(current_target.get("path") or "").strip(),
                str(ctx.get("path") or "").strip(),
                str(ctx.get("source") or "").strip(),
                str(ctx.get("target") or "").strip(),
            ]
        )

    seen = set()
    for candidate in candidates:
        normalized = _normalize_protocol_remember_path(
            candidate,
            prefer_file_resolution=prefer_file_resolution,
            resolve_user_file_target=resolve_user_file_target,
            is_allowed_user_target=is_allowed_user_target,
        )
        lowered = normalized.replace("/", "\\").lower()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        return {"path": normalized, "option": default_option, "source": "tool_runtime"}
    return None


def _extract_recent_context_paths(context: dict | None) -> list[str]:
    context = context if isinstance(context, dict) else {}
    recent_history = context.get("recent_history") if isinstance(context.get("recent_history"), list) else []
    paths = []
    seen = set()
    for item in reversed(recent_history):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        for pattern in _RECENT_PATH_PATTERNS:
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
            path_obj = Path(str(raw).replace("\\", "/"))
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


def _extract_protocol_candidate_path(name: str, values: dict | None) -> str:
    values = values if isinstance(values, dict) else {}
    if name in _FILE_LIKE_TOOLS:
        return str(values.get("file_path") or values.get("path") or values.get("target") or "").strip()
    if name in {"file_copy", "file_move", "file_delete", "save_export", "folder_explore", "open_target"}:
        return str(values.get("path") or values.get("source") or values.get("file_path") or values.get("target") or "").strip()
    if name == "app_target":
        return str(values.get("path") or values.get("target") or values.get("app") or "").strip()
    if name == "ui_interaction":
        return str(values.get("target") or values.get("window_title") or "").strip()
    return ""


def _is_generic_shell_directory(path: str) -> bool:
    raw = str(path or "").strip()
    if not raw:
        return False
    try:
        tail = Path(raw.replace("/", "\\")).name.strip().lower()
    except Exception:
        return False
    return tail in _GENERIC_SHELL_TAILS


def _normalize_followup_text(user_input: str) -> str:
    raw = str(user_input or "").strip().lower()
    if not raw:
        return ""
    return _re.sub(r"[^\w\u4e00-\u9fff]+", " ", raw).strip()


def _contains_followup_cue(raw: str, cues: tuple[str, ...] | set[str]) -> bool:
    return bool(raw) and any(cue in raw for cue in cues)


def _looks_like_short_followup(raw: str) -> bool:
    if not raw or "\n" in raw or len(raw) > 72:
        return False
    return len(raw.split()) <= 8


def _looks_like_referential_followup(user_input: str) -> bool:
    raw = _normalize_followup_text(user_input)
    if not raw:
        return False
    if raw in _DIRECT_FOLLOWUP_COMMANDS:
        return True
    if not _looks_like_short_followup(raw):
        return False
    has_resume = _contains_followup_cue(raw, _FOLLOWUP_RESUME_CUES)
    has_reference = _contains_followup_cue(raw, _FOLLOWUP_REFERENCE_CUES)
    has_fs_focus = _contains_followup_cue(raw, _FOLLOWUP_FS_FOCUS_CUES)
    if has_reference and has_fs_focus:
        return True
    if has_resume and (has_reference or has_fs_focus):
        return True
    return False


def _allow_generic_target_reuse(user_input: str, explicit_target: dict | None = None) -> bool:
    explicit_target = explicit_target if isinstance(explicit_target, dict) else {}
    if str(explicit_target.get("path") or "").strip():
        return True
    return _looks_like_referential_followup(user_input)


def apply_protocol_context(
    name: str,
    ctx: dict,
    user_input: str,
    tool_args: dict | None = None,
    *,
    resolve_user_file_target,
    is_allowed_user_target,
) -> dict:
    if name not in PROTOCOL_CONTEXT_SKILLS:
        return ctx

    default_option = PROTOCOL_DEFAULT_OPTIONS.get(name, "inspect")
    tool_args = tool_args if isinstance(tool_args, dict) else {}
    context_data = ctx.get("context_data") if isinstance(ctx.get("context_data"), dict) else {}
    current_candidate_path = _extract_protocol_candidate_path(name, tool_args)
    resolved_current_target = None
    if current_candidate_path and not current_candidate_path.startswith(("http://", "https://")):
        resolved_current_target = {"path": current_candidate_path, "option": default_option, "source": "tool_args"}
    allow_generic_reuse = _allow_generic_target_reuse(user_input, resolved_current_target)
    blocked_generic_target = False

    fs_target = _normalize_protocol_fs_target(ctx.get("fs_target"), default_option=default_option)
    if fs_target and _is_generic_shell_directory(str(fs_target.get("path") or "")) and not allow_generic_reuse:
        fs_target = None
        blocked_generic_target = True
        ctx.pop("fs_target", None)
        if _is_generic_shell_directory(str(ctx.get("path") or "")):
            ctx["path"] = ""
    if not fs_target:
        inherited_context_target = _normalize_protocol_fs_target(
            context_data.get("fs_target"),
            default_option=default_option,
        )
        if inherited_context_target and _is_generic_shell_directory(
            str(inherited_context_target.get("path") or "")
        ) and not allow_generic_reuse:
            inherited_context_target = None
            blocked_generic_target = True
            context_data = dict(context_data)
            context_data.pop("fs_target", None)
        fs_target = inherited_context_target

    try:
        from core.context_pull import pull_context_data

        pulled = pull_context_data(user_input or current_candidate_path, PROTOCOL_CONTEXT_MANIFESTS.get(name, {}))
    except Exception:
        pulled = {}
    if isinstance(pulled, dict):
        context_data = _merge_context_dict(context_data, pulled)
        pulled_target = _normalize_protocol_fs_target(pulled.get("fs_target"), default_option=default_option)
        if not resolved_current_target and pulled_target:
            resolved_current_target = pulled_target

    if resolved_current_target:
        fs_target = resolved_current_target

    if not fs_target:
        task_plan = ctx.get("task_plan") if isinstance(ctx.get("task_plan"), dict) else {}
        if task_plan:
            try:
                from core.task_store import get_structured_fs_target_for_task_plan

                task_target = get_structured_fs_target_for_task_plan(task_plan)
            except Exception:
                task_target = None
            candidate_target = _normalize_protocol_fs_target(task_target, default_option=default_option)
            if candidate_target and _is_generic_shell_directory(
                str(candidate_target.get("path") or "")
            ) and not allow_generic_reuse:
                candidate_target = None
                blocked_generic_target = True
            fs_target = candidate_target

    if not fs_target:
        inferred_dir = _infer_recent_directory_from_context(ctx)
        if inferred_dir and not (_is_generic_shell_directory(inferred_dir) and not allow_generic_reuse):
            fs_target = {"path": inferred_dir, "option": default_option, "source": "recent_history"}
        elif inferred_dir:
            blocked_generic_target = True

    if not fs_target:
        try:
            from core.task_store import get_latest_structured_fs_target

            latest_fs_target = get_latest_structured_fs_target()
        except Exception:
            latest_fs_target = None
        candidate_target = _normalize_protocol_fs_target(latest_fs_target, default_option=default_option)
        if candidate_target and _is_generic_shell_directory(
            str(candidate_target.get("path") or "")
        ) and not allow_generic_reuse:
            candidate_target = None
            blocked_generic_target = True
        fs_target = candidate_target

    if fs_target:
        ctx["fs_target"] = fs_target
        if resolved_current_target:
            ctx["path"] = str(fs_target.get("path") or "").strip()
        else:
            ctx["path"] = str(ctx.get("path") or fs_target.get("path") or "").strip()
        context_data = _merge_context_dict(context_data, {"fs_target": fs_target})
        if resolved_current_target:
            context_data["fs_target"] = dict(fs_target)
    elif blocked_generic_target:
        ctx.pop("fs_target", None)
        if _is_generic_shell_directory(str(ctx.get("path") or "")):
            ctx["path"] = ""
        if isinstance(context_data, dict):
            context_data = dict(context_data)
            context_data.pop("fs_target", None)

    if context_data:
        ctx["context_data"] = context_data
    elif "context_data" in ctx:
        ctx.pop("context_data", None)
    if user_input and "last_user_input" not in ctx:
        ctx["last_user_input"] = user_input
    return ctx


def remember_protocol_target(
    name: str,
    ctx: dict,
    result: dict,
    *,
    resolve_user_file_target,
    is_allowed_user_target,
) -> None:
    if name not in PROTOCOL_CONTEXT_SKILLS:
        return
    if not isinstance(ctx, dict) or not isinstance(result, dict):
        return

    default_option = PROTOCOL_DEFAULT_OPTIONS.get(name, "inspect")
    if not result.get("success") and name not in _FILE_LIKE_TOOLS:
        return

    fs_target = _extract_protocol_result_fs_target(
        name,
        ctx,
        result,
        default_option=default_option,
        resolve_user_file_target=resolve_user_file_target,
        is_allowed_user_target=is_allowed_user_target,
    )
    if not fs_target:
        return

    ctx["fs_target"] = fs_target
    ctx["path"] = str(fs_target.get("path") or "").strip()
    context_data = ctx.get("context_data") if isinstance(ctx.get("context_data"), dict) else {}
    ctx["context_data"] = _merge_context_dict(context_data, {"fs_target": fs_target})
    task_plan = ctx.get("task_plan") if isinstance(ctx.get("task_plan"), dict) else {}
    if task_plan:
        try:
            from core.task_store import remember_fs_target_for_task_plan

            remember_fs_target_for_task_plan(task_plan, fs_target)
        except Exception:
            pass
