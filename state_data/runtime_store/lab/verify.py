from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]


def _score_story_target(goal: str) -> float:
    from core.skills.story import execute

    reply = execute("讲个短故事")
    if not reply:
        return 0.0

    score = 20.0
    if re.search(r"《.+》", reply):
        score += 15.0

    paragraphs = [item.strip() for item in reply.split("\n\n") if item.strip()]
    score += min(len(paragraphs) * 5.0, 20.0)

    length = len(reply)
    if "60秒" in goal or "短视频" in goal:
        if 250 <= length <= 550:
            score += 30.0
        elif 200 <= length <= 700:
            score += 15.0
    else:
        if 400 <= length <= 800:
            score += 30.0
        elif 200 <= length <= 1000:
            score += 15.0

    bad_markers = ("没生成出来", "再说一次", "抱歉", "<think>")
    if not any(marker in reply[:100] for marker in bad_markers):
        score += 15.0
    return score


def _score_weather_target() -> float:
    from core.skills.weather import execute

    reply = execute("常州天气")
    if not reply:
        return 0.0

    score = 30.0
    if re.search(r"\d+\s*[度℃]", reply):
        score += 40.0
    if len(reply) > 20:
        score += 30.0
    return score


def _score_news_target() -> float:
    from core.skills.news import execute

    reply = execute("今日新闻")
    if not reply:
        return 0.0

    score = 20.0
    lines = [line.strip() for line in reply.split("\n") if len(line.strip()) > 10]
    score += min(len(lines) * 10.0, 50.0)
    if len(reply) > 100:
        score += 30.0
    return score


def _score_json_target(target_file: str) -> float:
    try:
        data = json.loads(Path(target_file).read_text(encoding="utf-8"))
    except Exception:
        return 0.0
    return float(50 + len(str(data)) // 10)


def score_target(target_file: str = "", goal: str = "") -> float:
    target = str(target_file or "").strip().replace("\\", "/").lower()
    requested_goal = str(goal or "").strip()

    if "story" in target:
        return _score_story_target(requested_goal)
    if "weather" in target:
        return _score_weather_target()
    if "news" in target:
        return _score_news_target()
    return _score_json_target(target_file)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    target_file = args[0] if len(args) >= 1 else ""
    goal = args[1] if len(args) >= 2 else ""
    try:
        score = score_target(target_file, goal)
    except Exception:
        score = 0.0
    print(score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
