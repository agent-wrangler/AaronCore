"""实验室验证脚本 — 根据目标评估技能输出"""
import sys
import re

sys.path.insert(0, ".")

target_file = sys.argv[1] if len(sys.argv) > 1 else ""
goal = sys.argv[2] if len(sys.argv) > 2 else ""

score = 0

# 根据目标文件类型执行
if "story" in target_file:
    from core.skills.story import execute
    r = execute("讲个短故事")
    if not r:
        print(0)
        sys.exit()
    length = len(r)
    # 基础分：能跑出来就有分
    score += 20
    # 有标题
    if re.search(r"《.+》", r):
        score += 15
    # 有分段（至少3段）
    paragraphs = [p.strip() for p in r.split("\n\n") if p.strip()]
    score += min(len(paragraphs) * 5, 20)
    # 字数评估（根据目标调整）
    if "60秒" in goal or "短视频" in goal:
        # 60秒约300-500字
        if 250 <= length <= 550:
            score += 30
        elif 200 <= length <= 700:
            score += 15
    else:
        # 默认400-800字
        if 400 <= length <= 800:
            score += 30
        elif 200 <= length <= 1000:
            score += 15
    # 没有报错/废话
    bad = ["没生成出来", "再说一次", "抱歉", "<think>"]
    if not any(b in r[:100] for b in bad):
        score += 15

elif "weather" in target_file:
    from core.skills.weather import execute
    r = execute("常州天气")
    if not r:
        print(0)
        sys.exit()
    score += 30
    if re.search(r"\d+\s*[°℃]", r):
        score += 40
    if len(r) > 20:
        score += 30

elif "news" in target_file:
    from core.skills.news import execute
    r = execute("今日新闻")
    if not r:
        print(0)
        sys.exit()
    score += 20
    lines = [l.strip() for l in r.split("\n") if len(l.strip()) > 10]
    score += min(len(lines) * 10, 50)
    if len(r) > 100:
        score += 30

else:
    # 配置文件类：检查 JSON 合法性
    import json
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        score = 50 + len(str(data)) // 10
    except Exception:
        score = 0

print(score)
