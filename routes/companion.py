"""Companion 伴侣窗口路由"""
import json
import os
import re
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from core import shared as S

router = APIRouter()

# ── Companion 状态 ──
activity = "idle"       # idle / thinking / replying / skill
last_reply = ""         # 最近一次回复摘要
last_reply_full = ""    # 完整回复文本（供 TTS 使用）
reply_id = ""           # 回复 ID（用于前端去重）
model = "Hiyori"        # 当前模型名
tts_playing = False     # 伴侣窗口正在播放 TTS
voice_mode = False      # 主窗口语音模式是否开启
emotion = "neutral"     # 当前情绪标签（neutral/happy/thinking/surprised/sad/cute）

LIVE2D_DIR = None       # set by init()
COMPANION_HTML_FILE = None
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 年轻活泼女声
_CONFIG_FILE = None
_companion_process = None  # 跟踪伴侣进程

# TTS 可选语音列表
TTS_VOICES = [
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊（活泼女声）"},
    {"id": "zh-CN-XiaohanNeural", "name": "晓涵（温柔女声）"},
    {"id": "zh-CN-XiaomengNeural", "name": "晓萌（甜美女声）"},
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓（标准女声）"},
    {"id": "zh-CN-YunxiNeural", "name": "云希（少年男声）"},
    {"id": "zh-CN-YunjianNeural", "name": "云健（成熟男声）"},
]


def _load_config():
    try:
        return json.loads(_CONFIG_FILE.read_text("utf-8")) if _CONFIG_FILE and _CONFIG_FILE.exists() else {}
    except Exception:
        return {}


def _save_config(cfg):
    try:
        if _CONFIG_FILE:
            _CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def init(*, engine_dir):
    global LIVE2D_DIR, COMPANION_HTML_FILE, _available_models, _CONFIG_FILE, model, TTS_VOICE
    LIVE2D_DIR = engine_dir / "static" / "live2d"
    COMPANION_HTML_FILE = engine_dir / "companion.html"
    _CONFIG_FILE = engine_dir / "memory_db" / "companion_config.json"
    _available_models = _scan_live2d_models()
    # 从配置文件恢复
    cfg = _load_config()
    if cfg.get("model") and cfg["model"] in _available_models:
        model = cfg["model"]
    if cfg.get("tts_voice"):
        TTS_VOICE = cfg["tts_voice"]


def _scan_live2d_models():
    models = {}
    if LIVE2D_DIR and LIVE2D_DIR.is_dir():
        for d in sorted(LIVE2D_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                m3 = d / f"{d.name}.model3.json"
                if m3.exists():
                    models[d.name] = f"/static/live2d/{d.name}/{d.name}.model3.json"
    return models


_available_models = {}


@router.get("/companion", response_class=HTMLResponse)
async def companion_page():
    if COMPANION_HTML_FILE and COMPANION_HTML_FILE.exists():
        try:
            html = COMPANION_HTML_FILE.read_text(encoding="utf-8")
            css_file = S.ENGINE_DIR / "static" / "css" / "companion.css"
            if css_file.exists():
                css = css_file.read_text(encoding="utf-8")
                html = html.replace(
                    '<link rel="stylesheet" href="/static/css/companion.css">',
                    f"<style>{css}</style>",
                )
            return html
        except Exception:
            pass
    return "<html><body style='background:transparent'>companion not found</body></html>"


@router.get("/companion/state")
async def companion_state():
    persona = S.load_l4_persona()
    ps = persona.get("persona_state", {}) if isinstance(persona, dict) else {}

    # 视觉感知 + 主动搭话
    vision_ctx = {"description": "", "ts": ""}
    proactive = {"message": "", "ts": ""}
    try:
        from core.vision import get_vision_context, get_proactive_message
        vision_ctx = get_vision_context()
        proactive = get_proactive_message()
    except Exception:
        pass

    return {
        "mood": ps.get("mood", "\u6e29\u67d4"),
        "energy": ps.get("energy", "\u7a33\u5b9a"),
        "active_mode": persona.get("active_mode", "sweet") if isinstance(persona, dict) else "sweet",
        "activity": activity,
        "emotion": emotion,
        "last_reply_id": reply_id,
        "last_reply_summary": last_reply,
        "last_reply_full": last_reply_full,
        "tts_playing": tts_playing,
        "voice_mode": voice_mode,
        "model": model,
        "vision": vision_ctx,
        "proactive": proactive,
        "ts": datetime.now().isoformat(),
    }


@router.post("/companion/tts_status")
async def companion_tts_status(req: Request):
    global tts_playing
    data = await req.json()
    tts_playing = bool(data.get("playing", False))
    return {"ok": True}


@router.post("/companion/voice_mode")
async def companion_voice_mode(req: Request):
    global voice_mode
    data = await req.json()
    voice_mode = bool(data.get("enabled", False))
    return {"ok": True}


@router.get("/companion/vision")
async def companion_vision():
    """调试接口：查看当前视觉感知状态"""
    try:
        from core.vision import get_vision_context, _running, _last_capture_time
        ctx = get_vision_context()
        return {
            "running": _running,
            "last_capture_epoch": _last_capture_time,
            "description": ctx.get("description", ""),
            "ts": ctx.get("ts", ""),
        }
    except Exception as e:
        return {"running": False, "error": str(e)}


@router.get("/companion/models")
async def companion_models():
    return {"models": _available_models, "current": model}


@router.post("/companion/model/{name}")
async def companion_switch_model(name: str):
    global model
    if name in _available_models:
        model = name
        cfg = _load_config()
        cfg["model"] = name
        _save_config(cfg)
        return {"ok": True, "model": name, "path": _available_models[name]}
    return {"ok": False, "error": f"model '{name}' not found"}


@router.get("/companion/config")
async def companion_get_config():
    cfg = _load_config()
    return {
        "enabled": cfg.get("enabled", True),
        "model": model,
        "tts_voice": TTS_VOICE,
        "opacity_idle": cfg.get("opacity_idle", 0.3),
        "always_on_top": cfg.get("always_on_top", True),
        "models": _available_models,
        "tts_voices": TTS_VOICES,
    }


@router.post("/companion/config")
async def companion_update_config(req: Request):
    global model, TTS_VOICE
    data = await req.json()
    cfg = _load_config()
    for key in ["enabled", "opacity_idle", "always_on_top"]:
        if key in data:
            cfg[key] = data[key]
    if "model" in data and data["model"] in _available_models:
        cfg["model"] = data["model"]
        model = data["model"]
    if "tts_voice" in data:
        cfg["tts_voice"] = data["tts_voice"]
        TTS_VOICE = data["tts_voice"]
    _save_config(cfg)
    return {"ok": True, "config": cfg}


def _is_companion_running():
    """检测伴侣 Electron 进程是否在运行"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", 8091))
        s.close()
        return True
    except Exception:
        return False


def _start_companion_process():
    """启动伴侣 Electron 进程"""
    global _companion_process
    if _is_companion_running():
        return True
    try:
        companion_dir = S.ENGINE_DIR / "companion" if S.ENGINE_DIR else None
        if not companion_dir or not companion_dir.exists():
            return False
        electron_exe = companion_dir / "node_modules" / "electron" / "dist" / "electron.exe"
        if not electron_exe.exists():
            return False
        env = os.environ.copy()
        env.pop("ELECTRON_RUN_AS_NODE", None)
        _companion_process = subprocess.Popen(
            [str(electron_exe), "."],
            cwd=str(companion_dir),
            env=env,
        )
        return True
    except Exception:
        return False


def _stop_companion_process():
    """关闭伴侣 Electron 进程"""
    global _companion_process
    # 只杀已跟踪的伴侣进程，不用 /im electron.exe 避免误杀主窗口
    if _companion_process and _companion_process.poll() is None:
        try:
            _companion_process.kill()
            _companion_process.wait(timeout=5)
        except Exception:
            pass
        _companion_process = None
    # 兜底：只杀伴侣进程的 PID，不做全局 electron 清杀
    try:
        companion_dir = S.ENGINE_DIR / "companion" if S.ENGINE_DIR else None
        if companion_dir:
            subprocess.run(
                ["taskkill", "/f", "/fi", f"WINDOWTITLE eq *companion*"],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


@router.post("/companion/toggle")
async def companion_toggle(req: Request):
    data = await req.json()
    enabled = bool(data.get("enabled", True))
    cfg = _load_config()
    cfg["enabled"] = enabled
    _save_config(cfg)
    if enabled:
        ok = _start_companion_process()
        return {"ok": ok, "running": True, "message": "Entity 已启动" if ok else "启动失败"}
    else:
        _stop_companion_process()
        return {"ok": True, "running": False, "message": "Entity 已关闭"}


@router.get("/companion/running")
async def companion_running():
    return {"running": _is_companion_running()}


# 清理 TTS 文本：只去掉 emoji
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0000200D]+"
)


def _clean_tts_text(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


# ── TTS 语音合成 ──

def _clear_proxies():
    """临时清除代理环境变量，返回旧值"""
    old = {}
    for k in list(os.environ):
        if "proxy" in k.lower():
            old[k] = os.environ.pop(k)
    return old


@router.get("/tts_stream")
async def tts_stream(text: str = ""):
    """纯流式 TTS：边生成边推送，不落盘"""
    text = text.strip()
    if not text:
        return {"error": "empty text"}

    clean = _clean_tts_text(text)
    if not clean:
        return {"error": "empty after clean"}

    import edge_tts

    async def audio_generator():
        old_proxies = _clear_proxies()
        try:
            tts = edge_tts.Communicate(clean, TTS_VOICE)
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        finally:
            os.environ.update(old_proxies)

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")
