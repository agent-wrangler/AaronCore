import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / "memory_db" / "feedback_rules.json"

# ── 依赖注入 ──────────────────────────────────────────────
_llm_call = None
_debug_write = lambda stage, data: None


def init(*, llm_call=None, debug_write=None):
    global _llm_call, _debug_write
    if llm_call:
        _llm_call = llm_call
    if debug_write:
        _debug_write = debug_write

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
    try:
        from core.rule_runtime import invalidate_constraint_cache
        invalidate_constraint_cache()
    except ImportError:
        pass


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


def _condense_fix(user_feedback: str, last_question: str, last_answer: str, raw_fix: str) -> str:
    """用 LLM 把反馈凝结成一句可执行的经验规则。"""
    if not _llm_call:
        return raw_fix
    if not last_question and not user_feedback:
        return raw_fix
    try:
        prompt = (
            "\u4f60\u662f\u7ecf\u9a8c\u51dd\u7ed3\u5668\u3002\u4ee5\u4e0b\u662f\u4e00\u6b21\u5bf9\u8bdd\u7ea0\u504f\uff1a\n"
            f"\u7528\u6237\u4e0a\u4e00\u6b21\u95ee\uff1a\u300c{last_question[:100]}\u300d\n"
            f"AI\u56de\u590d\uff1a\u300c{last_answer[:150]}\u300d\n"
            f"\u7528\u6237\u7ea0\u6b63\u8bf4\uff1a\u300c{user_feedback[:100]}\u300d\n\n"
            "\u8bf7\u7528\u4e00\u53e5\u8bdd\u603b\u7ed3\u8fd9\u6b21\u7ea0\u504f\u7684\u6838\u5fc3\u6559\u8bad\uff0c\u683c\u5f0f\uff1a"
            "\u300c\u5f53\u7528\u6237\u95eeXX\u65f6\uff0c\u4e0d\u8981YY\uff0c\u5e94\u8be5ZZ\u300d\n"
            "\u8981\u6c42\uff1a\n"
            "1. \u53ea\u8f93\u51fa\u4e00\u53e5\u8bdd\uff0c\u4e0d\u8d85\u8fc750\u5b57\n"
            "2. \u5177\u4f53\u53ef\u6267\u884c\uff0c\u4e0d\u8981\u7b3c\u7edf\u7684\u201c\u6ce8\u610f\u7528\u6237\u611f\u53d7\u201d\n"
            "3. \u53bb\u6389\u8868\u60c5/\u8bed\u6c14\u8bcd/\u89d2\u8272\u626e\u6f14"
        )
        result = _llm_call(prompt)
        if result and len(result.strip()) >= 6:
            condensed = result.strip()[:100]
            _debug_write("l7_condense_ok", {"q": last_question[:30], "fix": condensed})
            return condensed
    except Exception as e:
        _debug_write("l7_condense_err", {"err": str(e)})
    return raw_fix


# ── L7 路由约束提取 ──────────────────────────────────────

# 技能关键词 → 技能名映射（用于规则提取快速路径）
_SKILL_KEYWORD_MAP = {
    "\u5929\u6c14": "weather", "\u6c14\u6e29": "weather", "\u67e5\u5929\u6c14": "weather",
    "\u6545\u4e8b": "story", "\u8bb2\u6545\u4e8b": "story",
    "\u6e38\u620f": "run_code", "\u4ee3\u7801": "run_code", "\u8d2a\u5403\u86c7": "run_code",
    "\u753b": "draw", "\u6d77\u62a5": "draw",
    "\u65b0\u95fb": "news", "\u5934\u6761": "news",
    "\u80a1\u7968": "stock", "\u80a1\u4ef7": "stock",
    "\u6587\u7ae0": "article", "\u5199\u7bc7": "article",
}

_LEVEL_TTL = {"session": 1, "short_term": 30, "long_term": 90}


def _extract_routing_constraint(
    user_feedback: str, last_question: str, last_answer: str, classified: dict
) -> dict | None:
    """对意图理解/路由调度类反馈，提取结构化路由约束。
    返回 constraint dict 或 None。在反馈记录时调用（非热路径）。"""
    category = classified.get("category", "")
    if category not in ("\u610f\u56fe\u7406\u89e3", "\u8def\u7531\u8c03\u5ea6"):
        return None

    text = f"{user_feedback} {last_question} {last_answer}".strip()
    level = classified.get("level", "short_term")
    ttl_days = _LEVEL_TTL.get(level, 30)

    # ── 规则快速路径（不调 LLM）──
    skill = None
    for kw, sk in _SKILL_KEYWORD_MAP.items():
        if kw in user_feedback or kw in last_answer[:100]:
            skill = sk
            break

    if skill:
        # 从 last_question 生成阻断模式
        patterns = []
        keywords = []
        lq = last_question.strip()
        if lq and len(lq) >= 2:
            # 取前缀做 glob 模式（如"我在常州" → "我在*"）
            for prefix_len in (2, 3):
                if len(lq) >= prefix_len + 1:
                    patterns.append(lq[:prefix_len] + "*")
        _debug_write("l7_constraint_rule", {"skill": skill, "patterns": patterns, "q": lq[:30]})
        return {
            "type": "block_skill",
            "skill": skill,
            "patterns": patterns,
            "keywords": keywords,
            "confidence": 0.9,
            "ttl_days": ttl_days,
            "created_at": datetime.now().isoformat(),
        }

    # ── LLM 兜底 ──
    if not _llm_call:
        return None
    try:
        skill_names = "\u3001".join(set(_SKILL_KEYWORD_MAP.values()))
        prompt = (
            "\u7528\u6237\u4e0a\u6b21\u8bf4\uff1a\u300c" + last_question[:80] + "\u300d\n"
            "\u7cfb\u7edf\u9519\u8bef\u89e6\u53d1\u4e86\u6280\u80fd\u6267\u884c\u3002\n"
            "\u7528\u6237\u7ea0\u6b63\u8bf4\uff1a\u300c" + user_feedback[:80] + "\u300d\n\n"
            "\u8bf7\u5206\u6790\uff1a\u54ea\u4e2a\u6280\u80fd\u88ab\u9519\u8bef\u89e6\u53d1\uff1f\u4ece\u8fd9\u4e9b\u6280\u80fd\u4e2d\u9009\uff1a" + skill_names + "\n"
            "\u7528\u6237\u539f\u8bdd\u4e2d\u54ea\u4e9b\u8bcd\u5bfc\u81f4\u8bef\u89e6\u53d1\uff1f\n"
            "\u8fd4\u56deJSON\uff1a{\"skill\":\"\u6280\u80fd\u540d\",\"block_keywords\":[\"\u5173\u952e\u8bcd\"]}\n"
            "\u53ea\u8fd4\u56deJSON\u3002"
        )
        result = _llm_call(prompt)
        if result:
            start = result.find("{")
            end = result.rfind("}")
            if start != -1 and end > start:
                parsed = json.loads(result[start:end + 1])
                sk = str(parsed.get("skill", "")).strip()
                bk = parsed.get("block_keywords", [])
                if sk and isinstance(bk, list):
                    _debug_write("l7_constraint_llm", {"skill": sk, "keywords": bk})
                    return {
                        "type": "block_skill",
                        "skill": sk,
                        "patterns": [],
                        "keywords": [str(k) for k in bk if k][:5],
                        "confidence": 0.7,
                        "ttl_days": ttl_days,
                        "created_at": datetime.now().isoformat(),
                    }
    except Exception as e:
        _debug_write("l7_constraint_llm_err", {"err": str(e)})

    return None


def record_feedback_rule(user_feedback: str, last_question: str = "", last_answer: str = "") -> dict:
    rule = classify_feedback(user_feedback, last_question, last_answer)
    # LLM 凝结：把原始 fix 提炼成可执行的经验规则
    raw_fix = rule.get("fix", "")
    if raw_fix and raw_fix != "keep_observing_and_refine":
        rule["fix"] = _condense_fix(user_feedback, last_question, last_answer, raw_fix)
    # 路由约束提取：意图理解/路由调度类反馈生成结构化约束
    constraint = _extract_routing_constraint(user_feedback, last_question, last_answer, rule)
    rules = _load_rules()
    item = {
        "id": f"rule_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source": "user_feedback",
        "created_at": datetime.now().isoformat(),
        "enabled": True,
        "user_feedback": user_feedback,
        "last_question": last_question,
        "last_answer": last_answer,
        "hit_count": 0,
        "fail_count": 0,
        "last_hit_at": None,
        **rule,
    }
    if constraint:
        item["constraint"] = constraint
    rules.append(item)
    _save_rules(rules[-200:])
    return item


def search_relevant_rules(user_input: str, limit: int = 3) -> list[dict]:
    """根据当前用户输入，检索相关的 L7 反馈规则。
    匹配逻辑：关键词重叠 + 场景匹配，返回最相关的 N 条。"""
    text = str(user_input or "").strip()
    if not text or len(text) < 2:
        return []
    rules = _load_rules()
    if not rules:
        return []

    # 提取用户输入的关键词（2字以上的词）
    input_chars = set(text)

    scored = []
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        last_q = str(rule.get("last_question", ""))
        fix = str(rule.get("fix", ""))
        feedback = str(rule.get("user_feedback", ""))
        if not last_q and not fix:
            continue

        score = 0.0
        # 1. 上次问题与当前输入的字符重叠度
        if last_q:
            overlap = len(input_chars & set(last_q))
            score += min(overlap / max(len(input_chars), 1), 1.0) * 0.5
            # 子串匹配加分
            if text[:6] in last_q or last_q[:6] in text:
                score += 0.3

        # 2. 场景关键词匹配
        scene = rule.get("scene", "")
        if scene in ("joke",) and any(k in text for k in ["笑话", "好笑"]):
            score += 0.3
        elif scene in ("story",) and any(k in text for k in ["故事", "讲"]):
            score += 0.3
        elif scene in ("routing",) and any(k in text for k in ["天气", "技能", "查"]):
            score += 0.2

        if score > 0.2:
            scored.append((score, rule))

    scored.sort(key=lambda x: x[0], reverse=True)
    matched = [item[1] for item in scored[:limit]]

    # 效果追踪：命中的规则记录 hit_count
    if matched:
        try:
            all_rules = _load_rules()
            matched_ids = {r.get("id") for r in matched if r.get("id")}
            dirty = False
            for r in all_rules:
                if r.get("id") in matched_ids:
                    r["hit_count"] = (r.get("hit_count") or 0) + 1
                    r["last_hit_at"] = datetime.now().isoformat()
                    dirty = True
            if dirty:
                _save_rules(all_rules)
        except Exception:
            pass

    return matched


def format_l7_context(rules: list[dict]) -> str:
    """把 L7 规则格式化为 prompt 注入文本。"""
    if not rules:
        return ""
    lines = []
    for rule in rules:
        fix = str(rule.get("fix", "")).strip()
        cat = rule.get("category", "")
        last_q = str(rule.get("last_question", ""))[:40]
        feedback = str(rule.get("user_feedback", ""))[:40]
        if fix and fix != "keep_observing_and_refine":
            lines.append(f"\u00b7 [{cat}] {fix}")
        elif last_q and feedback:
            lines.append(f"\u00b7 \u7528\u6237\u95ee\u300c{last_q}\u300d\u65f6\u8bf4\u8fc7\u300c{feedback}\u300d\uff0c\u6ce8\u610f\u907f\u514d\u540c\u6837\u7684\u95ee\u9898")
    return "\n".join(lines)
