# Memory - L3 记忆系统 + L7-L8 自动学习
import os
import json
from pathlib import Path
from datetime import datetime

# 路径
memory_dir = Path(__file__).parent.parent / "memory_db"
knowledge_file = memory_dir / "knowledge.json"
persona_file = memory_dir / "persona.json"
long_term_file = memory_dir / "long_term.json"
evolution_file = memory_dir / "evolution.json"

# 对话历史
conversation_file = memory_dir / "conversation_history.txt"

def add_to_history(role: str, content: str):
    """添加对话到历史"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(conversation_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {role}: {content}\n")

def get_history(limit: int = 20) -> str:
    """获取对话历史"""
    if not conversation_file.exists():
        return ""
    with open(conversation_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    recent = lines[-limit:] if len(lines) > limit else lines
    return "".join(recent)

def get_knowledge() -> dict:
    """获取知识库"""
    if knowledge_file.exists():
        return json.loads(knowledge_file.read_text(encoding="utf-8"))
    return []

def get_persona() -> dict:
    """获取人格配置"""
    if persona_file.exists():
        return json.loads(persona_file.read_text(encoding="utf-8"))
    return {}

def update_persona(key: str, value):
    """更新人格配置"""
    data = get_persona()
    data[key] = value
    with open(persona_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def get_long_term() -> list:
    """获取长期记忆"""
    if long_term_file.exists():
        return json.loads(long_term_file.read_text(encoding="utf-8"))
    return []

def add_long_term(content: str, category: str = "event"):
    """添加长期记忆（L3 只存经历类数据：event / milestone）"""
    data = get_long_term()
    data.append({
        "summary": content,
        "type": category,
        "created_at": datetime.now().isoformat()
    })
    with open(long_term_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def get_evolution() -> dict:
    """获取进化数据"""
    if evolution_file.exists():
        return json.loads(evolution_file.read_text(encoding="utf-8"))
    return {"skills_used": {}, "user_preferences": {}, "learning": [], "skill_runs": []}


def _can_count_skill_usage(skill_used: str) -> bool:
    name = str(skill_used or "").strip()
    if not name:
        return False
    try:
        from core.skills import get_skill

        return bool(get_skill(name))
    except Exception:
        return False


def _maybe_promote_success_path(skill_name: str, run_event: dict, now: str):
    """L6 -> L5: 提炼稳定成功经验，只记录成功 + 已验证 + 无 drift 的技能经验。"""
    if not isinstance(run_event, dict):
        return
    if not bool(run_event.get("success", False)):
        return
    if run_event.get("verified") is not True:
        return
    if str(run_event.get("drift_reason") or "").strip():
        return

    action_kind = str(run_event.get("action_kind") or "").strip()
    target_kind = str(run_event.get("target_kind") or "").strip()
    outcome = str(run_event.get("outcome") or "").strip()
    observed_state = str(run_event.get("observed_state") or "").strip()
    verification_mode = str(run_event.get("verification_mode") or "").strip()
    verification_detail = str(run_event.get("verification_detail") or "").strip()
    summary = str(run_event.get("summary") or "").strip()

    if not action_kind and not outcome and not observed_state:
        return

    try:
        kb = get_knowledge()
        if not isinstance(kb, list):
            kb = []
    except Exception:
        kb = []

    key_parts = [skill_name, action_kind, target_kind, outcome, observed_state]
    exp_key = "|".join([p for p in key_parts if p])
    if not exp_key:
        return

    experience_name = " / ".join([p for p in [skill_name, action_kind or outcome, target_kind] if p])
    if not experience_name:
        experience_name = skill_name

    existing = None
    for item in kb:
        if not isinstance(item, dict):
            continue
        if str(item.get("source") or "").strip() != "l6_success_path":
            continue
        if str(item.get("experience_key") or "").strip() == exp_key:
            existing = item
            break

    if existing is None:
        kb.append({
            "source": "l6_success_path",
            "experience_key": exp_key,
            "name": experience_name,
            "核心技能": skill_name,
            "action_kind": action_kind,
            "target_kind": target_kind,
            "outcome": outcome,
            "observed_state": observed_state,
            "verification_mode": verification_mode,
            "verification_detail": verification_detail,
            "summary": summary,
            "应用示例": summary,
            "success_count": 1,
            "使用次数": 1,
            "learned_at": now,
            "最近使用时间": now,
        })
    else:
        existing["success_count"] = int(existing.get("success_count", 0)) + 1
        existing["使用次数"] = int(existing.get("使用次数", 0)) + 1
        existing["最近使用时间"] = now
        if summary:
            existing["summary"] = summary
            existing["应用示例"] = summary
        if verification_mode:
            existing["verification_mode"] = verification_mode
        if verification_detail:
            existing["verification_detail"] = verification_detail
        if observed_state:
            existing["observed_state"] = observed_state
        if outcome:
            existing["outcome"] = outcome

    try:
        with open(knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(kb, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def evolve(user_input: str, skill_used: str, run_event: dict | None = None):
    """L8: 能力进化 - 记录并更新"""
    evo = get_evolution()
    now = datetime.now().isoformat()
    skill_name = str(skill_used or "").strip()
    can_count_skill = _can_count_skill_usage(skill_name)
    run_event = run_event if isinstance(run_event, dict) else {}
    
    # 记录技能使用
    if can_count_skill:
        if skill_name not in evo.get("skills_used", {}):
            evo["skills_used"][skill_name] = {
                "count": 0,
                "last_used": "",
                "verified_count": 0,
                "failure_count": 0,
                "drift_count": 0,
                "last_outcome": "",
            }
        evo["skills_used"][skill_name]["count"] += 1
        evo["skills_used"][skill_name]["last_used"] = now
        if run_event:
            if run_event.get("verified") is True:
                evo["skills_used"][skill_name]["verified_count"] = int(evo["skills_used"][skill_name].get("verified_count", 0)) + 1
            if run_event.get("success") is False:
                evo["skills_used"][skill_name]["failure_count"] = int(evo["skills_used"][skill_name].get("failure_count", 0)) + 1
            if str(run_event.get("drift_reason") or "").strip():
                evo["skills_used"][skill_name]["drift_count"] = int(evo["skills_used"][skill_name].get("drift_count", 0)) + 1
            evo["skills_used"][skill_name]["last_outcome"] = str(run_event.get("outcome") or run_event.get("summary") or "").strip()

    if can_count_skill and run_event:
        runs = evo.get("skill_runs")
        if not isinstance(runs, list):
            runs = []
        runs.append({
            "skill": skill_name,
            "at": now,
            "success": bool(run_event.get("success", True)),
            "verified": run_event.get("verified"),
            "summary": str(run_event.get("summary") or "").strip(),
            "expected_state": str(run_event.get("expected_state") or "").strip(),
            "observed_state": str(run_event.get("observed_state") or "").strip(),
            "drift_reason": str(run_event.get("drift_reason") or "").strip(),
            "repair_hint": str(run_event.get("repair_hint") or "").strip(),
            "repair_succeeded": bool(run_event.get("repair_succeeded", False)),
            "action_kind": str(run_event.get("action_kind") or "").strip(),
            "target_kind": str(run_event.get("target_kind") or "").strip(),
            "target": str(run_event.get("target") or "").strip(),
            "outcome": str(run_event.get("outcome") or "").strip(),
            "verification_mode": str(run_event.get("verification_mode") or "").strip(),
            "verification_detail": str(run_event.get("verification_detail") or "").strip(),
        })
        evo["skill_runs"] = runs[-240:]
        _maybe_promote_success_path(skill_name, run_event, now)
    
    # 检测用户偏好
    user_keywords = []
    if any(w in user_input for w in ["天气", "温度"]):
        user_keywords.append("天气")
    if any(w in user_input for w in ["游戏", "做个", "写个"]):
        user_keywords.append("编程")
    if any(w in user_input for w in ["画", "海报", "图"]):
        user_keywords.append("画图")
    
    for kw in user_keywords:
        if kw not in evo.get("user_preferences", {}):
            evo["user_preferences"][kw] = 0
        evo["user_preferences"][kw] += 1
    
    # 定期更新knowledge.json的优先级
    if can_count_skill and knowledge_file.exists():
        try:
            kb = json.loads(knowledge_file.read_text(encoding="utf-8"))
            for item in kb:
                if item.get("触发器函数") == skill_name:
                    item["使用次数"] = item.get("使用次数", 0) + 1
            # 按使用次数排序
            kb.sort(key=lambda x: x.get("使用次数", 0), reverse=True)
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(kb, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    # 保存进化数据
    with open(evolution_file, 'w', encoding='utf-8') as f:
        json.dump(evo, f, ensure_ascii=False, indent=2)
    
    return evo

def get_context(query: str) -> str:
    """获取完整记忆上下文"""
    context_parts = []
    
    # 0. 用户信息（最重要！）
    persona = get_persona()
    if persona:
        user_name = persona.get('user', '用户')
        user_info = persona.get('user_info', {})
        if user_info:
            context_parts.append(f"【用户信息】\n你是和{user_name}对话，了解他的偏好：{user_info}")
    
    # 1. 对话历史
    history = get_history()
    if history:
        context_parts.append(f"【对话历史】\n{history}")
    
    # 2. 知识库（技能）
    knowledge = get_knowledge()
    if knowledge:
        skills = [f"- {k.get('一级场景')}/{k.get('二级场景')}: {k.get('核心技能')}" for k in knowledge[:10]]
        context_parts.append(f"【可用技能】\n" + "\n".join(skills))
    
    # 3. 长期记忆
    long_term = get_long_term()
    if long_term:
        memories = [f"- {m.get('content', '')[:50]}" for m in long_term[-5:]]
        context_parts.append(f"【重要记忆】\n" + "\n".join(memories))
    
    # 4. 进化数据
    evo = get_evolution()
    if evo.get("user_preferences"):
        prefs = [f"- {k}: {v}次" for k, v in evo["user_preferences"].items()]
        context_parts.append(f"【用户偏好】\n" + "\n".join(prefs))
    
    return "\n\n".join(context_parts)
