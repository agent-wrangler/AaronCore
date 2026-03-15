import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / "memory_db" / "feedback_rules.json"

# ── L7 板块定义 ──────────────────────────────────────────────
# 每条反馈规则归入一个板块（category），方便上层统计和设置页展示
# 板块：内容生成 / 路由调度 / 意图理解 / 交互风格
_PROBLEM_TO_CATEGORY = {
    # 内容生成：创作类输出质量问题
    ("joke", "output_not_matching_intent"): "内容生成",
    ("story", "length_too_short"): "内容生成",
    # 路由调度：技能选择和调度问题
    ("routing", "wrong_skill_selected"): "路由调度",
    # 意图理解：没听懂用户在说什么
    ("general", "output_not_matching_intent"): "意图理解",
    # 交互风格：回复太空泛、模板化
    ("chat", "fallback_too_generic"): "交互风格",
}


def _infer_category(scene: str, problem: str) -> str:
    """根据 scene + problem 推断板块。"""
    cat = _PROBLEM_TO_CATEGORY.get((scene, problem))
    if cat:
        return cat
    # fallback 按 scene 粗分
    if scene in ("joke", "story"):
        return "内容生成"
    if scene == "routing":
        return "路由调度"
    if scene == "chat":
        return "交互风格"
    return "意图理解"


def _load_rules():
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_rules(rules):
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_feedback(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict:
    text = f"{last_question}\n{last_answer}\n{user_feedback}".strip()

    if any(k in text for k in ["不是笑话", "这不是笑话", "不好笑"]):
        return {
            "category": "内容生成",
            "type": "llm_rule",
            "scene": "joke",
            "problem": "output_not_matching_intent",
            "fix": "humor_request_should_use_llm_generation",
            "level": "short_term",
        }

    if any(k in text for k in ["太短", "有点短", "讲长一点"]):
        return {
            "category": "内容生成",
            "type": "llm_rule",
            "scene": "story",
            "problem": "length_too_short",
            "fix": "story_should_expand_when_user_requests_more",
            "level": "session",
        }

    if any(
        k in text
        for k in [
            "我没说天气",
            "不是天气",
            "你发天气之前",
            "别查天气",
            "别跳天气",
            "看我问的什么",
        ]
    ):
        return {
            "category": "路由调度",
            "type": "skill_route",
            "scene": "routing",
            "problem": "wrong_skill_selected",
            "fix": "adjust_skill_routing_for_scene",
            "level": "short_term",
        }

    if any(
        k in text
        for k in [
            "答歪了",
            "答偏了",
            "答非所问",
            "没听懂",
            "没有听懂",
            "理解错了",
            "你理解错了",
            "不是这个意思",
            "不是我要的",
            "我想听的是",
            "我想了解的是",
            "跑题了",
        ]
    ):
        return {
            "category": "意图理解",
            "type": "llm_rule",
            "scene": "general",
            "problem": "output_not_matching_intent",
            "fix": "keep_observing_and_refine",
            "level": "session",
        }

    if any(
        k in text
        for k in [
            "不该查",
            "不该调用",
            "走错",
            "不是这个技能",
            "小游戏",
            "弹窗",
            "窗口",
            "误触发",
            "流程错了",
            "对话里出现代码",
            "路由错了",
        ]
    ):
        return {
            "category": "路由调度",
            "type": "skill_route",
            "scene": "routing",
            "problem": "wrong_skill_selected",
            "fix": "adjust_skill_routing_for_scene",
            "level": "short_term",
        }

    if any(k in text for k in ["你还会什么", "别回空话", "别太傻", "别套话"]):
        return {
            "category": "交互风格",
            "type": "execution_policy",
            "scene": "chat",
            "problem": "fallback_too_generic",
            "fix": "ability_queries_should_answer_capabilities_directly",
            "level": "short_term",
        }

    # Default: generate a concrete correction note from the conversation
    fix_note = "keep_observing_and_refine"
    if last_answer and user_feedback:
        short_answer = last_answer[:60].replace("\n", " ")
        short_feedback = user_feedback[:60].replace("\n", " ")
        fix_note = f"\u4e0a\u6b21\u56de\u590d\u300c{short_answer}\u300d\uff0c\u7528\u6237\u8bf4\u300c{short_feedback}\u300d\uff0c\u4e0b\u6b21\u8981\u6309\u7528\u6237\u7ea0\u6b63\u7684\u65b9\u5411\u8c03\u6574"

    return {
        "category": _infer_category("general", "generic_feedback"),
        "type": "user_pref",
        "scene": "general",
        "problem": "generic_feedback",
        "fix": fix_note,
        "level": "session",
    }


def record_feedback_rule(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict:
    rule = classify_feedback(user_feedback, last_question, last_answer)
    rules = _load_rules()
    item = {
        "id": f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "user_feedback",
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "user_feedback": user_feedback,
        "last_question": last_question,
        "last_answer": last_answer,
        **rule,
    }
    rules.append(item)
    _save_rules(rules[-200:])
    return item
