"""Companion 伴侣窗口路由"""
import os
import re
from datetime import datetime

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

LIVE2D_DIR = None       # set by init()
COMPANION_HTML_FILE = None
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 年轻活泼女声


def init(*, engine_dir):
    global LIVE2D_DIR, COMPANION_HTML_FILE, _available_models
    LIVE2D_DIR = engine_dir / "static" / "live2d"
    COMPANION_HTML_FILE = engine_dir / "companion.html"
    _available_models = _scan_live2d_models()


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
    return {
        "mood": ps.get("mood", "\u6e29\u67d4"),
        "energy": ps.get("energy", "\u7a33\u5b9a"),
        "active_mode": persona.get("active_mode", "sweet") if isinstance(persona, dict) else "sweet",
        "activity": activity,
        "last_reply_id": reply_id,
        "last_reply_summary": last_reply,
        "last_reply_full": last_reply_full,
        "tts_playing": tts_playing,
        "model": model,
        "ts": datetime.now().isoformat(),
    }


@router.post("/companion/tts_status")
async def companion_tts_status(req: Request):
    global tts_playing
    data = await req.json()
    tts_playing = bool(data.get("playing", False))
    return {"ok": True}


@router.get("/companion/models")
async def companion_models():
    return {"models": _available_models, "current": model}


@router.post("/companion/model/{name}")
async def companion_switch_model(name: str):
    global model
    if name in _available_models:
        model = name
        return {"ok": True, "model": name, "path": _available_models[name]}
    return {"ok": False, "error": f"model '{name}' not found"}


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
