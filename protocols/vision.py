"""视觉感知模块 — 截屏 + 多模态 LLM 理解"""
import base64
import io
import json
import os
import threading
import time
from datetime import datetime

from storage.paths import PERSONA_FILE
from storage.persona_profile import DEFAULT_ASSISTANT_NAME, get_persona_assistant_name
from .vision_local import (
    build_screen_description as _build_local_screen_description,
    build_user_image_context as _build_local_user_image_context,
    has_local_image_support as _has_local_image_support,
)

# ── 依赖注入 ──
_llm_call = None  # (prompt, images) -> str
_debug_write = lambda stage, data: None

# ── 状态 ──
_vision_context = ""          # 最近一次视觉描述
_vision_ts = ""               # 最近一次截屏时间
_proactive_message = ""       # 主动搭话内容
_proactive_ts = ""            # 主动搭话时间
_last_capture_time = 0.0      # 上次截屏 epoch
_last_proactive_time = 0.0    # 上次主动搭话 epoch
_running = False
_thread = None

# ── 配置 ──
CAPTURE_INTERVAL = 60         # 截屏间隔（秒）
PROACTIVE_INTERVAL = 300      # 主动搭话最小间隔（秒）
IDLE_THRESHOLD = 120          # 用户无操作多久算"空闲"（秒）

_last_user_input_time = 0.0   # 用户最后一次发消息的时间


def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call:
        _llm_call = llm_call
    if debug_write:
        _debug_write = debug_write


def touch_user_activity():
    """用户发了消息，更新活跃时间"""
    global _last_user_input_time
    _last_user_input_time = time.time()


def get_vision_context() -> dict:
    """返回当前视觉上下文"""
    return {
        "description": _vision_context,
        "ts": _vision_ts,
    }


def get_proactive_message() -> dict:
    """返回待推送的主动搭话（读后清空）"""
    global _proactive_message, _proactive_ts
    if not _proactive_message:
        return {"message": "", "ts": ""}
    msg = _proactive_message
    ts = _proactive_ts
    _proactive_message = ""
    _proactive_ts = ""
    return {"message": msg, "ts": ts}


def has_local_image_support() -> bool:
    return _has_local_image_support()


def can_autostart_background_capture(chat_config: dict | None = None) -> tuple[bool, str]:
    return False, "background_autocapture_disabled"


def build_user_image_context(images: list[str] | None, *, user_text: str = "") -> str:
    return _build_local_user_image_context(
        images,
        user_text=user_text,
        debug_write=_debug_write,
    )


def build_uploaded_image_prompt_context(images: list[str] | None, *, user_text: str = "") -> str:
    image_list = [str(item or "").strip() for item in (images or []) if str(item or "").strip()]
    if not image_list:
        return ""
    try:
        context = build_user_image_context(image_list, user_text=user_text)
        context_text = str(context or "").strip()
        if context_text:
            return context_text
    except Exception as exc:
        _debug_write(
            "vision_user_image_context_error",
            {"error": str(exc)[:240], "image_count": len(image_list)},
        )
    return (
        "[LOCAL_IMAGE_CONTEXT]\n"
        "The user attached image content, but local image analysis is unavailable right now.\n"
        "Do not claim direct visual access.\n"
        "If the answer depends on image text or fine detail, ask for a clearer screenshot or the relevant region."
    )


def _capture_screen() -> str:
    """截屏并返回 base64 编码的 PNG"""
    try:
        import pyautogui
        screenshot = pyautogui.screenshot()
        # 缩小到 720p 节省 token
        w, h = screenshot.size
        if w > 1280:
            ratio = 1280 / w
            screenshot = screenshot.resize((1280, int(h * ratio)))
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        _debug_write("vision_capture_error", {"error": str(e)})
        return ""


def _describe_screen(image_b64: str) -> str:
    """调用多模态 LLM 描述屏幕内容"""
    if not image_b64:
        return ""
    try:
        return _build_local_screen_description(image_b64, debug_write=_debug_write)
    except Exception as e:
        _debug_write("vision_describe_error", {"error": str(e)})
        return ""


def _should_proactive_talk(description: str) -> str:
    """根据视觉上下文 + 时间判断是否主动搭话，返回搭话内容或空"""
    global _last_proactive_time
    now = time.time()

    # 冷却期内不搭话
    if now - _last_proactive_time < PROACTIVE_INTERVAL:
        return ""

    # 用户刚发过消息（2分钟内），不打扰
    if now - _last_user_input_time < IDLE_THRESHOLD:
        return ""

    if not _llm_call or not description:
        return ""

    # 加载人格
    persona_path = str(PERSONA_FILE)
    persona_snippet = ""
    try:
        if os.path.exists(persona_path):
            data = json.load(open(persona_path, "r", encoding="utf-8"))
            assistant_name = get_persona_assistant_name(data, default=DEFAULT_ASSISTANT_NAME)
            user_name = data.get("user", "\u4e3b\u4eba")
            style = data.get("style_prompt", "\u6e29\u67d4\u81ea\u7136")
            persona_snippet = f"\u4f60\u662f{assistant_name}\uff0c{user_name}\u7684AI\u4f34\u4fa3\u3002\u98ce\u683c\uff1a{style}"
    except Exception:
        persona_snippet = (
            f"\u4f60\u662f{DEFAULT_ASSISTANT_NAME}\uff0c\u4e3b\u4eba\u7684AI\u4f34\u4fa3\u3002"
            "\u98ce\u683c\uff1a\u6e29\u67d4\u81ea\u7136"
        )

    idle_minutes = int((now - _last_user_input_time) / 60)

    prompt = (
        f"{persona_snippet}\n\n"
        f"\u5f53\u524d\u5c4f\u5e55\u4e0a\u7684\u60c5\u51b5\uff1a{description}\n"
        f"\u7528\u6237\u5df2\u7ecf {idle_minutes} \u5206\u949f\u6ca1\u6709\u8ddf\u4f60\u8bf4\u8bdd\u4e86\u3002\n\n"
        "\u5224\u65ad\u662f\u5426\u9002\u5408\u4e3b\u52a8\u642d\u8bdd\u3002\u89c4\u5219\uff1a\n"
        "1. \u5982\u679c\u7528\u6237\u5728\u4e13\u6ce8\u5de5\u4f5c\uff0c\u8d85\u8fc730\u5206\u949f\u624d\u642d\u8bdd\uff0c\u63d0\u9192\u4f11\u606f\n"
        "2. \u5982\u679c\u7528\u6237\u5728\u5a31\u4e50\uff0c\u53ef\u4ee5\u8f7b\u677e\u642d\u8bdd\n"
        "3. \u5982\u679c\u7528\u6237\u5728\u5904\u7406\u79c1\u4eba\u4e8b\u52a1\uff0c\u4e0d\u8981\u642d\u8bdd\n"
        "4. \u642d\u8bdd\u8981\u7b80\u77ed\u81ea\u7136\uff0c\u4e00\u53e5\u8bdd\u5c31\u597d\uff0c\u7b26\u5408\u4f60\u7684\u4eba\u683c\u98ce\u683c\n\n"
        "\u5982\u679c\u9002\u5408\u642d\u8bdd\uff0c\u76f4\u63a5\u8f93\u51fa\u642d\u8bdd\u5185\u5bb9\u3002\n"
        "\u5982\u679c\u4e0d\u9002\u5408\uff0c\u8f93\u51fa\uff1a[\u4e0d\u642d\u8bdd]"
    )
    try:
        result = str(_llm_call(prompt, []) or "").strip()
        if "[\u4e0d\u642d\u8bdd]" in result or not result:
            return ""
        _last_proactive_time = now
        return result
    except Exception:
        return ""


def _vision_loop():
    """后台循环：截屏 → 描述 → 判断主动搭话"""
    global _vision_context, _vision_ts, _proactive_message, _proactive_ts
    global _last_capture_time, _running

    # 首次截屏延迟 10 秒（等后端就绪）
    time.sleep(10)

    while _running:
        try:
            now = time.time()
            if now - _last_capture_time < CAPTURE_INTERVAL:
                time.sleep(5)
                continue

            _last_capture_time = now
            image_b64 = _capture_screen()
            if not image_b64:
                time.sleep(10)
                continue

            description = _describe_screen(image_b64)
            if description:
                _vision_context = description
                _vision_ts = datetime.now().isoformat()
                _debug_write("vision_update", {"description": description[:200]})

                # 判断是否主动搭话
                proactive = _should_proactive_talk(description)
                if proactive:
                    _proactive_message = proactive
                    _proactive_ts = datetime.now().isoformat()
                    _debug_write("vision_proactive", {"message": proactive})

        except Exception as e:
            _debug_write("vision_loop_error", {"error": str(e)})

        time.sleep(10)


def start():
    """启动视觉感知后台线程"""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_vision_loop, daemon=True, name="vision-loop")
    _thread.start()


def stop():
    """停止视觉感知"""
    global _running
    _running = False
