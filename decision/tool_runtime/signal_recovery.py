"""Compatibility recovery for legacy and inferred tool signals."""


def contains_legacy_tool_markup(text: str, *, legacy_tool_markup_re) -> bool:
    return bool(legacy_tool_markup_re.search(str(text or "")))


def parse_legacy_tool_call_text(
    text: str,
    user_input: str = "",
    *,
    legacy_tool_block_re,
    legacy_minimax_tool_re,
    legacy_json_tool_re,
    re_mod,
    json_module,
) -> dict | None:
    raw = str(text or "")
    tool_name = ""
    args = {}

    match = legacy_tool_block_re.search(raw)
    if match:
        block = match.group(1)
        tool_match = re_mod.search(r'tool\s*=>\s*"([^"]+)"', block, flags=re_mod.I)
        if tool_match:
            tool_name = str(tool_match.group(1) or "").strip()
            for key, value in re_mod.findall(r'--([A-Za-z0-9_]+)\s+"([^"]*)"', block):
                args[str(key).strip()] = value

    if not tool_name:
        minimax_match = legacy_minimax_tool_re.search(raw)
        if minimax_match:
            block = minimax_match.group(1)
            invoke_match = re_mod.search(r'<\s*invoke[^>]*name\s*=\s*"([^"]+)"[^>]*>', block, flags=re_mod.I)
            if invoke_match:
                tool_name = str(invoke_match.group(1) or "").strip()
                for key, value in re_mod.findall(
                    r'<\s*parameter[^>]*name\s*=\s*"([^"]+)"[^>]*>\s*(.*?)\s*<\s*/\s*parameter\s*>',
                    block,
                    flags=re_mod.I | re_mod.S,
                ):
                    args[str(key).strip()] = re_mod.sub(r"\s+", " ", str(value or "")).strip()

    if not tool_name:
        json_match = legacy_json_tool_re.search(raw)
        if json_match:
            block = str(json_match.group(1) or "").strip()
            payload = None
            try:
                payload = json_module.loads(block)
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
            "arguments": json_module.dumps(args, ensure_ascii=False),
        },
    }


def infer_action_tool_call_from_reply(
    reply_text: str,
    user_input: str = "",
    context: dict | None = None,
    *,
    re_mod,
    json_module,
) -> dict | None:
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

    url_match = re_mod.search(r'https?://[^\s`<>"\]]+', raw_reply, flags=re_mod.I)
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
                    "arguments": json_module.dumps(args, ensure_ascii=False),
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
            "arguments": json_module.dumps(args, ensure_ascii=False),
        },
    }


def force_app_tool_call_from_reply(reply_text: str, user_input: str = "", *, json_module) -> dict | None:
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
            "arguments": json_module.dumps({"user_input": raw_input}, ensure_ascii=False),
        },
    }


def tool_has_unresolved_drift(exec_result: dict) -> bool:
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


def append_drift_note(tool_response: str, exec_result: dict) -> str:
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


def tool_requires_user_takeover(exec_result: dict) -> bool:
    if not isinstance(exec_result, dict):
        return False
    meta = exec_result.get("meta") if isinstance(exec_result.get("meta"), dict) else {}
    drift = meta.get("drift") if isinstance(meta.get("drift"), dict) else {}
    post = meta.get("post_condition") if isinstance(meta.get("post_condition"), dict) else {}
    reason = str(drift.get("reason") or post.get("drift") or "").strip().lower()
    hint = str(drift.get("repair_hint") or post.get("hint") or "").strip().lower()
    return reason in {"auth_required", "login_required", "verification_required", "captcha_required"} or hint in {"user_login_required", "user_verification_required"}
