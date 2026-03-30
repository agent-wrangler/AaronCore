import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from core.fs_protocol import build_operation_result

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120

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
    "npm run",
    "uv ",
    "cargo ",
    "fix code",
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

_GAME_MARKERS = (
    "game",
    "小游戏",
    "贪吃蛇",
    "俄罗斯方块",
    "扫雷",
    "五子棋",
    "井字棋",
    "tkinter game",
    "pygame",
    "像素游戏",
    "玩游戏",
)


def _load_llm_config() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "brain" / "llm_config.json"
    if not config_path.exists():
        return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if "models" not in raw:
        return raw
    default_name = str(raw.get("default") or "").strip()
    models = raw.get("models") or {}
    if default_name and isinstance(models.get(default_name), dict):
        return models[default_name]
    for item in models.values():
        if isinstance(item, dict):
            return item
    return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


def _looks_like_non_game_request(user_request: str) -> bool:
    text = str(user_request or "").strip().lower()
    if not text:
        return False
    has_non_game_marker = any(marker in text for marker in _NON_GAME_MARKERS)
    has_game_marker = any(marker in text for marker in _GAME_MARKERS)
    return has_non_game_marker and not has_game_marker


def execute(user_request):
    request_text = str(user_request or "").strip()

    if _looks_like_non_game_request(request_text):
        result = build_operation_result(
            "这更像构建、打包、安装或测试任务，不是小游戏请求。请改用 run_command。",
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
            verification_detail="run_code only handles actual local game requests.",
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "wrong_task_type",
            "detail": "run_code rejected a non-game request and asked for run_command.",
        }
        return result

    llm_config = _load_llm_config()
    prompt = (
        f"用户想要：{request_text}\n\n"
        "请生成一个完整的 Python 小游戏程序。\n"
        "要求：\n"
        "1. 必须使用 tkinter 图形界面\n"
        "2. 游戏可以直接运行，打开就能玩\n"
        "3. 窗口大小约 400x300\n"
        "4. 包含游戏主循环\n"
        "5. 只输出代码，不要解释\n"
    )

    try:
        from brain import llm_call

        result = llm_call(
            llm_config,
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
            timeout=(CONNECT_TIMEOUT + READ_TIMEOUT),
        )
        if result.get("error"):
            op = build_operation_result(
                f"小游戏生成失败：{str(result.get('error') or '')[:120]}",
                expected_state="game_generated",
                observed_state="llm_error",
                drift_reason="llm_error",
                repair_hint="retry_or_adjust_prompt",
                action_kind="generate_game",
                target_kind="request",
                target=request_text[:120],
                outcome="failed",
                display_hint="小游戏生成失败",
                verification_mode="llm_call",
                verification_detail=str(result.get("error") or "")[:300],
            )
            op["verification"] = {
                "verified": False,
                "observed_state": "llm_error",
                "detail": str(result.get("error") or "")[:300],
            }
            return op

        code = str(result.get("content") or "").strip()
        if "```" in code:
            lines = code.splitlines()
            code = "\n".join(line for line in lines if not line.strip().startswith("```")).strip()
        if not code:
            op = build_operation_result(
                "小游戏生成失败：模型没有返回可执行代码。",
                expected_state="game_generated",
                observed_state="empty_code",
                drift_reason="empty_generation",
                repair_hint="retry_or_adjust_prompt",
                action_kind="generate_game",
                target_kind="request",
                target=request_text[:120],
                outcome="failed",
                display_hint="小游戏生成失败，没有生成代码",
                verification_mode="llm_call",
                verification_detail="The model returned empty code content.",
            )
            op["verification"] = {
                "verified": False,
                "observed_state": "empty_code",
                "detail": "The model returned empty code content.",
            }
            return op

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nova_game_{timestamp}.py"
        temp_dir = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".").resolve()
        temp_path = temp_dir / filename
        temp_path.write_text(code, encoding="utf-8")

        popen_kwargs = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([sys.executable, str(temp_path)], **popen_kwargs)

        op = build_operation_result(
            "游戏启动啦！玩得开心哦～🎮",
            expected_state="game_running",
            observed_state="process_started",
            repair_succeeded=True,
            action_kind="launch_game",
            target_kind="file",
            target=str(temp_path),
            outcome="launched",
            display_hint="已生成并启动小游戏",
            verification_mode="process_spawned",
            verification_detail=str(temp_path),
        )
        op["verification"] = {
            "verified": True,
            "observed_state": "process_started",
            "detail": str(temp_path),
        }
        return op
    except Exception as exc:
        op = build_operation_result(
            f"启动失败：{str(exc)[:80]}",
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
        return op
