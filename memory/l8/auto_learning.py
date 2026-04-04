"""Auto-learning orchestration helpers for L8."""

from __future__ import annotations

from collections.abc import Callable


def is_explicit_learning_request(text: str, *, llm_call) -> bool:
    raw = str(text or "").strip()
    if len(raw) < 2 or not llm_call:
        return False
    prompt = (
        "Decide whether the user is explicitly asking the system to go search, "
        "look up references, or learn new information right now.\n"
        f"User message: {raw}\n"
        "Reply YES only when the user clearly asks the system to search or learn.\n"
        "Reply NO for normal questions, chat, complaints, reactions, or discussion.\n"
        "Return YES or NO only."
    )
    try:
        result = str(llm_call(prompt, max_tokens=5) or "").strip().upper()
    except Exception:
        return False
    return result == "YES"


def explicit_search_and_learn(
    search_query: str,
    *,
    load_autolearn_config: Callable[[], dict],
    search_web_results_fn: Callable[..., list[dict]],
    build_summary_fn: Callable[[str, list[dict], int], str],
    save_learned_knowledge_fn: Callable[..., dict],
) -> dict:
    config = load_autolearn_config()
    if not config.get("allow_web_search", True):
        return {"success": False, "reason": "web_search_disabled"}

    query = str(search_query or "").strip()
    if len(query) < 2:
        return {"success": False, "reason": "empty_query"}

    try:
        results = search_web_results_fn(
            query,
            max_results=int(config.get("max_results", 5) or 5),
            timeout_sec=int(config.get("search_timeout_sec", 5) or 5),
            skip_filter=True,
        )
    except Exception as exc:
        return {"success": False, "reason": "search_error: " + str(exc)}

    if not results:
        return {"success": False, "reason": "no_results"}

    summary = build_summary_fn(
        query,
        results,
        int(config.get("max_summary_length", 360) or 360),
    )
    if not summary:
        return {"success": False, "reason": "empty_summary"}

    entry = None
    if config.get("allow_knowledge_write", True):
        entry = save_learned_knowledge_fn(query, summary, results)

    return {
        "success": True,
        "query": query,
        "results": results,
        "summary": summary,
        "entry": entry,
        "result_count": len(results),
    }


def should_trigger_auto_learn(
    user_input: str,
    *,
    route_result: dict | None = None,
    has_relevant_knowledge: bool = False,
    config: dict | None = None,
    load_autolearn_config: Callable[[], dict],
) -> tuple[bool, str]:
    cfg = config or load_autolearn_config()
    text = str(user_input or "").strip()

    if not cfg.get("enabled", True):
        return False, "disabled"
    if not cfg.get("allow_web_search", True) or not cfg.get("allow_knowledge_write", True):
        return False, "permission_blocked"
    if has_relevant_knowledge:
        return False, "already_known"
    if len(text) < int(cfg.get("min_query_length", 4) or 4):
        return False, "too_short"

    if (
        route_result
        and route_result.get("mode") in ("skill", "hybrid")
        and route_result.get("skill") not in ("none", "", None)
    ):
        return False, "handled_by_skill"

    return True, "eligible"


def extract_search_query(
    user_input: str,
    *,
    llm_call,
    looks_like_compact_search_query: Callable[[str], bool],
) -> str | None:
    if not llm_call:
        return None
    prompt = (
        f"User message: {user_input}\n"
        "If this is a knowledge question that should trigger learning, extract a short "
        "search topic (about 2-8 words).\n"
        "If this is not a knowledge question, reply NO.\n"
        "Return only the search topic or NO."
    )
    try:
        result = str(llm_call(prompt, max_tokens=20) or "").strip()
    except Exception:
        return None
    if not result or result.upper() == "NO":
        return None
    if not looks_like_compact_search_query(result):
        return None
    return result


def results_match_learning_query(
    user_input: str,
    search_query: str,
    results: list[dict],
    *,
    llm_call,
    format_search_results_fn: Callable[[list[dict]], str],
    clean_text: Callable[[str, int | None], str],
) -> bool:
    if not results:
        return False
    if not llm_call:
        return True
    material = format_search_results_fn(results[:3])
    if not material:
        return True
    prompt = (
        "Decide whether these search results are genuinely relevant to the learning query.\n"
        f"Original user message: {clean_text(user_input, 120)}\n"
        f"Learning query: {clean_text(search_query, 48)}\n"
        f"Search results:\n{material[:1200]}\n\n"
        "Reply YES if the results are mostly relevant.\n"
        "Reply NO if they are mostly off-topic or only share surface words.\n"
        "Return YES or NO only."
    )
    try:
        result = str(llm_call(prompt, max_tokens=5) or "").strip().upper()
    except Exception:
        return True
    return result == "YES"


def auto_learn(
    user_input: str,
    *,
    route_result: dict | None = None,
    load_autolearn_config: Callable[[], dict],
    find_relevant_knowledge_fn: Callable[..., list[dict]],
    should_trigger_auto_learn_fn: Callable[..., tuple[bool, str]],
    extract_search_query_fn: Callable[[str], str | None],
    search_web_results_fn: Callable[..., list[dict]],
    results_match_learning_query_fn: Callable[[str, str, list[dict]], bool],
    build_summary_fn: Callable[[str, list[dict], int], str],
    save_learned_knowledge_fn: Callable[..., dict],
    debug_write: Callable[[str, dict], None],
) -> dict:
    config = load_autolearn_config()
    related = find_relevant_knowledge_fn(user_input, limit=1, min_score=6)
    should_run, reason = should_trigger_auto_learn_fn(
        user_input,
        route_result=route_result,
        has_relevant_knowledge=bool(related),
        config=config,
    )
    if not should_run:
        return {"success": False, "reason": reason}

    search_query = extract_search_query_fn(user_input)
    if not search_query:
        debug_write("l8_skip_not_knowledge", {"input": user_input[:50]})
        return {"success": False, "reason": "not_knowledge_query"}

    try:
        results = search_web_results_fn(
            search_query,
            max_results=int(config.get("max_results", 5) or 5),
            timeout_sec=int(config.get("search_timeout_sec", 5) or 5),
        )
    except Exception as exc:
        return {"success": False, "reason": f"search_error:{exc}"}

    if not results:
        return {"success": False, "reason": "no_results"}

    if not results_match_learning_query_fn(user_input, search_query, results):
        debug_write(
            "l8_skip_irrelevant",
            {"query": user_input[:40], "search_query": search_query[:40]},
        )
        return {"success": False, "reason": "search_results_irrelevant"}

    summary = build_summary_fn(
        user_input,
        results,
        int(config.get("max_summary_length", 360) or 360),
    )
    if not summary:
        return {"success": False, "reason": "empty_summary"}

    entry = save_learned_knowledge_fn(user_input, summary, results, route_result=route_result)
    return {
        "success": True,
        "type": "knowledge",
        "entry": entry,
        "summary": summary,
        "result_count": len(results),
    }
