import json
import os
import random
import re
from datetime import datetime
from pathlib import Path

from core.skills.save_export import execute as save_export_execute
from storage.paths import PRIMARY_HISTORY_FILE, STORY_STATE_FILE


ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORY_PATH = PRIMARY_HISTORY_FILE
STORY_STATE_PATH = STORY_STATE_FILE
STORY_DIR = Path.home() / "Desktop" / "Nova故事"


THEMES = [
    {
        "id": "forest_fox",
        "seed": (
            "月灯森林里的小狐狸阿雾，想找到一口会唱歌的月光井，让整片森林重新亮起来。"
            "它有一枚会发热的银叶钥匙，还有一只总爱绕着它打转的萤火虫小灯陪着它。"
        ),
    },
    {
        "id": "clock_robot",
        "seed": (
            "海边山坡上的旧天文台里住着小机器人零零，它想修好停了很多年的星图机，"
            "替大家重新找到夜空的方向。它有一枚刻着星轨的黄铜齿轮，还有一只总把信纸叼来叼去的纸星鸟陪着它。"
        ),
    },
    {
        "id": "seaside_cat",
        "seed": (
            "白石小镇的海风面包店里住着小猫云朵，它想在黎明前做出一炉能安慰失眠人的好梦面包。"
            "它有一本边角都卷起来的旧食谱，还有住在钟楼里的老燕子阿针帮它。"
        ),
    },
    {
        "id": "lake_whale",
        "seed": (
            "玻璃星湖里住着小鲸鱼蓝葡萄，它想学会在夜里唱出一首能让自己安心睡着的歌。"
            "它有一片会在水里发出微光的贝壳，还有一位总是慢慢说话的乌龟邮差陪着它。"
        ),
    },
]


def _load_llm_config():
    try:
        from brain import get_current_llm_config

        cfg = get_current_llm_config()
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


def _llm_generate(prompt: str, max_tokens: int = 2000) -> str:
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


def _compact_story_query(text: str) -> str:
    cleaned = re.sub(r"[\s，。？！、,.!?]", "", str(text or ""))
    return cleaned.strip("啊呀呢吗嘛吧啦")


def _should_continue_story(query: str, state: dict) -> bool:
    if not state or not state.get("theme_id"):
        return False
    compact = _compact_story_query(query)
    return not compact or len(compact) <= 4


def _pick_theme(state: dict, *, continue_story: bool):
    previous = _find_theme_by_id(str((state or {}).get("theme_id") or ""))
    if continue_story and previous:
        return previous
    if previous:
        others = [theme for theme in THEMES if theme["id"] != previous["id"]]
        if others:
            return random.choice(others)
    return random.choice(THEMES)


def _generate_new_story(theme: dict, query: str) -> str:
    seed = theme["seed"]
    user_hint = str(query or "").strip()
    prompt = (
        "请根据下面的故事种子，写一个适合 60 秒短视频口播的中文童话故事。\n\n"
        f"故事种子：{seed}\n\n"
        f"用户这轮补充：{user_hint or '自由发挥，但要自然温暖。'}\n\n"
        "要求：\n"
        "1. 故事要有起承转合，有一个温暖的结尾。\n"
        "2. 篇幅 120-150 字左右，适合短视频口播。\n"
        "3. 给故事起一个好听的标题，用《》包起来放在开头。\n"
        "4. 段落之间空一行。\n"
        "5. 直接输出故事，不要加解释。\n"
        "6. 故事内容要完整独立，不要出现“未完待续”“下一章”等连载暗示。\n"
        "7. 故事正文前，用【】标一个 15 字以内的短视频文案建议。\n"
        "8. 故事正文后，用【】标一个 15 字以内的话题标签建议。\n"
        "9. 故事正文里，用【】标 1-2 处适合短视频画面切换或特效的提示。\n"
        "10. 故事正文里，用【】标 1 处适合 BGM 情绪变化的提示。\n"
        "11. 故事正文里，用【】标 1 处适合字幕特效的提示。\n"
    )
    return _llm_generate(prompt)


def _generate_continuation(theme: dict, previous_text: str, chapter: int, query: str) -> str:
    seed = theme["seed"]
    prev_summary = previous_text[:500]
    if len(previous_text) > 500:
        prev_summary += "..."

    prompt = (
        "这是一个连载童话故事的续写。\n\n"
        f"故事背景：{seed}\n\n"
        f"上一章内容：\n{prev_summary}\n\n"
        f"用户这轮补充：{str(query or '').strip() or '自然承接上一章。'}\n\n"
        "要求：\n"
        f"1. 写第 {chapter} 章，自然接续上一章的情节。\n"
        "2. 引入新的小波折或发现，但整体保持温暖。\n"
        "3. 篇幅 120-150 字左右，适合短视频口播。\n"
        "4. 开头标注章节（例如《标题·第二章》）。\n"
        "5. 段落之间空一行。\n"
        "6. 直接输出故事，不要加解释。\n"
        "7. 故事结构紧凑，适合短视频传播。\n"
        "8. 故事正文前，用【】标一个 15 字以内的短视频文案建议。\n"
        "9. 故事正文后，用【】标一个 15 字以内的话题标签建议。\n"
        "10. 故事正文里，用【】标 1-2 处适合短视频画面切换或特效的提示。\n"
        "11. 故事正文里，用【】标 1 处适合 BGM 情绪变化的提示。\n"
        "12. 故事正文里，用【】标 1 处适合字幕特效的提示。\n"
    )
    return _llm_generate(prompt)


def execute(topic=""):
    query = str(topic or "").strip()
    state = _load_story_state()
    save_to_desktop = "桌面" in query
    should_continue = _should_continue_story(query, state)
    theme = _pick_theme(state, continue_story=should_continue)

    if should_continue:
        chapter = int(state.get("chapter", 1) or 1) + 1
        previous_text = str(state.get("last_story_text", ""))
        story_text = _generate_continuation(theme, previous_text, chapter, query)
        if not story_text:
            story_text = "这一章我没接稳，你再戳我一下试试。"
        new_state = {
            "theme_id": theme["id"],
            "chapter": chapter,
            "last_query": query,
            "last_story_text": story_text[:800],
            "updated_at": datetime.now().isoformat(),
        }
    else:
        story_text = _generate_new_story(theme, query)
        if not story_text:
            story_text = "故事没生成出来，你再说一次，我重新给你讲。"
        new_state = {
            "theme_id": theme["id"],
            "chapter": 1,
            "last_query": query,
            "last_story_text": story_text[:800],
            "updated_at": datetime.now().isoformat(),
        }

    _save_story_state(new_state)
    if save_to_desktop and story_text:
        try:
            save_reply = save_export_execute(
                query,
                {
                    "fs_action": {
                        "payload": {"content": story_text, "format": "md"},
                        "destination": {"path": str(STORY_DIR)},
                    },
                    "save_filename": re.sub(r'[\\/:*?"<>|]', "", query).strip()[:30] or "故事",
                    "save_content": story_text,
                    "save_format": "md",
                    "save_destination": str(STORY_DIR),
                },
            )
            return f"故事写好了，已经保存啦：{save_reply}\n\n{story_text}"
        except Exception as exc:
            return f"故事写出来了，但保存失败：{exc}\n\n{story_text}"
    return story_text
