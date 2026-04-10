from __future__ import annotations

"""Mini-game template catalog for run_code.

This module is not a user-facing skill entry. It only stores reusable
template metadata and the logic that turns a vague game request into a
structured game spec.
"""

DEFAULT_TEMPLATE = "brick_breaker"
DEFAULT_THEME = "neon"
TEMPLATE_CHOICE_OPTIONS = ["打砖块（推荐）", "贪吃蛇", "极限闪避", "你来挑一个"]

_TEMPLATE_HINTS = {
    "brick_breaker": ("打砖块", "brick breaker", "breakout", "砖块", "弹球"),
    "snake": ("贪吃蛇", "snake", "吃豆"),
    "dodge": ("躲避", "闪避", "dodge", "survive", "生存", "弹幕", "反应"),
}

_THEME_HINTS = {
    "neon": ("赛博", "霓虹", "cyber", "neon", "未来"),
    "space": ("太空", "宇宙", "星空", "space", "galaxy"),
    "forest": ("森林", "自然", "green", "forest"),
}

_THEMES = {
    "neon": {
        "label": "霓虹",
        "bg1": "#09111f",
        "bg2": "#150d2f",
        "panel": "rgba(8,16,34,0.88)",
        "line": "rgba(85,245,255,0.18)",
        "accent": "#55f5ff",
        "accent2": "#ff6bd6",
        "text": "#eef7ff",
        "muted": "#9bb8d4",
        "danger": "#ff7b7b",
    },
    "space": {
        "label": "星港",
        "bg1": "#040814",
        "bg2": "#101f4d",
        "panel": "rgba(7,14,34,0.88)",
        "line": "rgba(128,184,255,0.18)",
        "accent": "#80b8ff",
        "accent2": "#ffd166",
        "text": "#f4f7ff",
        "muted": "#b3c1e6",
        "danger": "#ff7f96",
    },
    "forest": {
        "label": "林间",
        "bg1": "#07150d",
        "bg2": "#133026",
        "panel": "rgba(9,28,18,0.88)",
        "line": "rgba(104,225,143,0.18)",
        "accent": "#68e18f",
        "accent2": "#d9ff8f",
        "text": "#eefcf1",
        "muted": "#c2e7cb",
        "danger": "#ff9168",
    },
}

_TEMPLATE_META = {
    "brick_breaker": {
        "title": "打砖块",
        "subtitle": "挡板、反弹、清空砖墙，一局就能进入状态。",
        "hint": "鼠标移动或左右方向键控制挡板，空格暂停。",
        "width": 900,
        "height": 540,
        "settings": {"speed": 5.0, "rows": 6, "cols": 9, "paddle": 150},
    },
    "snake": {
        "title": "贪吃蛇",
        "subtitle": "更顺滑的节奏和更干净的反馈，不只是能跑。",
        "hint": "方向键或 WASD 控制移动，空格暂停。",
        "width": 900,
        "height": 540,
        "settings": {"tick": 115},
    },
    "dodge": {
        "title": "极限闪避",
        "subtitle": "一边收集能量，一边躲开高速坠落的障碍。",
        "hint": "鼠标或 WASD 控制角色移动，空格暂停。",
        "width": 900,
        "height": 540,
        "settings": {"spawn": 650, "speed": 5.5},
    },
}


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


def _find_explicit_template(user_request: str) -> str | None:
    text = _normalize_text(user_request)
    for template_name, hints in _TEMPLATE_HINTS.items():
        if any(hint in text for hint in hints):
            return template_name
    return None


def pick_template(user_request: str) -> str:
    return _find_explicit_template(user_request) or DEFAULT_TEMPLATE


def pick_theme(user_request: str) -> str:
    text = _normalize_text(user_request)
    for theme_name, hints in _THEME_HINTS.items():
        if any(hint in text for hint in hints):
            return theme_name
    return DEFAULT_THEME


def needs_template_choice(user_request: str) -> bool:
    text = _normalize_text(user_request)
    if not text:
        return False
    if _find_explicit_template(text):
        return False
    return any(marker in text for marker in ("小游戏", "游戏", "game", "playable", "arcade", "玩玩"))


def get_template_choice_options() -> list[str]:
    return list(TEMPLATE_CHOICE_OPTIONS)


def resolve_template_choice(answer: str, *, fallback_request: str = "") -> str:
    text = _normalize_text(answer)
    explicit = _find_explicit_template(text)
    if explicit:
        return explicit
    if "挑一个" in text or "随机" in text or "随便" in text:
        return _find_explicit_template(fallback_request) or DEFAULT_TEMPLATE
    return _find_explicit_template(fallback_request) or DEFAULT_TEMPLATE


def build_game_spec(user_request: str) -> dict:
    template_name = pick_template(user_request)
    theme_name = pick_theme(user_request)
    meta = dict(_TEMPLATE_META[template_name])
    theme = dict(_THEMES[theme_name])
    return {
        "request_text": str(user_request or "").strip(),
        "template": template_name,
        "theme": theme_name,
        "title": f"{theme['label']}{meta['title']}",
        "subtitle": meta["subtitle"],
        "hint": meta["hint"],
        "width": meta["width"],
        "height": meta["height"],
        "settings": dict(meta["settings"]),
        "palette": theme,
    }
