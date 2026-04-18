"""Directory-resolution and tool-arg repair helpers for post-LLM runtime."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from protocols.fs import WORKSPACE_ROOT
from protocols.target import extract_explicit_local_path
from tasks.continuity import (
    looks_like_long_referential_followup,
    looks_like_short_referential_followup,
)


_EXPLICIT_LOCATION_REQUEST_PATTERNS = (
    re.compile(r"(?:\u5728\u54ea|\u5728\u54ea\u91cc|\u5728\u54ea\u513f)\s*[？?]?$"),
    re.compile(r"(?:\u6587\u4ef6\u5939|\u76ee\u5f55|\u8def\u5f84|\u4f4d\u7f6e).{0,8}(?:\u5728\u54ea|\u5728\u54ea\u91cc|\u5728\u54ea\u513f|\u53d1\u6211|\u7ed9\u6211|\u544a\u8bc9\u6211)"),
    re.compile(r"(?:\u5b58\u5230\u54ea|\u653e\u5230\u54ea|\u653e\u54ea|\u4fdd\u5b58\u5230\u54ea|\u4fdd\u5b58\u5728\u54ea)"),
    re.compile(r"(?:where is|which folder|which directory|what path|saved where|located where)", re.I),
)
_LOCATION_QUERY_RE = re.compile(
    r"(?:\bwhere\b|\bpath\b|\bfolder\b|\bdirectory\b|\blocation\b|\u54ea|\u8def\u5f84|\u4f4d\u7f6e|\u76ee\u5f55|\u6587\u4ef6\u5939)",
    re.I,
)


def extract_recent_file_paths(bundle: dict) -> list[str]:
    paths = []
    seen = set()
    patterns = (
        re.compile(r'[A-Za-z]:[\\/][^\s`<>"\]]+\.(?:md|html|txt|json|py|js|css)', re.I),
        re.compile(r'(?:\.{0,2}[\\/])?(?:[\w.-]+[\\/])+[\w.-]+\.(?:md|html|txt|json|py|js|css)', re.I),
    )
    for item in reversed(list(bundle.get("l1") or [])):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        for pattern in patterns:
            for match in pattern.findall(content):
                value = str(match).strip().strip(".,;:()[]{}<>\"'")
                if not value:
                    continue
                norm = value.replace("/", "\\")
                if norm.lower().startswith("http\\") or norm.lower().startswith("https\\"):
                    continue
                if norm.lower() in seen:
                    continue
                seen.add(norm.lower())
                paths.append(value)
                if len(paths) >= 6:
                    return paths
    return paths


def workspace_root_anchor() -> str:
    try:
        return str(WORKSPACE_ROOT.resolve())
    except Exception:
        return str(WORKSPACE_ROOT)


def infer_recent_directory_target(
    bundle: dict,
    *,
    extract_recent_file_paths_fn: Callable[[dict], list[str]] | None = None,
) -> str:
    scores: dict[str, int] = {}
    recent_paths = (extract_recent_file_paths_fn or extract_recent_file_paths)(bundle)
    for raw in recent_paths:
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


def looks_like_directory_resolution_request(user_input: str, *, has_structured_target: bool) -> bool:
    raw = str(user_input or "").strip()
    if not raw or not has_structured_target:
        return False
    if re.search(r"[A-Za-z]:[\\/]", raw):
        return False

    if any(pattern.search(raw) for pattern in _EXPLICIT_LOCATION_REQUEST_PATTERNS):
        return True
    if not _LOCATION_QUERY_RE.search(raw):
        return False
    return looks_like_short_referential_followup(raw) or looks_like_long_referential_followup(raw)


def reply_already_contains_location(
    reply_text: str,
    *,
    clean_visible_reply_text: Callable[[str], str],
) -> bool:
    text = clean_visible_reply_text(reply_text)
    if not text:
        return False
    patterns = (
        r"[A-Za-z]:[\\/][^\s`<>\"]+",
        r"(桌面|文档|下载)[/\\][^\s`<>\"]+",
        r"(Desktop|Documents|Downloads)[/\\][^\s`<>\"]+",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def pick_directory_resolution_target(
    bundle: dict,
    *,
    load_task_plan_fs_target: Callable[[dict], str],
    load_context_fs_target: Callable[[dict], str],
    load_latest_structured_fs_target: Callable[[], str],
    infer_recent_directory_target_fn: Callable[[dict], str] | None = None,
    allow_global_fallback: bool = True,
) -> str:
    infer_recent_target = infer_recent_directory_target_fn or infer_recent_directory_target
    candidates = [
        load_task_plan_fs_target(bundle),
        load_context_fs_target(bundle),
        infer_recent_target(bundle),
    ]
    if allow_global_fallback:
        candidates.append(load_latest_structured_fs_target())
    for candidate in candidates:
        path = str(candidate or "").strip()
        if path:
            return path
    return ""


def infer_directory_resolution_tool_call(
    bundle: dict,
    *,
    reply_text: str = "",
    clean_visible_reply_text: Callable[[str], str],
    load_task_plan_fs_target: Callable[[dict], str],
    load_context_fs_target: Callable[[dict], str],
    load_latest_structured_fs_target: Callable[[], str],
    infer_recent_directory_target_fn: Callable[[dict], str] | None = None,
) -> dict | None:
    raw_input = str(bundle.get("user_input") or "").strip()
    target = pick_directory_resolution_target(
        bundle,
        load_task_plan_fs_target=load_task_plan_fs_target,
        load_context_fs_target=load_context_fs_target,
        load_latest_structured_fs_target=load_latest_structured_fs_target,
        infer_recent_directory_target_fn=infer_recent_directory_target_fn,
        allow_global_fallback=False,
    )
    if not target or reply_already_contains_location(
        reply_text,
        clean_visible_reply_text=clean_visible_reply_text,
    ):
        return None
    if not looks_like_directory_resolution_request(raw_input, has_structured_target=True):
        return None
    return {
        "id": "inferred_directory_resolution_tool_call",
        "type": "function",
        "function": {
            "name": "folder_explore",
            "arguments": json.dumps(
                {
                    "path": target,
                    "user_input": raw_input,
                },
                ensure_ascii=False,
            ),
        },
    }


def repair_tool_args_from_context(
    tool_name: str,
    tool_args: dict,
    bundle: dict,
    *,
    load_task_plan_fs_target: Callable[[dict], str],
    load_context_fs_target: Callable[[dict], str],
    load_latest_structured_fs_target: Callable[[], str],
    extract_explicit_local_path_fn: Callable[[str], str] | None = None,
    infer_recent_directory_target_fn: Callable[[dict], str] | None = None,
    extract_recent_file_paths_fn: Callable[[dict], list[str]] | None = None,
) -> dict:
    args = dict(tool_args or {})
    user_input = str(bundle.get("user_input") or "")
    extract_local_path = extract_explicit_local_path_fn or extract_explicit_local_path
    infer_recent_target = infer_recent_directory_target_fn or infer_recent_directory_target
    recent_file_paths = extract_recent_file_paths_fn or extract_recent_file_paths

    if tool_name == "folder_explore":
        explicit_user_target = extract_local_path(user_input)
        target = str(args.get("path") or args.get("target") or "").strip()
        if explicit_user_target:
            target = explicit_user_target
        elif not target:
            target = (
                load_task_plan_fs_target(bundle)
                or load_context_fs_target(bundle)
                or infer_recent_target(bundle)
                or load_latest_structured_fs_target()
                or workspace_root_anchor()
            )
        if target:
            args["path"] = target
        if user_input and "user_input" not in args:
            args["user_input"] = user_input
        return args

    if tool_name != "write_file":
        if user_input and "user_input" not in args:
            args["user_input"] = user_input
        return args

    target = str(
        args.get("file_path")
        or args.get("path")
        or args.get("target")
        or args.get("filename")
        or ""
    ).strip()
    if target and "file_path" not in args:
        args["file_path"] = target

    if not str(args.get("file_path") or "").strip():
        recent_paths = recent_file_paths(bundle)
        if recent_paths:
            candidate = Path(recent_paths[0])
            wants_html = any(token in user_input.lower() for token in ("网页", "html", ".html"))
            if wants_html and candidate.suffix.lower() != ".html":
                candidate = candidate.with_suffix(".html")
            args["file_path"] = str(candidate)

    change_request = str(
        args.get("change_request")
        or args.get("instructions")
        or args.get("problem")
        or args.get("description")
        or ""
    ).strip()
    if change_request and "change_request" not in args:
        args["change_request"] = change_request

    if user_input and "user_input" not in args:
        args["user_input"] = user_input
    return args
