"""Web-search and summary helpers for L8 learning."""

from __future__ import annotations

from collections.abc import Callable

from core.network_protocol import get_with_network_strategy, post_with_network_strategy


def format_search_results(results: list[dict], *, clean_text: Callable[[str, int | None], str]) -> str:
    lines = []
    for item in results:
        title = clean_text(item.get("title"), 80)
        snippet = clean_text(item.get("snippet"), 120)
        if title:
            lines.append(f"- {title}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines[:10])


def search_tavily(
    query: str,
    api_key: str,
    *,
    max_results: int = 5,
    timeout_sec: int = 8,
    clean_text: Callable[[str, int | None], str],
) -> list[dict]:
    try:
        resp = post_with_network_strategy(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
            },
            timeout=max(timeout_sec, 5),
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("results", []):
            title = clean_text(str(item.get("title", "")), 90)
            content = clean_text(str(item.get("content", "")), 300)
            url = str(item.get("url", "")).strip()
            if title and content:
                results.append({
                    "title": title,
                    "snippet": content,
                    "link": url,
                })

        answer = str(data.get("answer", "")).strip()
        if answer and results:
            results[0]["tavily_answer"] = clean_text(answer, 200)

        return results[:max_results]
    except Exception as e:
        print(f"[L8] Tavily error: {e}")
        return []


def search_brave(
    query: str,
    api_key: str,
    *,
    max_results: int = 5,
    timeout_sec: int = 8,
    clean_text: Callable[[str, int | None], str],
) -> list[dict]:
    try:
        resp = get_with_network_strategy(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            timeout=max(timeout_sec, 5),
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            title = clean_text(str(item.get("title", "")), 90)
            snippet = clean_text(str(item.get("description", "")), 300)
            url = str(item.get("url", "")).strip()
            if title and snippet:
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "link": url,
                })

        return results[:max_results]
    except Exception as e:
        print(f"[L8] Brave error: {e}")
        return []


def search_web_results(
    query: str,
    *,
    load_autolearn_config: Callable[[], dict],
    max_results: int = 5,
    timeout_sec: int = 8,
    skip_filter: bool = False,
    search_tavily_fn: Callable[..., list[dict]] | None = None,
    search_brave_fn: Callable[..., list[dict]] | None = None,
) -> list[dict]:
    del skip_filter
    config = load_autolearn_config()
    tavily_key = str(config.get("tavily_api_key", "")).strip()
    brave_key = str(config.get("brave_api_key", "")).strip()
    use_tavily = search_tavily_fn or search_tavily
    use_brave = search_brave_fn or search_brave

    if tavily_key:
        results = use_tavily(query, tavily_key, max_results=max_results, timeout_sec=timeout_sec)
        if results:
            return results
        print("[L8] Tavily failed, trying Brave...")

    if brave_key:
        results = use_brave(query, brave_key, max_results=max_results, timeout_sec=timeout_sec)
        if results:
            return results
        print("[L8] Brave also failed")

    if not tavily_key and not brave_key:
        print("[L8] No search API configured. Set tavily_api_key or brave_api_key in autolearn_config.json")

    return []


def search_web(
    query: str,
    *,
    load_autolearn_config: Callable[[], dict],
    search_web_results_fn: Callable[..., list[dict]],
    format_search_results_fn: Callable[[list[dict]], str],
):
    try:
        config = load_autolearn_config()
        results = search_web_results_fn(
            query,
            max_results=int(config.get("max_results", 5)),
            timeout_sec=int(config.get("search_timeout_sec", 8)),
        )
        if not results:
            return None
        return format_search_results_fn(results)
    except Exception:
        return None


def build_summary(
    query: str,
    results: list[dict],
    *,
    max_length: int = 360,
    llm_call=None,
    clean_text: Callable[[str, int | None], str],
    debug_write: Callable[[str, dict], None] = lambda stage, data: None,
) -> str:
    if not results:
        return ""

    snippets = []
    for item in results[:3]:
        title = clean_text(item.get("title"), 48)
        snippet = clean_text(item.get("snippet"), 88)
        if title and snippet:
            snippets.append(f"{title}：{snippet}")
        elif title:
            snippets.append(title)
    raw_material = "\n".join(snippets)

    if llm_call and raw_material:
        try:
            prompt = (
                f"你是知识凝结器。用户问了：「{query}」\n"
                f"以下是搜索结果：\n{raw_material}\n\n"
                "请用简洁的中文总结核心答案，要求：\n"
                "1. 只保留最有价值的信息，去掉广告、无关内容、非中文内容\n"
                "2. 控制在 2-3 句话内\n"
                "3. 直接输出摘要，不要加前缀"
            )
            condensed = llm_call(prompt)
            if condensed and len(condensed) > 10:
                debug_write("l8_condense_ok", {"query": query[:30], "len": len(condensed)})
                return clean_text(condensed, max_length)
        except Exception as e:
            debug_write("l8_condense_err", {"err": str(e)})

    summary = "；".join(snippets)
    return clean_text(summary, max_length)
