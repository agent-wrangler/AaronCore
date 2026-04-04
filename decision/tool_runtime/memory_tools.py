"""Runtime helpers for memory-oriented tool calls."""


MEMORY_TOOL_NAMES = {
    "recall_memory",
    "query_knowledge",
    "web_search",
    "read_file",
    "list_files",
    "sense_environment",
}

SHORT_TERM_LABEL = "[\u77ed\u671f\u8bb0\u5fc6]"
LONG_TERM_LABEL = "[\u957f\u671f\u8bb0\u5fc6]"
NO_MEMORY_TEXT = "\u6682\u65e0\u76f8\u5173\u8bb0\u5fc6\u3002"
EMPTY_SEARCH_TEXT = "\u641c\u7d22\u5173\u952e\u8bcd\u4e0d\u80fd\u4e3a\u7a7a\u3002"
UNKNOWN_TOOL_PREFIX = "\u672a\u77e5\u8bb0\u5fc6\u5de5\u5177: "


def _recall_pair(item) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", ""
    query = str(item.get("query") or item.get("user_text") or "").strip()
    answer = str(item.get("answer") or item.get("ai_text") or item.get("summary") or "").strip()
    return query, answer


def _recall_event_text(event) -> str:
    if isinstance(event, str):
        return event.strip()
    if isinstance(event, dict):
        return str(event.get("text") or event.get("event") or event.get("summary") or "").strip()
    return ""


def format_recall(l2_results, l3_events) -> str:
    lines = []
    if l2_results:
        lines.append(SHORT_TERM_LABEL)
        for item in l2_results[:5]:
            query, answer = _recall_pair(item)
            if query or answer:
                lines.append(f"- Q: {query}\n  A: {answer[:160]}")
    if l3_events:
        lines.append(LONG_TERM_LABEL)
        for event in l3_events[:5]:
            text = _recall_event_text(event)
            if text:
                lines.append(f"- {text[:180]}")
    return "\n".join(lines) if lines else NO_MEMORY_TEXT


def format_knowledge(hits) -> str:
    lines = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        title = str(hit.get("query") or hit.get("name") or "").strip()
        summary = str(hit.get("summary") or "").strip()
        if summary:
            lines.append(f"- {title}: {summary}")
    return "\n".join(lines)


def execute_memory_tool(
    name: str,
    arguments: dict,
    *,
    debug_write,
    l2_search_relevant,
    load_l3_long_term,
    find_relevant_knowledge,
    execute_web_search,
    execute_self_fix,
    execute_read_file,
    execute_list_files_v3,
    execute_discover_tools,
    execute_sense_environment,
) -> dict:
    debug_write("memory_tool_execute", {"name": name, "args": arguments})
    if name == "recall_memory":
        query = str(arguments.get("query", "")).strip()
        l2 = l2_search_relevant(query, limit=5)
        l3 = load_l3_long_term(limit=5)
        response = format_recall(l2, l3)
        debug_write("memory_tool_result", {"name": name, "l2_hits": len(l2), "l3_hits": len(l3)})
        return {"success": True, "response": response}
    if name == "query_knowledge":
        topic = str(arguments.get("topic", "")).strip()
        hits = find_relevant_knowledge(topic, limit=3, touch=True)
        response = format_knowledge(hits)
        debug_write("memory_tool_result", {"name": name, "hits": len(hits)})
        return {"success": True, "response": response}
    if name == "web_search":
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"success": False, "error": EMPTY_SEARCH_TEXT}
        return execute_web_search(query)
    if name == "self_fix":
        return execute_self_fix(arguments)
    if name == "read_file":
        return execute_read_file(arguments)
    if name == "list_files":
        return execute_list_files_v3(arguments)
    if name == "discover_tools":
        return execute_discover_tools(arguments)
    if name == "sense_environment":
        return execute_sense_environment(arguments)
    return {"success": False, "error": f"{UNKNOWN_TOOL_PREFIX}{name}"}
