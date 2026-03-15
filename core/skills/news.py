# 新闻抓取技能 - Google News RSS
import requests
import json
import os
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

# LLM 配置
_llm_config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'brain', 'llm_config.json')


def _load_llm_config():
    try:
        with open(_llm_config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"api_key": "", "model": "MiniMax-M2.5", "base_url": "https://api.minimax.chat/v1"}


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
            import re
            cleaned = re.sub(r'^\d+[\.\、\)\s]+', '', line).strip()
            if cleaned:
                result.append(cleaned)
        return result if len(result) == len(titles) else None
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
    """格式化新闻列表为中文可读文本，带分板块"""
    # 先翻译标题
    en_titles = [item["title"] for item in news_list]
    cn_titles = _translate_titles(en_titles)

    if cn_titles:
        for i, item in enumerate(news_list):
            item["title_cn"] = cn_titles[i]
    else:
        for item in news_list:
            item["title_cn"] = item["title"]

    # 分板块
    categorized = _classify_news(news_list)

    lines = []
    idx = 1
    for cat_name, items in categorized.items():
        lines.append(f"\n📌 {cat_name}")
        lines.append("")
        for item in items:
            lines.append(f"{idx}. {item['title_cn']}")
            lines.append(f"   [{item['source']}]")
            idx += 1
        lines.append("")

    return "\n".join(lines).strip()


def execute(query, context=None):
    """抓取新闻主入口"""
    topic = _detect_topic(query)
    if topic and topic in TOPIC_URLS:
        url = TOPIC_URLS[topic]
    else:
        url = RSS_URL
        topic = None

    news_list, err = _parse_rss(url, limit=10)
    if err:
        return err
    if not news_list:
        return "没抓到新闻，可能 RSS 源暂时没数据"

    return _format_news(news_list, topic)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(execute("今天有什么大新闻"))
