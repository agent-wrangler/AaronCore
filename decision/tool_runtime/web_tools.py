"""Web-search-oriented runtime helpers for post-LLM tool calls."""

import re as _re
import time


def normalize_time_sensitive_search_query(query: str, *, current_year: int | None = None) -> str:
    text = str(query or "").strip()
    if not text:
        return text
    lowered = text.lower()
    latest_markers = (
        "\u6700\u65b0",
        "\u6700\u8fd1",
        "current",
        "latest",
        "today",
        "this year",
        "\u4eca\u5e74",
    )
    history_markers = (
        "\u5386\u53f2",
        "\u56de\u987e",
        "\u590d\u76d8",
        "\u76d8\u70b9",
        "\u5e74\u5ea6",
        "\u5f80\u5e74",
        "\u53bb\u5e74",
        "previous",
        "past",
    )
    if not any(marker in lowered for marker in latest_markers):
        return text
    if any(marker in lowered for marker in history_markers):
        return text

    current_year = current_year or time.localtime().tm_year
    years = [int(match.group(0)) for match in _re.finditer(r"20\d{2}", text)]
    if years and max(years) < current_year:
        return _re.sub(r"20\d{2}", str(current_year), text, count=1)
    if not years and any(marker in lowered for marker in latest_markers):
        prefix = (
            f"{current_year}\u5e74 "
            if _re.search(r"[\u4e00-\u9fff]", text)
            else f"{current_year} "
        )
        return f"{prefix}{text}"
    return text


def execute_web_search(query: str, *, debug_write, search_web_results) -> dict:
    normalized_query = normalize_time_sensitive_search_query(query)
    debug_write("web_search_execute", {"query": normalized_query})
    try:
        results = search_web_results(normalized_query, max_results=5, timeout_sec=8)
        if not results:
            return {"success": False, "error": "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c"}

        lines = ["\u3010\u8054\u7f51\u641c\u7d22\u7ed3\u679c\u3011"]
        for index, result in enumerate(results, 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            lines.append(f"{index}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if link:
                lines.append(f"   \u6765\u6e90: {link}")

        if results[0].get("tavily_answer"):
            lines.append(f"\nAI\u6458\u8981: {results[0]['tavily_answer']}")

        response = "\n".join(lines)
        debug_write("web_search_result", {"query": normalized_query, "count": len(results)})
        return {"success": True, "response": response}
    except Exception as exc:
        debug_write("web_search_error", {"query": normalized_query, "error": str(exc)})
        return {"success": False, "error": f"\u641c\u7d22\u5931\u8d25: {exc}"}
