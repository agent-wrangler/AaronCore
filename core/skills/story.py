# 讲故事技能 - LLM 实时生成
import json
import random
import re
import os
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT_DIR / "memory_db" / "msg_history.json"
STORY_STATE_PATH = ROOT_DIR / "memory_db" / "story_state.json"

FOLLOW_UP_HINTS = ("继续讲", "然后呢", "后来呢", "接着讲", "讲长一点", "有点短", "太短")
NEW_STORY_HINTS = ("再讲一个", "换一个故事", "换个故事", "重新讲一个")

# 主题库：作为 LLM 的创意种子，不再拼模板
THEMES = [
    {
        "id": "forest_fox",
        "keywords": ["狐狸", "森林", "月亮", "萤火虫"],
        "seed": "月灯森林里的小狐狸阿雾，想找到一口会唱歌的月光井，让整片森林重新亮起来。它有一枚会发热的银叶钥匙，还有一只总爱绕着它打转的萤火虫小灯陪着它。",
    },
    {
        "id": "clock_robot",
        "keywords": ["机器人", "星星", "宇宙", "天文台"],
        "seed": "海边山坡上的旧天文台里住着小机器人零零，它想修好停了很多年的星图机，替大家重新找到夜空的方向。它有一枚刻着星轨的黄铜齿轮，还有一只总把信纸叼来叼去的纸星鸟陪着它。",
    },
    {
        "id": "seaside_cat",
        "keywords": ["猫", "小猫", "面包", "海边", "小镇"],
        "seed": "白石小镇的海风面包店里住着小猫云朵，它想在黎明前做出一炉能安慰失眠人的好梦面包。它有一本边角都卷起来的旧食谱，还有住在钟楼里的老燕子阿针帮它。",
    },
    {
        "id": "lake_whale",
        "keywords": ["鲸鱼", "湖", "梦", "夜晚", "治愈"],
        "seed": "玻璃星湖里住着小鲸鱼蓝葡萄，它想学会在夜里唱出一首能让自己安心睡着的歌。它有一片会在水里发出微光的贝壳，还有一位总是慢慢说话的乌龟邮差陪着它。",
    },
]


def _load_llm_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'llm_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        # 新格式：models + default
        if "models" in raw:
            default = raw.get("default", "")
            models = raw["models"]
            return models.get(default) or next(iter(models.values()))
        # 旧格式：顶层 api_key/model/base_url
        return raw
    except Exception:
        return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


def _llm_generate(prompt: str, max_tokens: int = 2000) -> str:
    """直接调 LLM API 生成故事，不走 think() 避免人格指令干扰"""
    import requests
    cfg = _load_llm_config()
    if not cfg.get("api_key"):
        return ""
    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.85,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return ""
        return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception:
        return ""


def _load_story_state() -> dict:
    try:
        if STORY_STATE_PATH.exists():
            data = json.loads(STORY_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_story_state(state: dict):
    STORY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORY_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _find_theme_by_id(theme_id: str):
    for theme in THEMES:
        if theme["id"] == theme_id:
            return theme
    return None


def _detect_theme(text: str):
    lowered = str(text or "").lower()
    for theme in THEMES:
        for keyword in theme["keywords"]:
            if keyword.lower() in lowered:
                return theme
    return None


def _pick_theme(query: str, state: dict):
    requested = _detect_theme(query)
    if requested:
        return requested

    previous = _find_theme_by_id(state.get("theme_id", "")) if state else None

    if any(word in query for word in NEW_STORY_HINTS) and previous:
        others = [t for t in THEMES if t["id"] != previous["id"]]
        if others:
            return random.choice(others)

    # 不再因为"故事"两个字就返回上一个主题，每次随机选
    return random.choice(THEMES)


def _generate_new_story(theme: dict, query: str) -> str:
    seed = theme["seed"]
    mood = ""
    if any(w in query for w in ("睡前", "治愈", "温柔", "安慰")):
        mood = "风格要温柔治愈，适合睡前听。"
    elif any(w in query for w in ("冒险", "刺激", "紧张")):
        mood = "风格要有冒险感，节奏紧凑一点。"
    else:
        mood = "风格温暖自然，有画面感。"

    prompt = (
        f"请根据下面的故事种子，写一个完整的短篇童话故事。\n\n"
        f"故事种子：{seed}\n\n"
        f"要求：\n"
        f"1. {mood}\n"
        f"2. 故事要有起承转合，有一个温暖的结尾\n"
        f"3. 篇幅 400-600 字左右\n"
        f"4. 给故事起一个好听的标题，用《》包裹，放在开头\n"
        f"5. 段落之间空一行\n"
        f"6. 直接输出故事，不要加任何解释\n"
    )
    return _llm_generate(prompt)


def _generate_continuation(theme: dict, previous_text: str, chapter: int, query: str) -> str:
    seed = theme["seed"]
    # 只取上一章的前 500 字作为上下文，避免 prompt 太长
    prev_summary = previous_text[:500]
    if len(previous_text) > 500:
        prev_summary += "..."

    prompt = (
        f"这是一个连载童话故事的续写。\n\n"
        f"故事背景：{seed}\n\n"
        f"上一章内容：\n{prev_summary}\n\n"
        f"要求：\n"
        f"1. 写第{chapter}章，自然接续上一章的情节\n"
        f"2. 引入新的小波折或发现，但整体温暖\n"
        f"3. 篇幅 400-600 字左右\n"
        f"4. 开头标注章节（如《标题\u00b7第X章》）\n"
        f"5. 段落之间空一行\n"
        f"6. 直接输出故事，不要加任何解释\n"
    )
    return _llm_generate(prompt)


def execute(topic=""):
    query = str(topic or "").strip()
    state = _load_story_state()
    follow_up = any(word in query for word in FOLLOW_UP_HINTS)
    should_continue = bool(follow_up and state and state.get("theme_id"))

    if should_continue:
        theme = _find_theme_by_id(state.get("theme_id", "")) or _pick_theme(query, state)
        chapter = int(state.get("chapter", 1) or 1) + 1
        previous_text = str(state.get("last_story_text", ""))
        story_text = _generate_continuation(theme, previous_text, chapter, query)
        if not story_text:
            story_text = f"这一章人家没接住，你再戳我一下试试。"
        new_state = {
            "theme_id": theme["id"],
            "chapter": chapter,
            "last_query": query,
            "last_story_text": story_text[:800],
            "updated_at": datetime.now().isoformat(),
        }
    else:
        theme = _pick_theme(query, state)
        story_text = _generate_new_story(theme, query)
        if not story_text:
            story_text = f"故事没生成出来，你再说一次，我重新给你讲。"
        new_state = {
            "theme_id": theme["id"],
            "chapter": 1,
            "last_query": query,
            "last_story_text": story_text[:800],
            "updated_at": datetime.now().isoformat(),
        }

    _save_story_state(new_state)
    return story_text
