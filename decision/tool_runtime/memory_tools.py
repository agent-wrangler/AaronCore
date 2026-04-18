"""Runtime helpers for memory-oriented tool calls."""

import re


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
_TIMELINE_MARKERS = (
    "\u591a\u4e45",
    "\u591a\u957f\u65f6\u95f4",
    "\u4ec0\u4e48\u65f6\u5019",
    "\u4f55\u65f6",
    "\u5f00\u59cb",
    "\u8d77\u6b65",
    "\u6fc0\u6d3b",
    "\u8bde\u751f",
    "\u521b\u5efa",
    "\u5f00\u53d1\u65f6\u957f",
    "\u9879\u76ee\u5f00\u59cb\u65f6\u95f4",
)
_TIMELINE_ENTRY_MARKERS = (
    "\u6700\u8fd1",
    "\u5f00\u59cb",
    "\u8d77\u6b65",
    "\u6fc0\u6d3b",
    "\u542f\u52a8",
    "\u8bde\u751f",
    "\u521b\u5efa",
    "\u4e0a\u65ec",
    "\u4e0b\u65ec",
    "\u524d\u540e",
    "\u65f6\u95f4",
    "\u65f6\u957f",
)


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


def _looks_like_timeline_query(query: str) -> bool:
    text = str(query or "").strip()
    if not text:
        return False
    if any(marker in text for marker in _TIMELINE_MARKERS):
        return True
    return bool(re.search(r"(20\d{2}|[01]?\d月[0-3]?\d[号日]?|今天|昨天|前天|上周|这周)", text))


def _entry_has_timeline_signal(text: str) -> bool:
    content = str(text or "").strip()
    if not content:
        return False
    if any(marker in content for marker in _TIMELINE_ENTRY_MARKERS):
        return True
    return bool(re.search(r"(20\d{2}|[01]?\d月[0-3]?\d[号日]?|8090)", content))


def _filter_timeline_l2_results(l2_results) -> list:
    kept = []
    for item in l2_results or []:
        query, answer = _recall_pair(item)
        if _entry_has_timeline_signal(f"{query} {answer}"):
            kept.append(item)
    return kept


def _context_fs_target_path(context: dict | None) -> str:
    payload = context if isinstance(context, dict) else {}
    target = payload.get("fs_target") if isinstance(payload.get("fs_target"), dict) else {}
    path = str(target.get("path") or "").strip()
    if path:
        return path
    context_data = payload.get("context_data") if isinstance(payload.get("context_data"), dict) else {}
    target = context_data.get("fs_target") if isinstance(context_data.get("fs_target"), dict) else {}
    return str(target.get("path") or "").strip()


def _project_scope_from_context(context: dict | None) -> str:
    payload = context if isinstance(context, dict) else {}
    parts: list[str] = []

    working_state = payload.get("working_state") if isinstance(payload.get("working_state"), dict) else {}
    for key in ("goal", "summary", "recent_progress"):
        value = str(working_state.get(key) or "").strip()
        if value:
            parts.append(value)

    task_plan = payload.get("task_plan") if isinstance(payload.get("task_plan"), dict) else {}
    for key in ("goal", "summary"):
        value = str(task_plan.get(key) or "").strip()
        if value:
            parts.append(value)

    project_id = str(task_plan.get("project_id") or working_state.get("project_id") or "").strip()
    if project_id:
        try:
            from tasks.store import get_project

            project = get_project(project_id)
        except Exception:
            project = None
        if isinstance(project, dict):
            title = str(project.get("title") or "").strip()
            if title:
                parts.append(title)
            project_goal = project.get("goal") if isinstance(project.get("goal"), dict) else {}
            summary = str(project_goal.get("summary") or "").strip()
            if summary:
                parts.append(summary)
            kind = str(project.get("kind") or "").strip()
            if kind:
                parts.append(kind)

    fs_path = _context_fs_target_path(payload)
    if fs_path:
        parts.append(fs_path)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in parts:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return " | ".join(deduped[:6])


def _augment_recall_query(query: str, context: dict | None) -> str:
    base = str(query or "").strip()
    scope = _project_scope_from_context(context)
    if not scope:
        return base
    if not base:
        return scope
    return f"{base}\nCurrent project scope: {scope}"


def format_recall(l2_results, l3_events, *, long_term_first: bool = False) -> str:
    sections = []
    if l2_results:
        lines = [SHORT_TERM_LABEL]
        for item in l2_results[:5]:
            query, answer = _recall_pair(item)
            if query or answer:
                lines.append(f"- Q: {query}\n  A: {answer[:160]}")
        sections.append(lines)
    if l3_events:
        lines = [LONG_TERM_LABEL]
        for event in l3_events[:5]:
            text = _recall_event_text(event)
            if text:
                lines.append(f"- {text[:180]}")
        sections.append(lines)
    if not sections:
        return NO_MEMORY_TEXT
    if long_term_first and len(sections) == 2:
        sections = [sections[1], sections[0]]
    return "\n".join("\n".join(section) for section in sections)


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


def _build_memory_stats_meta(**stats) -> dict:
    return {
        "memory_stats": {
            key: max(int(value), 0)
            for key, value in stats.items()
        }
    }


def execute_memory_tool(
    name: str,
    arguments: dict,
    context: dict | None = None,
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
        effective_query = _augment_recall_query(query, context)
        timeline_query = _looks_like_timeline_query(query)
        l2 = l2_search_relevant(effective_query, limit=5)
        if timeline_query:
            l2 = _filter_timeline_l2_results(l2)
        l3 = load_l3_long_term(limit=5, query=effective_query)
        if timeline_query and l3:
            l2 = []
        response = format_recall(l2, l3, long_term_first=timeline_query)
        debug_write(
            "memory_tool_result",
            {"name": name, "l2_hits": len(l2), "l3_hits": len(l3), "scoped": effective_query != query},
        )
        return {
            "success": True,
            "response": response,
            "meta": _build_memory_stats_meta(
                l2_searches=1,
                l2_hits=1 if l2 else 0,
                l3_queries=1,
                l3_hits=1 if l3 else 0,
            ),
        }
    if name == "query_knowledge":
        topic = str(arguments.get("topic", "")).strip()
        hits = find_relevant_knowledge(topic, limit=3, touch=True)
        response = format_knowledge(hits)
        debug_write("memory_tool_result", {"name": name, "hits": len(hits)})
        return {
            "success": True,
            "response": response,
            "meta": _build_memory_stats_meta(
                l8_searches=1,
                l8_hits=1 if hits else 0,
            ),
        }
    if name == "web_search":
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"success": False, "error": EMPTY_SEARCH_TEXT}
        return execute_web_search(query)
    if name == "self_fix":
        return execute_self_fix(arguments)
    if name == "read_file":
        return execute_read_file(arguments, context=context)
    if name == "list_files":
        return execute_list_files_v3(arguments, context=context)
    if name == "discover_tools":
        return execute_discover_tools(arguments)
    if name == "sense_environment":
        return execute_sense_environment(arguments)
    return {"success": False, "error": f"{UNKNOWN_TOOL_PREFIX}{name}"}
