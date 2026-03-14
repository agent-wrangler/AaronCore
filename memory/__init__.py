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

def add_long_term(content: str, category: str = "fact"):
    """添加长期记忆"""
    data = get_long_term()
    data.append({
        "content": content,
        "category": category,
        "timestamp": datetime.now().isoformat()
    })
    with open(long_term_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def get_evolution() -> dict:
    """获取进化数据"""
    if evolution_file.exists():
        return json.loads(evolution_file.read_text(encoding="utf-8"))
    return {"skills_used": {}, "user_preferences": {}, "learning": []}


def _can_count_skill_usage(skill_used: str) -> bool:
    name = str(skill_used or "").strip()
    if not name:
        return False
    try:
        from core.skills import get_skill

        return bool(get_skill(name))
    except Exception:
        return False

def evolve(user_input: str, skill_used: str):
    """L8: 能力进化 - 记录并更新"""
    evo = get_evolution()
    now = datetime.now().isoformat()
    skill_name = str(skill_used or "").strip()
    can_count_skill = _can_count_skill_usage(skill_name)
    
    # 记录技能使用
    if can_count_skill:
        if skill_name not in evo.get("skills_used", {}):
            evo["skills_used"][skill_name] = {"count": 0, "last_used": ""}
        evo["skills_used"][skill_name]["count"] += 1
        evo["skills_used"][skill_name]["last_used"] = now
    
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
