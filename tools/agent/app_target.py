import os
import subprocess
import time
from pathlib import Path

from core.fs_protocol import build_operation_result
from core.target_protocol import _PINYIN_MAP, resolve_local_app_reference, resolve_target_reference
from decision.tool_runtime.runtime_control import cooperative_sleep, raise_if_cancelled

try:
    import pygetwindow as gw

    _HAS_PYGETWINDOW = True
except ImportError:
    _HAS_PYGETWINDOW = False


_REVERSE_PINYIN = {}
for _cn, _py in _PINYIN_MAP.items():
    _REVERSE_PINYIN[_py.lower()] = _cn


def _expand_window_keywords(keywords: list[str]) -> list[str]:
    expanded = set()
    for kw in keywords or []:
        if not kw:
            continue
        lowered = kw.lower()
        expanded.add(kw)
        expanded.add(lowered)
        for cn, py in _PINYIN_MAP.items():
            if cn in kw:
                expanded.add(py)
                expanded.add(py.lower())
        for py, cn in _REVERSE_PINYIN.items():
            if py in lowered:
                expanded.add(cn)
    return [item for item in expanded if item]


def _get_all_windows() -> list[str]:
    if not _HAS_PYGETWINDOW:
        return []
    try:
        return [w.title for w in gw.getAllWindows() if w.title and w.title.strip()]
    except Exception:
        return []


def _find_window(keywords: list[str]) -> str:
    if not _HAS_PYGETWINDOW:
        return ""
    try:
        windows = [w.title for w in gw.getAllWindows() if w.title and w.title.strip()]
    except Exception:
        return ""
    for title in windows:
        lowered = title.lower()
        if any(keyword.lower() in lowered for keyword in (keywords or []) if keyword):
            return title
    return ""


def _find_new_window(before_titles: set[str], ignore_keywords: list[str] | None = None) -> str:
    if not _HAS_PYGETWINDOW:
        return ""
    try:
        current = [w.title for w in gw.getAllWindows() if w.title and w.title.strip()]
    except Exception:
        return ""
    ignore = {keyword.lower() for keyword in (ignore_keywords or []) if keyword}
    for title in current:
        if title in before_titles:
            continue
        if title.lower() in ignore:
            continue
        if len(title.strip()) > 1:
            return title
    return ""


def _resolve_app_target(raw: str, context: dict) -> dict:
    direct_target = str(context.get("target") or context.get("app") or "").strip()
    direct_path = str(context.get("path") or "").strip()
    if direct_path and Path(direct_path).exists():
        return {
            "target_type": "app",
            "value": direct_path,
            "label": direct_target or Path(direct_path).stem,
            "resolution": "resolved",
            "source": "tool_args",
        }
    if direct_target:
        local_direct = resolve_local_app_reference(direct_target, context)
        if local_direct.get("target_type") in {"app", "window"}:
            return local_direct

    fs_action = context.get("fs_action") if isinstance(context.get("fs_action"), dict) else {}
    pre_resolved_target = fs_action.get("target") if isinstance(fs_action.get("target"), dict) else {}

    if pre_resolved_target.get("path") and Path(str(pre_resolved_target.get("path"))).exists():
        return {
            "target_type": "app",
            "value": str(pre_resolved_target.get("path")),
            "label": str(pre_resolved_target.get("app") or pre_resolved_target.get("path", "")),
            "resolution": "resolved",
            "source": "context_pre_resolved",
        }

    local_hint = str(pre_resolved_target.get("app") or raw or "").strip()
    if local_hint:
        local_resolved = resolve_local_app_reference(local_hint, context)
        if local_resolved.get("target_type") in {"app", "window"}:
            return local_resolved

    fallback_hint = str(pre_resolved_target.get("app") or raw or "").strip()
    return resolve_target_reference(fallback_hint, context)


def _launch_probe_schedule() -> list[float]:
    return [0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.0, 1.25, 1.5, 1.5]


def _restore_or_activate_window(title: str, context: dict | None = None) -> str:
    if not (_HAS_PYGETWINDOW and title):
        return "failed"
    try:
        wins = gw.getWindowsWithTitle(title)
        if not wins:
            return "failed"
        win = wins[0]
        was_minimized = bool(getattr(win, "isMinimized", False))
        if was_minimized:
            try:
                win.restore()
                cooperative_sleep(0.2, context, detail="app_target cancelled during window restore")
            except Exception:
                pass
        try:
            win.activate()
            cooperative_sleep(0.3, context, detail="app_target cancelled during window activation")
        except Exception:
            return "restored" if was_minimized else "failed"
        return "restored" if was_minimized else "focused"
    except Exception:
        return "failed"


def execute(query, context=None):
    raw = str(query or "").strip()
    context = context if isinstance(context, dict) else {}
    raise_if_cancelled(context, detail="app_target cancelled before start")

    is_close = any(
        token in raw
        for token in ("关闭", "退出", "杀掉", "结束", "close", "kill", "quit", "exit")
    )

    resolved = _resolve_app_target(raw, context)

    if is_close:
        if resolved.get("target_type") == "window":
            title = str(resolved.get("value") or "").strip()
            try:
                wins = gw.getWindowsWithTitle(title) if _HAS_PYGETWINDOW else []
                if wins:
                    wins[0].close()
                    cooperative_sleep(0.5, context, detail="app_target cancelled during window close verification")
                    still = _find_window([title])
                    if not still:
                        return build_operation_result(
                            f"已关闭窗口：`{title}`",
                            expected_state="window_closed",
                            observed_state="window_closed",
                            repair_succeeded=True,
                            action_kind="close_window",
                            target_kind="window",
                            target=title,
                            outcome="closed",
                            display_hint=f"已关闭窗口：{title}",
                        )
                    return build_operation_result(
                        f"已尝试关闭窗口，但它还在：`{title}`",
                        expected_state="window_closed",
                        observed_state="window_still_open",
                        drift_reason="close_incomplete",
                        repair_hint="retry_or_force_kill",
                        action_kind="close_window",
                        target_kind="window",
                        target=title,
                        outcome="close_incomplete",
                        display_hint=f"关闭窗口未完成：{title}",
                    )
            except Exception as exc:
                return build_operation_result(
                    f"关闭窗口失败：{exc}",
                    expected_state="window_closed",
                    observed_state="close_failed",
                    drift_reason="close_exception",
                    repair_hint="retry_or_force_kill",
                    action_kind="close_window",
                    target_kind="window",
                    target=title,
                    outcome="failed",
                    display_hint=f"关闭窗口失败：{title}",
                )

        if resolved.get("target_type") == "app":
            label = str(resolved.get("label") or "").strip()
            exe_name = f"{label}.exe" if label else ""
            try:
                if exe_name:
                    subprocess.run(
                        ["taskkill", "/f", "/im", exe_name],
                        capture_output=True,
                        timeout=5,
                    )
                cooperative_sleep(0.5, context, detail="app_target cancelled during app close verification")
                still = _find_window([label]) if label else ""
                if not still:
                    return build_operation_result(
                        f"已尝试结束应用：`{label or exe_name}`",
                        expected_state="app_closed",
                        observed_state="app_closed",
                        repair_succeeded=True,
                        action_kind="close_app",
                        target_kind="app",
                        target=label or exe_name,
                        outcome="closed",
                        display_hint=f"已结束应用：{label or exe_name}",
                    )
                return build_operation_result(
                    f"已尝试结束应用，但它还在：`{label or exe_name}`",
                    expected_state="app_closed",
                    observed_state="app_still_running",
                    drift_reason="kill_incomplete",
                    repair_hint="retry_kill",
                    action_kind="close_app",
                    target_kind="app",
                    target=label or exe_name,
                    outcome="close_incomplete",
                    display_hint=f"结束应用未完成：{label or exe_name}",
                )
            except Exception as exc:
                return build_operation_result(
                    f"结束应用失败：{exc}",
                    expected_state="app_closed",
                    observed_state="kill_failed",
                    drift_reason="kill_exception",
                    repair_hint="retry_or_manual_close",
                    action_kind="close_app",
                    target_kind="app",
                    target=label or exe_name,
                    outcome="failed",
                    display_hint=f"结束应用失败：{label or exe_name}",
                )

        return build_operation_result(
            "没有识别到要关闭的应用。",
            expected_state="app_closed",
            observed_state="target_unresolved",
            drift_reason="missing_close_target",
            repair_hint="provide_app_name",
            action_kind="close_app",
            target_kind="app",
            target=raw,
            outcome="unresolved",
            display_hint="没有识别到要关闭的应用",
        )

    if resolved.get("target_type") not in {"app", "window"}:
        return build_operation_result(
            "当前还没有从系统环境里解析出匹配的桌面应用。",
            expected_state="app_running",
            observed_state="app_unresolved",
            drift_reason="missing_app_target",
            repair_hint="provide_clearer_app_reference",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="open_app",
            target_kind="app",
            target=raw,
            outcome="unresolved",
            display_hint="还没有解析出匹配的桌面应用",
        )

    if resolved.get("target_type") == "window":
        target = {
            "label": str(resolved.get("value") or "").strip(),
            "window_keywords": [str(resolved.get("value") or "").strip()],
            "source": "window",
        }
    else:
        label = str(resolved.get("label") or resolved.get("value") or "").strip()
        target = {
            "label": label,
            "path": str(resolved.get("value") or "").strip(),
            "window_keywords": _expand_window_keywords([label]),
            "source": str(resolved.get("source") or "app"),
        }

    existing = _find_window(target.get("window_keywords") or [])
    if existing:
        activation_state = _restore_or_activate_window(existing, context)
        focused = _find_window(target.get("window_keywords") or [])
        if focused:
            if activation_state == "restored":
                reply = f"已恢复并聚焦现有应用窗口：`{focused}`"
                observed_state = "window_restored"
            else:
                reply = f"已找到并聚焦现有应用窗口：`{focused}`"
                observed_state = "window_visible"
            return build_operation_result(
                reply,
                expected_state="app_running",
                observed_state=observed_state,
                repair_attempted=False,
                repair_succeeded=True,
                action_kind="focus_app",
                target_kind="window",
                target=focused,
                outcome="restored" if activation_state == "restored" else "focused_existing",
                display_hint=reply.replace("`", ""),
            )
        return build_operation_result(
            f"已找到应用窗口，但聚焦失败：`{existing}`",
            expected_state="window_focused",
            observed_state="focus_failed",
            drift_reason="focus_failed",
            repair_hint="retry_focus_window",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="focus_app",
            target_kind="window",
            target=existing,
            outcome="focus_failed",
            display_hint=f"聚焦现有窗口失败：{existing}",
        )

    app_path = str(target.get("path") or "").strip()
    if not app_path or not Path(app_path).exists():
        return build_operation_result(
            f"没有找到这个应用的启动入口：`{app_path}`",
            expected_state="app_launchable",
            observed_state="launcher_missing",
            drift_reason="launcher_not_found",
            repair_hint="check_shortcut_or_installation",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="open_app",
            target_kind="app",
            target=target.get("label") or app_path,
            outcome="launcher_missing",
            display_hint=f"没有找到启动入口：{target.get('label') or app_path}",
        )

    before_titles = set(_get_all_windows())

    try:
        os.startfile(app_path)
    except Exception as exc:
        return build_operation_result(
            f"应用启动失败：{exc}",
            expected_state="app_running",
            observed_state="launch_failed",
            drift_reason="os_start_failed",
            repair_hint="retry_or_check_launcher",
            repair_attempted=False,
            repair_succeeded=False,
            action_kind="open_app",
            target_kind="app",
            target=target.get("label") or app_path,
            outcome="failed",
            display_hint=f"启动应用失败：{target.get('label') or app_path}",
        )

    for wait_seconds in _launch_probe_schedule():
        cooperative_sleep(wait_seconds, context, detail="app_target cancelled during launch verification")

        matched = _find_window(target.get("window_keywords") or [])
        if matched:
            return build_operation_result(
                f"已打开应用：`{target.get('label')}`\n窗口：`{matched}`",
                expected_state="app_running",
                observed_state="window_visible",
                repair_attempted=False,
                repair_succeeded=True,
                action_kind="open_app",
                target_kind="app",
                target=target.get("label") or matched,
                outcome="opened_new",
                display_hint=f"已打开应用：{target.get('label') or matched}",
            )

        new_win = _find_new_window(before_titles)
        if new_win:
            return build_operation_result(
                f"已打开应用：`{target.get('label')}`\n窗口：`{new_win}`",
                expected_state="app_running",
                observed_state="window_visible",
                repair_attempted=False,
                repair_succeeded=True,
                action_kind="open_app",
                target_kind="app",
                target=target.get("label") or new_win,
                outcome="opened_new",
                display_hint=f"已打开应用：{target.get('label') or new_win}",
            )

    return build_operation_result(
        f"已尝试启动应用：`{target.get('label')}`，但暂时还没检测到窗口。",
        expected_state="app_running",
        observed_state="window_not_detected",
        drift_reason="window_not_detected",
        repair_hint="retry_or_check_startup_delay",
        repair_attempted=False,
        repair_succeeded=False,
        action_kind="open_app",
        target_kind="app",
        target=target.get("label") or app_path,
        outcome="unconfirmed",
        display_hint=f"已尝试启动应用：{target.get('label') or app_path}",
    )
