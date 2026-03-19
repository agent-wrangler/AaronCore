# 新闻抓取技能 - 多源聚合（Google News / BBC / NewsAPI / AP News）
import requests
import json
import os
import re
import xml.etree.ElementTree as ET

# 代理配置（本机翻墙代理）
PROXIES = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890",
}

# RSS 源：Google News 美国英文版（热门新闻）
RSS_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

# 分类 RSS（按话题）
TOPIC_URLS = {
    "科技": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "商业": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "世界": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
}

# BBC RSS 源（英文，走代理）
BBC_RSS = {
    "top": "http://feeds.bbci.co.uk/news/rss.xml",
    "科技": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "商业": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "世界": "http://feeds.bbci.co.uk/news/world/rss.xml",
}

# AP News RSS（通过 RSS 聚合）
AP_RSS = {
    "top": "https://rsshub.app/apnews/topics/apf-topnews",
    "科技": "https://rsshub.app/apnews/topics/apf-technology",
    "商业": "https://rsshub.app/apnews/topics/apf-business",
    "世界": "https://rsshub.app/apnews/topics/apf-WorldNews",
}

# NewsAPI（需要 API key，存在 news_config.json）
NEWSAPI_BASE = "https://newsapi.org/v2/top-headlines"
NEWSAPI_TOPICS = {"科技": "technology", "商业": "business", "世界": "general"}

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


_news_config_path = os.path.join(os.path.dirname(__file__), 'news_config.json')


def _load_news_config():
    try:
        with open(_news_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _translate_titles(titles):
    """用 LLM 批量翻译英文标题为中文"""
    cfg = _load_llm_config()
    if not cfg.get("api_key"):
        return None

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    prompt = f"""把下面的英文新闻标题逐条翻译成中文，保持序号，每行一条，只输出翻译结果：

{numbered}"""

    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500},
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        # 解析翻译结果
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        result = []
        for line in lines:
            # 去掉序号前缀 "1. " "1、" 等
            cleaned = re.sub(r'^\d+[\.\、\)\s]+', '', line).strip()
            if cleaned:
                result.append(cleaned)
        # 宽松匹配：数量一致直接用；多了截断；少了补英文原文
        if len(result) >= len(titles):
            return result[:len(titles)]
        if len(result) >= len(titles) * 0.6:
            return result + [titles[i] for i in range(len(result), len(titles))]
        return None
    except Exception:
        return None


def _classify_news(news_list):
    """简单按关键词把新闻分板块"""
    categories = {
        "国际局势": [],
        "科技": [],
        "商业财经": [],
        "社会民生": [],
    }
    keywords_map = {
        "国际局势": ["war", "iran", "trump", "israel", "attack", "strike", "military", "nuclear",
                    "russia", "ukraine", "china", "nato", "sanctions", "diplomat", "congress",
                    "senate", "president", "minister", "hezbollah", "hamas"],
        "科技": ["ai", "tech", "apple", "google", "microsoft", "chip", "robot", "software",
                "ios", "android", "macbook", "nvidia", "openai", "startup", "cyber"],
        "商业财经": ["oil", "price", "stock", "market", "economy", "trade", "bank", "fed",
                    "inflation", "gdp", "airline", "energy", "business", "deal", "billion"],
    }
    for item in news_list:
        title_lower = item["title"].lower()
        placed = False
        for cat, kws in keywords_map.items():
            if any(kw in title_lower for kw in kws):
                categories[cat].append(item)
                placed = True
                break
        if not placed:
            categories["社会民生"].append(item)
    # 去掉空板块
    return {k: v for k, v in categories.items() if v}


def _parse_rss(url, limit=10):
    """抓取并解析 RSS，返回新闻列表"""
    try:
        resp = requests.get(url, proxies=PROXIES, timeout=15)
        if resp.status_code != 200:
            return None, f"请求失败，状态码 {resp.status_code}"
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        news_list = []
        for item in items[:limit]:
            title = (item.find("title").text or "") if item.find("title") is not None else ""
            source = (item.find("source").text or "") if item.find("source") is not None else ""
            link = (item.find("link").text or "") if item.find("link") is not None else ""
            pub = (item.find("pubDate").text or "") if item.find("pubDate") is not None else ""
            if " - " in title and source and title.endswith(source):
                title = title[:title.rfind(" - ")].strip()
            news_list.append({
                "title": title,
                "source": source,
                "link": link,
                "pubDate": pub,
            })
        return news_list, None
    except requests.exceptions.ProxyError:
        return None, "代理连接失败，请确认翻墙代理（127.0.0.1:7890）是否开启"
    except requests.exceptions.Timeout:
        return None, "请求超时，网络可能不太稳定"
    except Exception as e:
        return None, f"抓取失败: {str(e)[:80]}"


def _fetch_newsapi(topic=None, limit=5):
    """从 NewsAPI 抓取新闻（需要 API key）"""
    cfg = _load_news_config()
    api_key = cfg.get("newsapi_key", "")
    if not api_key:
        return [], None  # 没配 key，静默跳过

    params = {"apiKey": api_key, "language": "en", "pageSize": limit, "country": "us"}
    if topic and topic in NEWSAPI_TOPICS:
        params["category"] = NEWSAPI_TOPICS[topic]

    try:
        resp = requests.get(NEWSAPI_BASE, params=params, proxies=PROXIES, timeout=15)
        if resp.status_code != 200:
            return [], f"NewsAPI {resp.status_code}"
        articles = resp.json().get("articles", [])
        news_list = []
        for art in articles[:limit]:
            title = art.get("title", "")
            source = (art.get("source") or {}).get("name", "NewsAPI")
            link = art.get("url", "")
            pub = art.get("publishedAt", "")
            if " - " in title and source and title.endswith(source):
                title = title[:title.rfind(" - ")].strip()
            news_list.append({"title": title, "source": source, "link": link, "pubDate": pub})
        return news_list, None
    except Exception as e:
        return [], f"NewsAPI: {str(e)[:60]}"


def _detect_topic(query):
    """从用户输入检测话题分类"""
    q = (query or "").lower()
    if any(w in q for w in ("科技", "tech", "ai", "人工智能", "芯片")):
        return "科技"
    if any(w in q for w in ("商业", "经济", "财经", "股市", "business")):
        return "商业"
    if any(w in q for w in ("国际", "世界", "world", "全球")):
        return "世界"
    return None


def _format_news(news_list, topic=None):
    """格式化新闻列表为中文，输出简洁的原始数据供 LLM 排版"""
    # 先翻译标题
    en_titles = [item["title"] for item in news_list]
    cn_titles = _translate_titles(en_titles)

    if cn_titles:
        for i, item in enumerate(news_list):
            item["title_cn"] = cn_titles[i]
    else:
        for item in news_list:
            item["title_cn"] = item["title"]

    # 输出简洁的编号列表，不做板块分类（交给 LLM）
    lines = []
    for i, item in enumerate(news_list, 1):
        lines.append(f"{i}. {item['title_cn']} [{item['source']}]")

    return "\n".join(lines)


def execute(query, context=None):
    """抓取新闻主入口 - 多源聚合（Google News + BBC + AP News + NewsAPI）"""
    topic = _detect_topic(query)
    all_news = []
    errors = []

    # 1) Google News RSS
    gn_url = TOPIC_URLS.get(topic, RSS_URL) if topic else RSS_URL
    gn_list, gn_err = _parse_rss(gn_url, limit=4)
    if gn_list:
        all_news.extend(gn_list)
    elif gn_err:
        errors.append(f"Google: {gn_err}")

    # 2) BBC RSS
    bbc_url = BBC_RSS.get(topic, BBC_RSS["top"]) if topic else BBC_RSS["top"]
    bbc_list, bbc_err = _parse_rss(bbc_url, limit=4)
    if bbc_list:
        for item in bbc_list:
            if not item.get("source"):
                item["source"] = "BBC"
        all_news.extend(bbc_list)
    elif bbc_err:
        errors.append(f"BBC: {bbc_err}")

    # 3) AP News RSS
    ap_url = AP_RSS.get(topic, AP_RSS["top"]) if topic else AP_RSS["top"]
    ap_list, ap_err = _parse_rss(ap_url, limit=4)
    if ap_list:
        for item in ap_list:
            if not item.get("source"):
                item["source"] = "AP News"
        all_news.extend(ap_list)
    elif ap_err:
        errors.append(f"AP: {ap_err}")

    # 4) NewsAPI（可选，没配 key 就跳过）
    na_list, na_err = _fetch_newsapi(topic, limit=3)
    if na_list:
        all_news.extend(na_list)

    if not all_news:
        err_detail = "\n".join(errors) if errors else ""
        return f"新闻源都没抓到数据\n{err_detail}".strip()

    # 去重（标题前 20 字符）
    seen = set()
    unique = []
    for item in all_news:
        key = re.sub(r'\s+', '', item["title"][:20]).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return _format_news(unique[:12], topic)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(execute("今天有什么大新闻"))
