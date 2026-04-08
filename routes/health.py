"""健康检查 + 感知 + QQ 监控路由"""
from datetime import datetime
from fastapi import APIRouter
from core import shared as S

router = APIRouter()


@router.get("/health")
async def get_health():
    return {
        "status": "ok",
        "entry": "agent_final.py",
        "core_ready": S.NOVA_CORE_READY,
        "current_model": S.load_current_model(),
        "state_dir": str(S.PRIMARY_STATE_DIR),
        "time": datetime.now().isoformat(),
    }


@router.get("/qq/monitor")
async def get_qq_monitor_status():
    try:
        from core.skills.computer_use import qq_monitor_status
        return qq_monitor_status()
    except Exception:
        return {"active": False, "group": None}
