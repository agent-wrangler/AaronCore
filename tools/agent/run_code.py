from __future__ import annotations

import json
import os
import re
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path

from core.fs_protocol import build_operation_result
from decision.tool_runtime.ask_user import execute_ask_user
from tools.agent.delivery_protocol import build_delivery_task_plan
from tools.agent.game_catalog import (
    build_game_spec as _catalog_build_game_spec,
    get_template_choice_options as _catalog_get_template_choice_options,
    needs_template_choice as _catalog_needs_template_choice,
    resolve_template_choice as _catalog_resolve_template_choice,
)
from tools.agent.game_templates import get_template_script

OUTPUT_DIR_NAME = "aaroncore_games"
_GAME_DELIVERY_TITLES = {
    "clarify_spec": "明确小游戏目标和约束",
    "choose_approach": "选择模板和表现方向",
    "build_artifact": "生成并落地小游戏文件",
    "verify_delivery": "验证启动并交付结果",
}

_NON_GAME_MARKERS = (
    "pyinstaller",
    "exe",
    "msi",
    "installer",
    "install",
    "setup",
    "package",
    "packaging",
    "build",
    "compile",
    "test",
    "pytest",
    "pip install",
    "npm install",
    "repair",
    "deploy",
    "release",
    "打包",
    "安装",
    "构建",
    "编译",
    "测试",
    "修代码",
    "修复代码",
    "放到桌面",
)

_GAME_MARKERS = ("game", "小游戏", "游戏", "玩玩", "playable", "arcade")

_HTML_SHELL = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__TITLE__</title>
  <style>
    :root{--bg1:__BG1__;--bg2:__BG2__;--panel:__PANEL__;--line:__LINE__;--accent:__ACCENT__;--accent2:__ACCENT2__;--text:__TEXT__;--muted:__MUTED__;}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;padding:22px;display:grid;place-items:center;font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text);background:linear-gradient(160deg,var(--bg1),var(--bg2))}
    .shell{width:min(96vw,1020px);padding:20px;border-radius:24px;background:var(--panel);border:1px solid var(--line);box-shadow:0 24px 80px rgba(0,0,0,.35)}
    .top{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:14px}.top h1{margin:0;font-size:clamp(28px,3vw,38px)}.top p{margin:10px 0 0;color:var(--muted);max-width:52ch;line-height:1.6}
    .stats{display:flex;gap:10px;flex-wrap:wrap}.chip{min-width:108px;padding:10px 14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.04)}.chip label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}.chip strong{font-size:18px}
    .board{position:relative;border-radius:22px;overflow:hidden;border:1px solid var(--line)} canvas{display:block;width:100%;height:auto;aspect-ratio:__WIDTH__/__HEIGHT__}
    .overlay{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(5,8,18,.68);padding:24px}.overlay.show{display:flex}.overlay-card{max-width:520px;padding:22px;border-radius:20px;background:rgba(10,16,30,.92);border:1px solid var(--line);text-align:center}.overlay-card h2{margin:0 0 10px;font-size:30px}.overlay-card p{margin:0;color:var(--muted);line-height:1.6}
    .foot{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin-top:14px}.hint{color:var(--muted);line-height:1.5}.actions{display:flex;gap:10px;flex-wrap:wrap}
    button{border:0;cursor:pointer;border-radius:999px;padding:11px 18px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#07111f}.secondary{background:rgba(255,255,255,.05);color:var(--text);border:1px solid var(--line)}
  </style>
</head>
<body>
  <main class="shell">
    <section class="top">
      <div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div>
      <div class="stats">
        <div class="chip"><label>分数</label><strong id="scoreValue">0</strong></div>
        <div class="chip"><label>状态</label><strong id="statusValue">准备开始</strong></div>
        <div class="chip"><label>额外</label><strong id="extraValue">-</strong></div>
      </div>
    </section>
    <section class="board">
      <canvas id="gameCanvas" width="__WIDTH__" height="__HEIGHT__"></canvas>
      <div class="overlay" id="overlay"><div class="overlay-card"><h2 id="overlayTitle">已准备</h2><p id="overlayBody">点重新开始可以再来一局。</p></div></div>
    </section>
    <section class="foot">
      <div class="hint">__HINT__</div>
      <div class="actions"><button id="restartBtn">重新开始</button><button id="pauseBtn" class="secondary">暂停 / 继续</button></div>
    </section>
  </main>
  <script>
    const SPEC = __SPEC__;
    const canvas = document.getElementById("gameCanvas");
    const ctx = canvas.getContext("2d");
    const P = SPEC.palette;
    const overlay = document.getElementById("overlay");
    const overlayTitle = document.getElementById("overlayTitle");
    const overlayBody = document.getElementById("overlayBody");
    const scoreValue = document.getElementById("scoreValue");
    const statusValue = document.getElementById("statusValue");
    const extraValue = document.getElementById("extraValue");
    const clamp = (v,min,max) => Math.max(min, Math.min(max, v));
    const rand = (min,max) => Math.random() * (max - min) + min;
    function backdrop(){
      const g = ctx.createLinearGradient(0,0,canvas.width,canvas.height); g.addColorStop(0,P.bg1); g.addColorStop(1,P.bg2); ctx.fillStyle = g; ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.strokeStyle = P.line; ctx.lineWidth = 1; for(let i = 0; i < 18; i += 1){ const y = (i / 18) * canvas.height; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(canvas.width,y+20); ctx.stroke(); }
    }
    const api = {
      clamp, rand, backdrop,
      setScore(v){ scoreValue.textContent = String(Math.max(0, Math.floor(v))); },
      setStatus(v){ statusValue.textContent = v; },
      setExtra(v){ extraValue.textContent = v; },
      show(title, body){ overlayTitle.textContent = title; overlayBody.textContent = body; overlay.classList.add("show"); },
      hide(){ overlay.classList.remove("show"); }
    };
    __SCRIPT__
    const game = createGame(api);
    document.getElementById("restartBtn").addEventListener("click", () => game.restart());
    document.getElementById("pauseBtn").addEventListener("click", () => game.pause());
    window.addEventListener("keydown", (e) => {
      const key = e.key.toLowerCase();
      if(key === " "){ e.preventDefault(); game.pause(); return; }
      if(key === "r"){ game.restart(); return; }
      game.onKey && game.onKey(key);
    });
    window.addEventListener("keyup", (e) => { const key = e.key.toLowerCase(); game.onKeyUp && game.onKeyUp(key); });
    game.start();
  </script>
</body>
</html>
"""


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _normalize_text(value))
    return slug.strip("_") or "mini_game"


def _looks_like_non_game_request(user_request: str) -> bool:
    text = _normalize_text(user_request)
    if not text:
        return False
    return any(marker in text for marker in _NON_GAME_MARKERS) and not any(
        marker in text for marker in _GAME_MARKERS
    )


def _build_game_spec(user_request: str) -> dict:
    return _catalog_build_game_spec(user_request)


def _extract_ask_user_answer(result: dict) -> str:
    response = str((result or {}).get("response") or "").strip()
    if "：" in response:
        return response.split("：", 1)[-1].strip()
    if ":" in response:
        return response.split(":", 1)[-1].strip()
    return response


def _resolve_game_request_text(user_request: str, context: dict | None = None) -> tuple[str | None, dict | None]:
    request_text = str(user_request or "").strip()
    if not _catalog_needs_template_choice(request_text):
        return request_text, None

    selection = execute_ask_user(
        {
            "question": "先选一个小游戏模板吧，我按这个方向直接给你做。",
            "options": _catalog_get_template_choice_options(),
        }
    )
    if not bool(selection.get("success")):
        return None, selection

    answer = _extract_ask_user_answer(selection)
    template_name = _catalog_resolve_template_choice(answer, fallback_request=request_text)
    return f"{request_text} {template_name}", selection


def _resolve_output_dir() -> Path:
    temp_root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".").resolve()
    output_dir = temp_root / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _build_output_path(spec: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _resolve_output_dir() / f"{_slugify(spec['template'])}_{stamp}.html"


def _open_generated_game(target_path: Path) -> tuple[bool, str]:
    target = Path(target_path).resolve()
    uri = target.as_uri()
    detail_parts: list[str] = []
    try:
        opened = bool(webbrowser.open(uri))
        detail_parts.append(f"webbrowser={opened}")
        if opened:
            return True, f"{uri} ({', '.join(detail_parts)})"
    except Exception as exc:
        detail_parts.append(f"webbrowser_error={str(exc)[:120]}")
    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(str(target))
            detail_parts.append("startfile=True")
            return True, f"{uri} ({', '.join(detail_parts)})"
        except Exception as exc:
            detail_parts.append(f"startfile_error={str(exc)[:120]}")
    return False, f"{uri} ({', '.join(detail_parts)})"


def _render_game_html(spec: dict) -> str:
    palette = spec["palette"]
    html = _HTML_SHELL
    replacements = {
        "__TITLE__": escape(spec["title"]),
        "__SUBTITLE__": escape(spec["subtitle"]),
        "__HINT__": escape(spec["hint"]),
        "__WIDTH__": str(spec["width"]),
        "__HEIGHT__": str(spec["height"]),
        "__SPEC__": json.dumps(spec, ensure_ascii=False),
        "__SCRIPT__": get_template_script(spec["template"]),
        "__BG1__": palette["bg1"],
        "__BG2__": palette["bg2"],
        "__PANEL__": palette["panel"],
        "__LINE__": palette["line"],
        "__ACCENT__": palette["accent"],
        "__ACCENT2__": palette["accent2"],
        "__TEXT__": palette["text"],
        "__MUTED__": palette["muted"],
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html


def _build_game_delivery_plan(
    goal: str,
    *,
    summary: str = "",
    current_step: str = "",
    completed_steps=None,
    waiting_step: str = "",
    blocked_step: str = "",
    step_details: dict | None = None,
    phase: str = "",
) -> dict:
    return build_delivery_task_plan(
        goal,
        titles=_GAME_DELIVERY_TITLES,
        summary=summary,
        current_step=current_step,
        completed_steps=completed_steps,
        waiting_step=waiting_step,
        blocked_step=blocked_step,
        step_details=step_details,
        phase=phase,
    )


def execute(user_request, context=None):
    context = context if isinstance(context, dict) else {}
    request_text = str(user_request or "").strip()
    if _looks_like_non_game_request(request_text):
        result = build_operation_result(
            "这更像构建、打包、安装或测试任务，不是小游戏交付请求。请改用 run_command。",
            expected_state="game_request",
            observed_state="wrong_task_type",
            drift_reason="wrong_tool_selected",
            repair_hint="use_run_command",
            action_kind="run_code",
            target_kind="request",
            target=request_text[:120],
            outcome="blocked",
            display_hint="这不是小游戏请求，建议改用 run_command",
            verification_mode="intent_guard",
            verification_detail="run_code only handles actual local game delivery requests.",
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "wrong_task_type",
            "detail": "run_code rejected a non-game request and asked for run_command.",
        }
        return result

    try:
        resolved_request_text, selection_result = _resolve_game_request_text(request_text, context)
        if not resolved_request_text:
            detail = str((selection_result or {}).get("response") or "").strip() or "未拿到模板选择结果"
            op = build_operation_result(
                "小游戏分型暂时没有完成，这轮先停在模板选择这里。",
                expected_state="template_selected",
                observed_state="selection_timeout",
                drift_reason="user_choice_timeout",
                repair_hint="retry_template_selection",
                action_kind="choose_game_template",
                target_kind="request",
                target=request_text[:120],
                outcome="blocked",
                display_hint="等待小游戏模板选择超时",
                verification_mode="ask_user",
                verification_detail=detail,
            )
            op["verification"] = {
                "verified": False,
                "observed_state": "selection_timeout",
                "detail": detail,
            }
            op["task_plan"] = _build_game_delivery_plan(
                request_text,
                completed_steps=["clarify_spec"],
                waiting_step="choose_approach",
                summary="等待用户选择小游戏模板",
                step_details={"choose_approach": detail},
                phase="choose_approach",
            )
            return op

        spec = _build_game_spec(resolved_request_text)
        html = _render_game_html(spec)
        output_path = _build_output_path(spec)
        output_path.write_text(html, encoding="utf-8")

        opened, launch_detail = _open_generated_game(output_path)
        if not opened:
            op = build_operation_result(
                "小游戏已经生成好了，但自动打开失败了。",
                expected_state="game_running",
                observed_state="launch_failed",
                drift_reason="browser_launch_failed",
                repair_hint="open_generated_game_manually",
                action_kind="launch_game",
                target_kind="file",
                target=str(output_path),
                outcome="failed",
                display_hint="小游戏文件已生成，但浏览器启动失败",
                verification_mode="browser_launch",
                verification_detail=launch_detail,
            )
            op["verification"] = {
                "verified": False,
                "observed_state": "launch_failed",
                "detail": launch_detail,
            }
            op["task_plan"] = _build_game_delivery_plan(
                request_text,
                completed_steps=["clarify_spec", "choose_approach", "build_artifact"],
                blocked_step="verify_delivery",
                summary="小游戏文件已生成，但自动启动失败",
                step_details={"verify_delivery": launch_detail},
                phase="blocked",
            )
            return op

        op = build_operation_result(
            f"小游戏已经准备好了：{spec['title']}",
            expected_state="game_running",
            observed_state="browser_opened",
            repair_succeeded=True,
            action_kind="launch_game",
            target_kind="file",
            target=str(output_path),
            outcome="launched",
            display_hint=f"已生成并打开 {spec['title']}",
            verification_mode="browser_launch",
            verification_detail=launch_detail,
        )
        op["verification"] = {
            "verified": True,
            "observed_state": "browser_opened",
            "detail": launch_detail,
        }
        op["task_plan"] = _build_game_delivery_plan(
            request_text,
            completed_steps=["clarify_spec", "choose_approach", "build_artifact", "verify_delivery"],
            summary=f"{spec['title']} 已生成并打开",
            phase="done",
        )
        return op
    except Exception as exc:
        op = build_operation_result(
            f"小游戏交付失败：{str(exc)[:120]}",
            expected_state="game_running",
            observed_state="launch_failed",
            drift_reason="launch_exception",
            repair_hint="inspect_generation_or_runtime_error",
            action_kind="launch_game",
            target_kind="request",
            target=request_text[:120],
            outcome="failed",
            display_hint="小游戏启动失败",
            verification_mode="exception",
            verification_detail=str(exc)[:300],
        )
        op["verification"] = {
            "verified": False,
            "observed_state": "launch_failed",
            "detail": str(exc)[:300],
        }
        op["task_plan"] = _build_game_delivery_plan(
            request_text,
            completed_steps=["clarify_spec"],
            blocked_step="build_artifact",
            summary="小游戏交付失败",
            step_details={"build_artifact": str(exc)[:300]},
            phase="blocked",
        )
        return op
