import os
import subprocess
import time

from core.fs_protocol import (
    build_operation_result,
    check_saved_state,
    classify_open_target,
    compose_remote_target_url,
    load_export_state,
)
from core.network_protocol import preflight_remote_access
from core.skills.ui_interaction import submit_browser_search
from decision.tool_runtime.runtime_control import cooperative_sleep, raise_if_cancelled


_BROWSERS = ["chrome.exe", "msedge.exe", "firefox.exe"]


def _hidden_console_kwargs() -> dict:
    if os.name != "nt":
        return {}

    kwargs = {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creationflags:
        kwargs["creationflags"] = creationflags

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass

    return kwargs


def _count_windows(title_hint: str = "") -> int:
    try:
        import pygetwindow as gw

        if title_hint:
            return len([w for w in gw.getAllWindows() if title_hint.lower() in (w.title or "").lower()])
        return len(gw.getAllWindows())
    except Exception:
        return -1


def _check_process_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            **_hidden_console_kwargs(),
        )
        return name.lower() in result.stdout.lower()
    except Exception:
        return False


def _browser_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            **_hidden_console_kwargs(),
        )
        output = result.stdout.lower()
        return any(browser.lower() in output for browser in _BROWSERS)
    except Exception:
        return any(_check_process_running(browser) for browser in _BROWSERS)


def _verify_url_opened(pre_count: int, pre_browser: bool, wait: float = 8.0, context: dict | None = None) -> dict:
    elapsed = 0.0
    interval = 2.0

    while elapsed < wait:
        cooperative_sleep(interval, context, detail="open_target cancelled during browser verification")
        elapsed += interval

        post_count = _count_windows()
        post_browser = _browser_running()
        window_increased = post_count > pre_count if pre_count >= 0 and post_count >= 0 else None
        browser_started = post_browser and not pre_browser

        if window_increased or browser_started:
            return {
                "ok": True,
                "mode": "window_changed" if window_increased else "browser_started",
                "detail": f"窗口数 {pre_count} -> {post_count}，约 {elapsed:.0f} 秒后检测到变化",
            }

    post_count = _count_windows()
    if pre_count >= 0 and post_count >= 0:
        return {
            "ok": False,
            "mode": "no_window_change",
            "detail": f"窗口数未变化（{pre_count} -> {post_count}），等待了约 {wait:.0f} 秒",
        }
    return {"ok": None, "mode": "unverified", "detail": "无法检测到窗口变化"}


def _snapshot_before() -> tuple[int, bool]:
    return _count_windows(), _browser_running()


def _find_browser() -> str | None:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _open_url(url: str) -> str:
    browser = _find_browser()
    if browser:
        try:
            subprocess.Popen([browser, url])
            return browser
        except Exception:
            pass
    os.startfile(url)
    return "startfile"


def _preflight_url_access(url: str) -> dict:
    try:
        return preflight_remote_access(url)
    except Exception as exc:
        return {
            "available": False,
            "source": "exception",
            "error_type": "network_preflight_error",
            "message": str(exc),
            "user_safe_message": f"当前环境暂时访问不了 `{url}`",
            "route": "",
        }


def _resolve_target(query: str, context: dict | None = None) -> tuple[str, str]:
    context = context if isinstance(context, dict) else {}
    direct_target = str(context.get("url") or context.get("path") or context.get("target") or "").strip().strip('"')
    if direct_target:
        if direct_target.startswith(("http://", "https://")):
            return "url", direct_target
        return "path", direct_target

    fs_action = context.get("fs_action") if isinstance(context.get("fs_action"), dict) else {}
    target = fs_action.get("target") if isinstance(fs_action.get("target"), dict) else {}
    url = str(target.get("url") or "").strip()
    path = str(target.get("path") or "").strip()
    if url:
        return "url", url
    if path:
        return "path", path

    raw = str(query or "").strip().strip('"')
    export_state = load_export_state()
    if any(word in raw for word in ("打开保存位置", "打开保存目录", "打开刚才保存的位置")):
        saved_dir = str(export_state.get("last_export_dir") or "").strip()
        if saved_dir:
            return "path", saved_dir
    if any(word in raw for word in ("打开刚才那个结果", "打开刚才保存的文件", "打开刚才导出的文件")):
        saved_path = str(export_state.get("last_export_path") or "").strip()
        if saved_path:
            return "path", saved_path
    if raw.startswith(("http://", "https://")):
        return "url", raw
    return "path", raw if raw else ""


def _url_result(
    reply: str,
    *,
    target: str,
    observed_state: str,
    outcome: str,
    repair_attempted: bool,
    repair_succeeded: bool,
    drift_reason: str = "",
    repair_hint: str = "",
    display_hint: str = "",
    verification_mode: str = "",
    verification_detail: str = "",
) -> dict:
    return build_operation_result(
        reply,
        expected_state="url_opened",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        action_kind="open_url",
        target_kind="url",
        target=target,
        outcome=outcome,
        display_hint=display_hint or reply.replace("`", ""),
        verification_mode=verification_mode,
        verification_detail=verification_detail,
    )


def _local_target_result(
    reply: str,
    *,
    target: str,
    target_kind: str,
    observed_state: str,
    outcome: str,
    repair_attempted: bool,
    repair_succeeded: bool,
    drift_reason: str = "",
    repair_hint: str = "",
    display_hint: str = "",
) -> dict:
    return build_operation_result(
        reply,
        expected_state="target_opened",
        observed_state=observed_state,
        drift_reason=drift_reason,
        repair_hint=repair_hint,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
        action_kind="open_folder" if target_kind == "folder" else "open_file",
        target_kind=target_kind,
        target=target,
        outcome=outcome,
        display_hint=display_hint or reply.replace("`", ""),
    )


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    raise_if_cancelled(context, detail="open_target cancelled before start")
    _, target_value = _resolve_target(query, context)
    if not target_value:
        return build_operation_result(
            "如果目标还不够明确，可以先结合上文，把它补全成具体的文件、文件夹、保存结果或网页地址，再继续打开。",
            expected_state="target_resolved",
            observed_state="target_missing",
            drift_reason="missing_target",
            repair_hint="infer_or_provide_target",
            action_kind="open_target",
            target_kind="target",
            target="",
            outcome="unresolved",
            display_hint="还缺少可以直接打开的明确目标",
        )

    info = classify_open_target(target_value)
    if not info.get("ok"):
        if info.get("repairable") and info.get("repair_target"):
            repaired = classify_open_target(info.get("repair_target"))
            if repaired.get("ok"):
                info = repaired
                target_value = info.get("target", target_value)
        if not info.get("ok"):
            reason = str(info.get("reason") or "").strip()
            target = str(info.get("target") or target_value or "").strip()
            if reason in {"unsupported_url_scheme", "missing_url_scheme"}:
                return build_operation_result(
                    f"暂时只支持打开 http/https 网页：`{target}`",
                    expected_state=str(info.get("expected_state") or "target_opened"),
                    observed_state=str(info.get("observed_state") or "unsupported_scheme"),
                    drift_reason="unsupported_url_scheme",
                    repair_hint=str(info.get("repair_hint") or "use_http_or_https"),
                    action_kind="open_url",
                    target_kind="url",
                    target=target,
                    outcome="blocked",
                    display_hint=f"暂不支持这个网页协议：{target}",
                )
            if reason == "target_not_found":
                return build_operation_result(
                    f"要打开的目标不存在：`{target}`",
                    expected_state=str(info.get("expected_state") or "path_exists"),
                    observed_state=str(info.get("observed_state") or "path_missing"),
                    drift_reason="target_not_found",
                    repair_hint=str(info.get("repair_hint") or "check_or_correct_path"),
                    action_kind="open_target",
                    target_kind="path",
                    target=target,
                    outcome="missing",
                    display_hint=f"没有找到目标：{target}",
                )
            if reason == "dangerous_open_target":
                return build_operation_result(
                    f"这个目标属于高风险可执行或脚本类型，暂不直接打开：`{target}`",
                    expected_state=str(info.get("expected_state") or "safe_target_ready"),
                    observed_state=str(info.get("observed_state") or "dangerous_target_blocked"),
                    drift_reason="dangerous_open_target",
                    repair_hint=str(info.get("repair_hint") or "confirm_or_use_safe_target"),
                    action_kind="open_target",
                    target_kind="path",
                    target=target,
                    outcome="blocked",
                    display_hint=f"目标被安全策略拦下：{target}",
                )
            return build_operation_result(
                "打开失败：目标无效。",
                expected_state="target_valid",
                observed_state="target_invalid",
                drift_reason="invalid_target",
                repair_hint="infer_or_provide_target",
                action_kind="open_target",
                target_kind="target",
                target=str(target_value or ""),
                outcome="invalid",
                display_hint="目标无效，暂时还不能直接打开",
            )

    effective_target = str(info["target"])
    remote_plan = {"url": effective_target, "search_term": "", "composed": False, "strategy": ""}

    if info["target_type"] == "url":
        remote_plan = compose_remote_target_url(info["target"], query)
        effective_target = str(remote_plan.get("url") or info["target"]).strip()
        preflight = _preflight_url_access(effective_target)
        if not preflight.get("available", True):
            return _url_result(
                preflight.get("user_safe_message") or f"当前环境暂时访问不了 `{effective_target}`",
                target=effective_target,
                observed_state="network_unavailable",
                outcome="blocked",
                repair_attempted=False,
                repair_succeeded=False,
                drift_reason=str(preflight.get("error_type") or "network_unavailable"),
                repair_hint="check_network_environment",
                display_hint=f"当前环境访问不了：{effective_target}",
                verification_mode=str(preflight.get("source") or ""),
                verification_detail=str(preflight.get("message") or ""),
            )

    pre_count, pre_browser = _snapshot_before() if info["target_type"] == "url" else (0, False)

    if info["target_type"] == "url":
        raise_if_cancelled(context, detail="open_target cancelled before launching browser")
        _open_url(effective_target)
    else:
        raise_if_cancelled(context, detail="open_target cancelled before opening local target")
        os.startfile(info["target"])

    if info["target_type"] == "url":
        verify = _verify_url_opened(pre_count, pre_browser, context=context)
        if verify.get("ok") is False:
            if pre_browser and _browser_running():
                if remote_plan.get("search_term") and not remote_plan.get("composed"):
                    search_result = submit_browser_search(str(remote_plan.get("search_term") or ""))
                    if bool(search_result.get("repair_succeeded")):
                        return _url_result(
                            f"已在现有浏览器中完成搜索：`{remote_plan['search_term']}`",
                            target=effective_target,
                            observed_state="url_search_submitted",
                            outcome="opened_existing_browser_search_submit",
                            repair_attempted=True,
                            repair_succeeded=True,
                            display_hint=f"已在现有浏览器中完成搜索：{remote_plan['search_term']}",
                            verification_mode="browser_search_submit",
                            verification_detail=str((search_result.get("reply") or "")).strip(),
                        )
                    return _url_result(
                        f"网页已经打开，但搜索还没有完成：`{remote_plan['search_term']}`",
                        target=effective_target,
                        observed_state="search_submit_pending",
                        outcome="opened_search_pending",
                        repair_attempted=True,
                        repair_succeeded=False,
                        drift_reason="search_submit_pending",
                        repair_hint="use_ui_interaction_or_query_url",
                        display_hint=f"网页已经打开，但搜索还没有完成：{remote_plan['search_term']}",
                        verification_mode="browser_search_submit",
                        verification_detail=str((search_result.get("reply") or "")).strip(),
                    )
                return _url_result(
                    f"已在现有浏览器中触发打开：`{effective_target}`",
                    target=effective_target,
                    observed_state="url_opened_unconfirmed",
                    outcome="opened_existing_browser",
                    repair_attempted=False,
                    repair_succeeded=True,
                    repair_hint="check_existing_browser_tab",
                    display_hint=f"已在现有浏览器中触发打开：{effective_target}",
                    verification_mode=str(remote_plan.get("strategy") or verify.get("mode") or "existing_browser"),
                    verification_detail=str(verify.get("detail") or ""),
                )

            pre2, pre2_b = _snapshot_before()
            raise_if_cancelled(context, detail="open_target cancelled before retry")
            _open_url(effective_target)
            verify_retry = _verify_url_opened(pre2, pre2_b, wait=10.0, context=context)
            if verify_retry.get("ok") is False:
                if _browser_running():
                    return _url_result(
                        f"已在现有浏览器标签页中触发打开：`{effective_target}`",
                        target=effective_target,
                        observed_state="url_opened_unconfirmed",
                        outcome="opened_existing_tab",
                        repair_attempted=True,
                        repair_succeeded=True,
                        repair_hint="check_existing_browser_tab",
                        display_hint=f"已在现有浏览器标签页中触发打开：{effective_target}",
                        verification_mode=str(remote_plan.get("strategy") or verify_retry.get("mode") or "existing_browser_tab"),
                        verification_detail=str(verify_retry.get("detail") or ""),
                    )
                return _url_result(
                    f"打开网页失败：浏览器似乎没有响应。目标：`{effective_target}`\n{verify_retry.get('detail', '')}",
                    target=effective_target,
                    observed_state="browser_not_responding",
                    outcome="failed",
                    repair_attempted=True,
                    repair_succeeded=False,
                    drift_reason="url_open_no_window_change",
                    repair_hint="check_default_browser",
                    display_hint=f"打开网页失败：{effective_target}",
                    verification_mode=str(remote_plan.get("strategy") or verify_retry.get("mode") or "no_window_change"),
                    verification_detail=str(verify_retry.get("detail") or ""),
                )
            return _url_result(
                f"已重试并打开网页：`{effective_target}`",
                target=effective_target,
                observed_state="url_opened_after_retry",
                outcome="opened_after_retry",
                repair_attempted=True,
                repair_succeeded=True,
                display_hint=f"已重试并打开网页：{effective_target}",
                verification_mode=str(remote_plan.get("strategy") or verify_retry.get("mode") or "retry_success"),
                verification_detail=str(verify_retry.get("detail") or ""),
            )

        if verify.get("ok") is True:
            reply = f"已打开网页：`{effective_target}`"
            outcome = "opened"
            if verify.get("mode") == "browser_started":
                reply = f"已启动浏览器并打开网页：`{effective_target}`"
                outcome = "opened_new_browser"
            if remote_plan.get("composed") and remote_plan.get("search_term"):
                reply = f"已打开网页并带入搜索内容：`{remote_plan['search_term']}`"
                outcome = "opened_with_query"
            elif remote_plan.get("search_term"):
                search_result = submit_browser_search(str(remote_plan.get("search_term") or ""))
                if bool(search_result.get("repair_succeeded")):
                    return _url_result(
                        f"已打开网页并提交搜索：`{remote_plan['search_term']}`",
                        target=effective_target,
                        observed_state="url_search_submitted",
                        outcome="opened_with_search_submit",
                        repair_attempted=True,
                        repair_succeeded=True,
                        display_hint=f"已打开网页并提交搜索：{remote_plan['search_term']}",
                        verification_mode="browser_search_submit",
                        verification_detail=str((search_result.get("reply") or "")).strip(),
                    )
                return _url_result(
                    f"网页已打开，但搜索还没有完成：`{remote_plan['search_term']}`",
                    target=effective_target,
                    observed_state="search_submit_pending",
                    outcome="opened_search_pending",
                    repair_attempted=True,
                    repair_succeeded=False,
                    drift_reason="search_submit_pending",
                    repair_hint="use_ui_interaction_or_query_url",
                    display_hint=f"网页已打开，但搜索还没有完成：{remote_plan['search_term']}",
                    verification_mode="browser_search_submit",
                    verification_detail=str((search_result.get("reply") or "")).strip(),
                )
            return _url_result(
                reply,
                target=effective_target,
                observed_state="url_opened",
                outcome=outcome,
                repair_attempted=False,
                repair_succeeded=True,
                verification_mode=str(remote_plan.get("strategy") or verify.get("mode") or ""),
                verification_detail=str(verify.get("detail") or ""),
            )

        return _url_result(
            f"已触发打开网页：`{effective_target}`",
            target=effective_target,
            observed_state="url_opened_unconfirmed",
            outcome="triggered_unconfirmed",
            repair_attempted=False,
            repair_succeeded=True,
            repair_hint="check_existing_browser_tab",
            display_hint=f"已触发打开网页：{effective_target}",
            verification_mode=str(remote_plan.get("strategy") or verify.get("mode") or "unverified"),
            verification_detail=str(verify.get("detail") or ""),
        )

    state = check_saved_state(info["target"]) if info["target_type"] in {"file", "folder"} else {"ok": True}
    if info["target_type"] in {"file", "folder"} and not state.get("exists"):
        return _local_target_result(
            f"打开失败：执行后没有检测到目标：`{info['target']}`",
            target=info["target"],
            target_kind=info["target_type"],
            observed_state="target_not_visible",
            outcome="failed",
            repair_attempted=False,
            repair_succeeded=False,
            drift_reason="post_open_invisible",
            repair_hint="retry_or_check_shell_association",
            display_hint=f"打开后没有检测到目标：{info['target']}",
        )

    if info["target_type"] == "folder":
        reply = f"已打开文件夹：`{info['target']}`"
    else:
        reply = f"已打开文件：`{info['target']}`"
    return _local_target_result(
        reply,
        target=info["target"],
        target_kind=info["target_type"],
        observed_state="target_visible",
        outcome="opened",
        repair_attempted=False,
        repair_succeeded=True,
    )
