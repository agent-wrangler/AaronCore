from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


activity = "idle"
reply_id = ""
last_reply = ""
last_reply_summary = ""
last_reply_full = ""
emotion = "neutral"
tts_playing = False
voice_mode = False


class VoiceModeRequest(BaseModel):
    enabled: bool = False


class TtsStatusRequest(BaseModel):
    playing: bool = False


def build_state_payload() -> dict:
    summary = str(last_reply_summary or last_reply or "").strip()
    full = str(last_reply_full or summary).strip()
    rid = str(reply_id or "").strip()
    return {
        "activity": str(activity or "idle"),
        "emotion": str(emotion or "neutral"),
        "reply_id": rid,
        "last_reply_id": rid,
        "last_reply": summary,
        "last_reply_summary": summary,
        "last_reply_full": full,
        "tts_playing": bool(tts_playing),
        "voice_mode": bool(voice_mode),
    }


def reset_state() -> None:
    global activity, reply_id, last_reply, last_reply_summary, last_reply_full
    global emotion, tts_playing, voice_mode

    activity = "idle"
    reply_id = ""
    last_reply = ""
    last_reply_summary = ""
    last_reply_full = ""
    emotion = "neutral"
    tts_playing = False
    voice_mode = False


@router.get("/companion/state")
async def companion_state():
    return build_state_payload()


@router.post("/companion/voice_mode")
async def companion_voice_mode(req: VoiceModeRequest):
    global voice_mode

    voice_mode = bool(req.enabled)
    return {"ok": True, "enabled": voice_mode}


@router.post("/companion/tts_status")
async def companion_tts_status(req: TtsStatusRequest):
    global tts_playing

    tts_playing = bool(req.playing)
    return {"ok": True, "playing": tts_playing}


@router.get("/companion/running")
async def companion_running():
    return {
        "running": bool(
            voice_mode
            or tts_playing
            or str(activity or "").strip().lower() not in {"", "idle"}
        )
    }
