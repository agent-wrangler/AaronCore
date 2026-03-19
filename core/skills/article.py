# 写文章技能 - 新闻 → 文章生成 → 桌面保存 → 用户可控
import requests
import json
import os
import re
import time
from datetime import date

# 状态文件：缓存新闻列表 + 最近生成的文章
_state_path = os.path.join(os.path.dirname(__file__), '.article_state.json')

# 文章保存目录
ARTICLE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "Nova\u65b0\u95fb")

# LLM 配置
_llm_config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'llm_config.json')


def _load_llm_config():
    try:
        with open(_llm_config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if "models" in raw:
            default = raw.get("default", "")
            models = raw["models"]
            return models.get(default) or next(iter(models.values()))
        return raw
    except Exception:
        return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


def _llm_call(prompt, max_tokens=3000, temperature=0.75):
    cfg = _load_llm_config()
    if not cfg.get("api_key"):
        return None
    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        return None


# ── 状态管理 ──

def _save_state(news_list=None, last_article=None):
    existing = {}
    try:
        with open(_state_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except Exception:
        pass
    existing["time"] = time.time()
    if news_list is not None:
        existing["news"] = news_list
    if last_article is not None:
        existing["last_article"] = last_article
    try:
        with open(_state_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False)
    except Exception:
        pass


def _load_state():
    """加载新闻列表缓存（10分钟有效）"""
    try:
        with open(_state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if time.time() - data.get("time", 0) > 600:
            return None
        return data.get("news")
    except Exception:
        return None


def _load_full_state():
    """加载完整状态（30分钟有效）"""
    try:
        with open(_state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if time.time() - data.get("time", 0) > 1800:
            return None
        return data
    except Exception:
        return None


# ── 文件保存 ──

def _save_article_to_desktop(article_text, news_title):
    os.makedirs(ARTICLE_DIR, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', '', news_title)[:30].strip()
    today = date.today().strftime("%Y-%m-%d")
    filename = f"{today}_{safe_title}.md"
    filepath = os.path.join(ARTICLE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(article_text)
    return filepath


def _extract_article_title(article_text):
    for line in (article_text or "").split("\n"):
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return ""


# ── 新闻抓取（复用 news 技能内部函数）──

def _fetch_news(topic=None):
    from core.skills.news import _parse_rss, _fetch_newsapi
    from core.skills.news import TOPIC_URLS, RSS_URL, BBC_RSS, AP_RSS

    t = topic or None
    all_news = []

    gn_url = TOPIC_URLS.get(t, RSS_URL) if t else RSS_URL
    gn_list, _ = _parse_rss(gn_url, limit=4)
    if gn_list:
        all_news.extend(gn_list)

    bbc_url = BBC_RSS.get(t, BBC_RSS["top"]) if t else BBC_RSS["top"]
    bbc_list, _ = _parse_rss(bbc_url, limit=4)
    if bbc_list:
        for item in bbc_list:
            if not item.get("source"):
                item["source"] = "BBC"
        all_news.extend(bbc_list)

    ap_url = AP_RSS.get(t, AP_RSS["top"]) if t else AP_RSS["top"]
    ap_list, _ = _parse_rss(ap_url, limit=3)
    if ap_list:
        for item in ap_list:
            if not item.get("source"):
                item["source"] = "AP News"
        all_news.extend(ap_list)

    na_list, _ = _fetch_newsapi(t, limit=2)
    if na_list:
        all_news.extend(na_list)

    seen = set()
    unique = []
    for item in all_news:
        key = re.sub(r'\s+', '', item["title"][:20]).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:10]


# ── LLM 生成 ──

def _ai_pick_best(news_list):
    titles = "\n".join(f"{i+1}. {item['title']} [{item['source']}]" for i, item in enumerate(news_list))
    prompt = (
        "\u4e0b\u9762\u662f\u4eca\u5929\u7684\u65b0\u95fb\u6807\u9898\u5217\u8868\uff1a\n\n"
        + titles + "\n\n"
        "\u4ece\u4e2d\u9009\u51fa\u6700\u9002\u5408\u5199\u6210\u5934\u6761\u53f7\u6587\u7ae0\u7684 1 \u6761\uff08\u8bdd\u9898\u6027\u5f3a\u3001\u8bfb\u8005\u5173\u6ce8\u5ea6\u9ad8\u3001\u6709\u5c55\u5f00\u7a7a\u95f4\uff09\u3002\n"
        "\u53ea\u8fd4\u56de\u5e8f\u53f7\u6570\u5b57\uff0c\u4e0d\u8981\u5176\u4ed6\u5185\u5bb9\u3002"
    )
    result = _llm_call(prompt, max_tokens=10, temperature=0.3)
    if result:
        match = re.search(r'(\d+)', result.strip())
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(news_list):
                return idx
    return 0


def _generate_article(news_item):
    title = news_item.get("title", "")
    source = news_item.get("source", "")
    prompt = (
        "\u4f60\u662f\u4e00\u4e2a\u5934\u6761\u53f7\u81ea\u5a92\u4f53\u4f5c\u8005\uff0c\u64c5\u957f\u5199\u4fe1\u606f\u91cf\u5927\u3001\u8282\u594f\u660e\u5feb\u7684\u8d44\u8baf\u6587\u7ae0\u3002\n\n"
        "\u65b0\u95fb\u7d20\u6750\uff1a\n"
        "\u6807\u9898\uff1a" + title + "\n"
        "\u6765\u6e90\uff1a" + source + "\n\n"
        "\u8bf7\u6839\u636e\u8fd9\u6761\u65b0\u95fb\u7d20\u6750\uff0c\u5199\u4e00\u7bc7\u5934\u6761\u53f7\u98ce\u683c\u7684\u4e2d\u6587\u6587\u7ae0\u3002\u8981\u6c42\uff1a\n\n"
        "1. \u6807\u9898\uff1a\u5438\u5f15\u773c\u7403\u4f46\u4e0d\u6807\u9898\u515a\uff0c15-25\u5b57\n"
        "2. \u6b63\u6587 800-1200 \u5b57\uff0c\u5206 3-5 \u4e2a\u6bb5\u843d\n"
        "3. \u5f00\u5934\u7528\u4e00\u53e5\u8bdd\u6293\u4f4f\u8bfb\u8005\u6ce8\u610f\u529b\n"
        "4. \u4e2d\u95f4\u5c55\u5f00\u4e8b\u4ef6\u80cc\u666f\u3001\u5173\u952e\u7ec6\u8282\u3001\u5404\u65b9\u53cd\u5e94\n"
        "5. \u7ed3\u5c3e\u7ed9\u51fa\u7b80\u77ed\u89c2\u70b9\u6216\u5f15\u53d1\u601d\u8003\u7684\u95ee\u9898\n"
        "6. \u8bed\u6c14\uff1a\u4e13\u4e1a\u4f46\u4e0d\u67af\u71e5\uff0c\u50cf\u4e00\u4e2a\u61c2\u884c\u7684\u670b\u53cb\u5728\u8ddf\u4f60\u804a\n"
        "7. \u4e0d\u8981\u7528\u201c\u636e\u6089\u201d\u201c\u4f17\u6240\u5468\u77e5\u201d\u8fd9\u7c7b\u5957\u8bdd\n"
        "8. \u9002\u5f53\u52a0\u7c97\u5173\u952e\u4fe1\u606f\uff08\u7528 **\u52a0\u7c97** \u683c\u5f0f\uff09\n\n"
        "\u8f93\u51fa\u683c\u5f0f\uff1a\n# \u6807\u9898\n\n\u6b63\u6587\u5185\u5bb9..."
    )
    result = _llm_call(prompt, max_tokens=3000, temperature=0.75)
    if not result or len(result) < 100:
        return None
    return result.strip()


# ── 意图检测 ──

def _is_ai_pick(query):
    patterns = [
        r'(你|AI|ai|Nova|nova).{0,4}(选|挑|找)',
        r'(帮我|给我).{0,4}(选|挑)',
        r'(随便|随机).{0,4}(选|写|来)',
        r'自己选',
    ]
    return any(re.search(p, query) for p in patterns)


def _is_number_selection(query):
    match = re.match(r'^\s*(\d{1,2})\s*$', query.strip())
    if match:
        return int(match.group(1))
    match = re.search(r'\u7b2c\s*(\d{1,2})\s*[\u6761\u4e2a\u7bc7]', query)
    if match:
        return int(match.group(1))
    # "帮我把1写成文章""把3号写一篇""1写成文章"
    match = re.search(r'[\u628a\u5c06]?\s*(\d{1,2})\s*[\u53f7\u6761]?\s*[\u5199\u751f\u6210]', query)
    if match:
        return int(match.group(1))
    return None


def _is_rewrite_request(query):
    return any(w in query for w in ("重写", "不满意", "再写一遍", "重新写", "换个写法"))


def _is_self_edit_request(query):
    return any(w in query for w in ("我自己改", "我来改", "自己编辑", "我改"))


def _is_satisfied(query):
    return any(w in query for w in ("可以", "满意", "不错", "挺好", "OK", "ok", "好的", "定稿"))


def _detect_topic_from_query(query):
    q = (query or "").lower()
    if any(w in q for w in ("科技", "tech", "ai")):
        return "科技"
    if any(w in q for w in ("商业", "经济", "财经")):
        return "商业"
    if any(w in q for w in ("国际", "世界")):
        return "世界"
    return None


# ── 生成文章后的统一返回 ──

def _build_summary(news_item, article_text, filepath, prefix="文章写好了，已经存到桌面啦"):
    art_title = _extract_article_title(article_text) or news_item.get("title", "")
    src = news_item.get("source", "")
    return (
        f"{prefix}\n\n"
        f"**{art_title}**\n"
        f"\u6765\u6e90\uff1a{src}\n"
        f"\u6587\u4ef6\uff1a`{filepath}`\n\n"
        "\u4f60\u770b\u770b\u6ee1\u4e0d\u6ee1\u610f\uff1f\u4e0d\u6ee1\u610f\u8bf4\u300c\u91cd\u5199\u300d\uff0c\u60f3\u81ea\u5df1\u6539\u5c31\u8bf4\u300c\u6211\u81ea\u5df1\u6539\u300d"
    )


# ── 主入口 ──

def execute(query, context=None):
    query = str(query or "").strip()

    # ── 重写 ──
    if _is_rewrite_request(query):
        state = _load_full_state()
        last = (state or {}).get("last_article")
        if last:
            news_item = last["news_item"]
            article = _generate_article(news_item)
            if article:
                fp = _save_article_to_desktop(article, news_item.get("title", ""))
                _save_state(last_article={"news_item": news_item, "file_path": fp, "article_text": article})
                return _build_summary(news_item, article, fp, "\u91cd\u65b0\u5199\u4e86\u4e00\u7248\uff0c\u5b58\u5230\u684c\u9762\u4e86")
            return "\u91cd\u5199\u5931\u8d25\u4e86\uff0c\u518d\u6765\u4e00\u6b21\uff1f"
        return "\u6ca1\u627e\u5230\u4e0a\u4e00\u7bc7\u6587\u7ae0\u7684\u8bb0\u5f55\uff0c\u4f60\u5148\u8ba9\u6211\u6293\u65b0\u95fb\u518d\u5199\u5427"

    # ── 自己改 ──
    if _is_self_edit_request(query):
        state = _load_full_state()
        last = (state or {}).get("last_article")
        if last:
            fp = last["file_path"]
            return f"\u6587\u4ef6\u5728\u8fd9\u91cc\uff1a`{fp}`\n\n\u4f60\u76f4\u63a5\u7528\u7f16\u8f91\u5668\u6253\u5f00\u6539\u5c31\u884c\uff0c\u6539\u5b8c\u4e86\u8ddf\u6211\u8bf4\u4e00\u58f0"
        return "\u6ca1\u627e\u5230\u4e0a\u4e00\u7bc7\u6587\u7ae0\uff0c\u4f60\u5148\u8ba9\u6211\u5199\u4e00\u7bc7\u518d\u8bf4"

    # ── 满意/定稿 ──
    if _is_satisfied(query):
        state = _load_full_state()
        last = (state or {}).get("last_article")
        if last:
            fp = last["file_path"]
            return f"\u597d\u5634\uff0c\u6587\u7ae0\u5b9a\u7a3f\u4e86\uff0c\u5728\u684c\u9762 Nova\u65b0\u95fb \u6587\u4ef6\u5939\u91cc\uff1a`{fp}`"
        # 没有文章上下文，不拦截，让它 fall through

    # ── 选序号 ──
    pick = _is_number_selection(query)
    if pick is not None:
        cached = _load_state()
        if cached and 1 <= pick <= len(cached):
            news_item = cached[pick - 1]
            article = _generate_article(news_item)
            if article:
                fp = _save_article_to_desktop(article, news_item.get("title", ""))
                _save_state(last_article={"news_item": news_item, "file_path": fp, "article_text": article})
                return _build_summary(news_item, article, fp)
            return "\u6587\u7ae0\u751f\u6210\u5931\u8d25\u4e86\uff0cLLM \u53ef\u80fd\u6ca1\u63a5\u4f4f\uff0c\u518d\u8bd5\u4e00\u6b21\uff1f"
        return "\u6ca1\u627e\u5230\u5bf9\u5e94\u7684\u65b0\u95fb\uff0c\u4f60\u5148\u8ba9\u6211\u6293\u4e00\u6ce2\u65b0\u95fb\u518d\u9009\u5427"

    # ── AI 自己选 ──
    if _is_ai_pick(query):
        topic = _detect_topic_from_query(query)
        news_list = _fetch_news(topic)
        if not news_list:
            return "\u65b0\u95fb\u90fd\u6ca1\u6293\u5230\uff0c\u5199\u4e0d\u4e86\u6587\u7ae0\uff0c\u5148\u68c0\u67e5\u4e0b\u7f51\u7edc\u548c\u4ee3\u7406"
        _save_state(news_list=news_list)
        idx = _ai_pick_best(news_list)
        news_item = news_list[idx]
        article = _generate_article(news_item)
        if article:
            fp = _save_article_to_desktop(article, news_item.get("title", ""))
            _save_state(last_article={"news_item": news_item, "file_path": fp, "article_text": article})
            return _build_summary(news_item, article, fp, "\u6211\u6311\u4e86\u4e00\u6761\u5199\u597d\u4e86\uff0c\u5b58\u5230\u684c\u9762\u4e86")
        return "\u9009\u597d\u4e86\u4f46\u6587\u7ae0\u6ca1\u751f\u6210\u51fa\u6765\uff0c\u518d\u6765\u4e00\u6b21\uff1f"

    # ── 默认：展示新闻列表让用户选 ──
    topic = _detect_topic_from_query(query)
    news_list = _fetch_news(topic)
    if not news_list:
        return "\u65b0\u95fb\u90fd\u6ca1\u6293\u5230\uff0c\u5199\u4e0d\u4e86\u6587\u7ae0\uff0c\u5148\u68c0\u67e5\u4e0b\u7f51\u7edc\u548c\u4ee3\u7406"
    _save_state(news_list=news_list)

    lines = []
    for i, item in enumerate(news_list, 1):
        lines.append(f"{i}. {item['title']} [{item['source']}]")
    listing = "\n".join(lines)

    return (
        "\u6293\u5230\u8fd9\u4e9b\u65b0\u95fb\uff0c\u4f60\u9009\u54ea\u6761\u5199\uff1f\u56de\u590d\u5e8f\u53f7\u5c31\u884c\uff1a\n\n"
        + listing + "\n\n"
        "\u6216\u8005\u8bf4\u300c\u4f60\u9009\u4e00\u4e2a\u5199\u300d\u8ba9\u6211\u6765\u6311\u3002"
    )
