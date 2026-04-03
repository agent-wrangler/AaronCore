import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from core.network_protocol import get_with_network_strategy


RSS_URL = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

TOPIC_URLS = {
    "科技": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "商业": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
    "世界": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
}

BBC_RSS = {
    "top": "http://feeds.bbci.co.uk/news/rss.xml",
    "科技": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "商业": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "世界": "http://feeds.bbci.co.uk/news/world/rss.xml",
}

AP_RSS = {
    "top": "https://rsshub.app/apnews/topics/apf-topnews",
    "科技": "https://rsshub.app/apnews/topics/apf-technology",
    "商业": "https://rsshub.app/apnews/topics/apf-business",
    "世界": "https://rsshub.app/apnews/topics/apf-WorldNews",
}

NEWSAPI_BASE = "https://newsapi.org/v2/top-headlines"
NEWSAPI_TOPICS = {"科技": "technology", "商业": "business", "世界": "general"}

_LLM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "brain", "llm_config.json")
_NEWS_CONFIG_PATH = str(Path(__file__).resolve().parents[2] / "app_data" / "config" / "news_config.json")


def _load_llm_config():
    try:
        with open(_LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if "models" in raw:
            default = raw.get("default", "")
            models = raw["models"]
            return models.get(default) or next(iter(models.values()))
        return raw
    except Exception:
        return {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


def _load_news_config():
    try:
        with open(_NEWS_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _format_fetch_error(url: str, exc: Exception) -> str:
    host = re.sub(r"^https?://", "", str(url or "")).split("/", 1)[0] or "目标站点"
    text = str(exc or "").strip()
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return f"当前环境访问 `{host}` 超时"
    if "proxy" in lowered or "127.0.0.1" in lowered or "localhost" in lowered:
        return f"当前环境里的代理不可用，暂时访问不了 `{host}`"
    if text:
        return f"当前环境暂时访问不了 `{host}`: {text[:60]}"
    return f"当前环境暂时访问不了 `{host}`"


def _translate_titles(titles):
    cfg = _load_llm_config()
    if not cfg.get("api_key"):
        return None

    numbered = "\n".join(f"{i + 1}. {title}" for i, title in enumerate(titles))
    prompt = (
        "把下面的英文新闻标题逐条翻译成中文，保持序号，每行一条，只输出翻译结果：\n\n"
        f"{numbered}"
    )

    try:
        from brain import llm_call

        result = llm_call(cfg, [{"role": "user", "content": prompt}], max_tokens=1500, timeout=20)
        text = result.get("content", "")
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        translated = []
        for line in lines:
            cleaned = re.sub(r"^\d+[\.\、\)\s]+", "", line).strip()
            if cleaned:
                translated.append(cleaned)
        if len(translated) >= len(titles):
            return translated[:len(titles)]
        if len(translated) >= len(titles) * 0.6:
            return translated + [titles[i] for i in range(len(translated), len(titles))]
        return None
    except Exception:
        return None


def _parse_rss(url, limit=10):
    try:
        resp = get_with_network_strategy(url, timeout=15)
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
                title = title[: title.rfind(" - ")].strip()
            news_list.append({
                "title": title,
                "source": source,
                "link": link,
                "pubDate": pub,
            })
        return news_list, None
    except Exception as exc:
        return None, _format_fetch_error(url, exc)


def _fetch_newsapi(topic=None, limit=5):
    cfg = _load_news_config()
    api_key = cfg.get("newsapi_key", "")
    if not api_key:
        return [], None

    params = {"apiKey": api_key, "language": "en", "pageSize": limit, "country": "us"}
    if topic and topic in NEWSAPI_TOPICS:
        params["category"] = NEWSAPI_TOPICS[topic]

    try:
        resp = get_with_network_strategy(NEWSAPI_BASE, params=params, timeout=15)
        if resp.status_code != 200:
            return [], f"NewsAPI {resp.status_code}"
        articles = resp.json().get("articles", [])
        news_list = []
        for article in articles[:limit]:
            title = article.get("title", "")
            source = (article.get("source") or {}).get("name", "NewsAPI")
            link = article.get("url", "")
            pub = article.get("publishedAt", "")
            if " - " in title and source and title.endswith(source):
                title = title[: title.rfind(" - ")].strip()
            news_list.append({
                "title": title,
                "source": source,
                "link": link,
                "pubDate": pub,
            })
        return news_list, None
    except Exception as exc:
        return [], _format_fetch_error(NEWSAPI_BASE, exc)


def _normalize_topic(topic):
    text = str(topic or "").strip()
    if not text:
        return None
    if text in TOPIC_URLS:
        return text
    lowered = text.lower()
    if lowered in {"technology", "tech"}:
        return "科技"
    if lowered in {"business"}:
        return "商业"
    if lowered in {"world", "international"}:
        return "世界"
    return None


def _format_news(news_list, topic=None):
    en_titles = [item["title"] for item in news_list]
    cn_titles = _translate_titles(en_titles)

    if cn_titles:
        for i, item in enumerate(news_list):
            item["title_cn"] = cn_titles[i]
    else:
        for item in news_list:
            item["title_cn"] = item["title"]

    lines = []
    for i, item in enumerate(news_list, 1):
        lines.append(f"{i}. {item['title_cn']} [{item['source']}]")
    return "\n".join(lines)


def execute(query, context=None):
    context = context if isinstance(context, dict) else {}
    topic = _normalize_topic(context.get("topic"))
    all_news = []
    errors = []

    gn_url = TOPIC_URLS.get(topic, RSS_URL) if topic else RSS_URL
    gn_list, gn_err = _parse_rss(gn_url, limit=4)
    if gn_list:
        all_news.extend(gn_list)
    elif gn_err:
        errors.append(f"Google: {gn_err}")

    bbc_url = BBC_RSS.get(topic, BBC_RSS["top"]) if topic else BBC_RSS["top"]
    bbc_list, bbc_err = _parse_rss(bbc_url, limit=4)
    if bbc_list:
        for item in bbc_list:
            if not item.get("source"):
                item["source"] = "BBC"
        all_news.extend(bbc_list)
    elif bbc_err:
        errors.append(f"BBC: {bbc_err}")

    ap_url = AP_RSS.get(topic, AP_RSS["top"]) if topic else AP_RSS["top"]
    ap_list, ap_err = _parse_rss(ap_url, limit=4)
    if ap_list:
        for item in ap_list:
            if not item.get("source"):
                item["source"] = "AP News"
        all_news.extend(ap_list)
    elif ap_err:
        errors.append(f"AP: {ap_err}")

    na_list, na_err = _fetch_newsapi(topic, limit=3)
    if na_list:
        all_news.extend(na_list)
    elif na_err:
        errors.append(f"NewsAPI: {na_err}")

    if not all_news:
        err_detail = "\n".join(errors) if errors else ""
        return f"新闻源都没抓到数据\n{err_detail}".strip()

    seen = set()
    unique = []
    for item in all_news:
        key = re.sub(r"\s+", "", item["title"][:20]).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return _format_news(unique[:12], topic)


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print(execute("今天有什么大新闻"))
