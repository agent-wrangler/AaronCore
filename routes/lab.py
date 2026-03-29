"""实验室路由：/lab API"""
from fastapi import APIRouter
from pydantic import BaseModel
from core import lab

router = APIRouter()


class CreateExperimentRequest(BaseModel):
    target_key: str = "l7_forge"
    goal: str
    rounds: int = 10
    test_inputs: list[str] | None = None


@router.get("/lab/status")
async def lab_status():
    return lab.get_status()


@router.get("/lab/targets")
async def list_targets():
    """列出所有可实验的目标（自我感知）"""
    return {"targets": lab.get_targets()}


@router.get("/lab/target/{key}")
async def read_target(key: str):
    """读取某个目标的完整内容"""
    content = lab.read_target(key)
    return {"key": key, "content": content}


@router.get("/lab/experiments")
async def list_experiments():
    return {"experiments": lab.get_experiments()}


@router.get("/lab/experiment/{exp_id}")
async def get_experiment(exp_id: str):
    exp = lab.get_experiment(exp_id)
    if not exp:
        return {"error": "not found"}
    return exp


@router.post("/lab/experiment")
async def create_experiment(req: CreateExperimentRequest):
    exp = lab.create_experiment(
        target_key=req.target_key,
        goal=req.goal,
        rounds=req.rounds,
        test_inputs=req.test_inputs,
    )
    if isinstance(exp, dict) and not exp.get("ok", True):
        return exp
    return {"ok": True, "experiment": exp}


@router.post("/lab/start/{exp_id}")
async def start_experiment(exp_id: str):
    return lab.start_experiment(exp_id)


@router.post("/lab/stop")
async def stop_experiment():
    return lab.stop_experiment()


@router.post("/lab/apply/{exp_id}")
async def apply_best(exp_id: str):
    return lab.apply_best_result(exp_id)
