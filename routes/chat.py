"""核心对话路由：/chat SSE 流式"""
import asyncio
import json
import requests
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import re as _re
from core import shared as S
from routes import companion as _comp


def _strip_markdown(text: str) -> str:
    """剥掉 LLM 回复中的 markdown 格式符号"""
    text = text.replace('**', '')
    text = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
    return text

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    image: str | None = None


def unified_skill_reply(bundle: dict, skill_name: str, skill_input: str) -> dict:
    import agent_final as _af  # lazy import to avoid circular; enables test patching
    route_result = {"mode": "skill", "skill": skill_name, "params": {}, "role": "assistant"}
    skill_context = {}
    l4 = bundle.get("l4") or {}
    if isinstance(l4, dict):
        up = l4.get("user_profile") or {}
        if isinstance(up, dict):
            skill_context["user_city"] = str(up.get("city") or "").strip()
            skill_context["user_identity"] = str(up.get("identity") or "").strip()
    l1 = bundle.get("l1") or []
    if l1:
        skill_context["recent_history"] = [
            {"role": m.get("role", ""), "content": m.get("content", "")[:200]}
            for m in l1 if isinstance(m, dict)
        ]
    execute_result = _af.nova_execute(route_result, skill_input, skill_context) if _af.NOVA_CORE_READY else {"success": False}
    S.debug_write("execute_result", execute_result)
    if not execute_result.get("success"):
        error_text = str(execute_result.get("error", "") or "").strip()
        if "\u672a\u627e\u5230" in error_text or "\u6ca1\u6709\u53ef\u6267\u884c\u51fd\u6570" in error_text:
            S.debug_write("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
            S.trigger_self_repair_from_error("skill_missing", {"skill": skill_name, "input": skill_input, "error": error_text})
        else:
            S.debug_write("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
            if "timeout" not in error_text.lower() and "connection" not in error_text.lower():
                S.trigger_self_repair_from_error("skill_failed", {"skill": skill_name, "input": skill_input, "error": error_text})
        return {
            "reply": S.format_skill_error_reply(skill_name, error_text, bundle.get("user_input", "")),
            "trace": {"skill": skill_name, "success": False, "error": error_text},
        }

    try:
        S.evolve(bundle["user_input"], skill_name)
    except Exception as exc:
        S.debug_write("evolve_error", {"skill": skill_name, "error": str(exc)})

    skill_response = execute_result.get("response", "")
    if skill_name == "story":
        return {"reply": S.format_story_reply(bundle["user_input"], skill_response), "trace": {"skill": skill_name, "success": True}}
    if skill_name == "article":
        return {"reply": skill_response, "trace": {"skill": skill_name, "success": True}}

    if skill_name == "news":
        dialogue_context = bundle.get("dialogue_context", "")
        format_prompt = (
            f"\u4e0b\u9762\u662f\u521a\u4ece Google News \u6293\u5230\u7684\u65b0\u95fb\uff08\u5df2\u7ffb\u8bd1\u6210\u4e2d\u6587\uff09\uff1a\n{skill_response}\n\n"
            "\u8bf7\u628a\u8fd9\u4e9b\u65b0\u95fb\u6574\u7406\u6210\u4e00\u4efd\u7ed3\u6784\u6e05\u6670\u7684\u65b0\u95fb\u7b80\u62a5\uff1a\n"
            "1. \u6309\u8bdd\u9898\u5206\u677f\u5757\uff08\u56fd\u9645\u5c40\u52bf\u3001\u79d1\u6280\u3001\u8d22\u7ecf\u3001\u793e\u4f1a\u7b49\uff09\uff0c\u677f\u5757\u6807\u9898\u7528\u7eaf\u6587\u5b57\uff08\u5982\u300c\u56fd\u9645\u5c40\u52bf\u300d\uff09\uff0c\u7981\u6b62\u7528 # \u6216 ### \u6216 emoji\n"
            "2. \u6bcf\u6761\u65b0\u95fb\u5355\u72ec\u4e00\u884c\uff0c\u4fdd\u7559\u6765\u6e90\uff0c\u4e0d\u8981\u538b\u7f29\u6216\u5408\u5e76\n"
            "3. \u4e0d\u8981\u52a0\u5f00\u573a\u767d\u548c\u7ed3\u5c3e\u70b9\u8bc4\uff0c\u53ea\u8f93\u51fa\u5206\u597d\u677f\u5757\u7684\u65b0\u95fb\u5217\u8868\n"
            "\u76f4\u63a5\u8f93\u51fa\u7ed3\u679c\u3002"
        )
        from brain import LLM_CONFIG
        formatted = ""
        try:
            llm_resp = requests.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
                json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": format_prompt}], "max_tokens": 2000},
                timeout=25,
            )
            if llm_resp.status_code == 200:
                formatted = llm_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass
        if not formatted or len(formatted) < 20:
            formatted = skill_response

        l4 = bundle.get("l4") or {}
        persona_data = l4.get("local_persona") or {}
        style = str(persona_data.get("style_prompt", "")).strip() or "\u6e29\u67d4\u3001\u81ea\u7136\u3001\u6709\u70b9\u4eb2\u8fd1\u611f"
        nova_name = str(persona_data.get("nova_name", "Nova")).strip()
        user_name = str(persona_data.get("user", "\u4e3b\u4eba")).strip()
        polish_prompt = (
            f"\u4f60\u662f {nova_name}\uff0c\u6b63\u5728\u7ed9 {user_name} \u62a5\u65b0\u95fb\u3002\n"
            f"\u4f60\u7684\u98ce\u683c\uff1a{style}\n\n"
            f"\u4e0b\u9762\u662f\u6574\u7406\u597d\u7684\u65b0\u95fb\u5217\u8868\uff1a\n{formatted}\n\n"
            "\u8981\u6c42\uff1a\n"
            "1. \u5728\u65b0\u95fb\u5217\u8868\u524d\u52a0\u4e00\u53e5\u4f60\u98ce\u683c\u7684\u5f00\u573a\u767d\n"
            "2. \u5728\u65b0\u95fb\u5217\u8868\u540e\u52a0\u4e00\u4e24\u53e5\u4f60\u7684\u70b9\u8bc4\n"
            "3. \u65b0\u95fb\u5217\u8868\u672c\u8eab\u539f\u6837\u4fdd\u7559\uff0c\u4e0d\u8981\u6539\u52a8\u3001\u538b\u7f29\u6216\u5408\u5e76\n"
            "4. \u53ea\u8f93\u51fa\u6700\u7ec8\u7ed3\u679c"
        )
        reply = ""
        try:
            polish_resp = requests.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}", "Content-Type": "application/json"},
                json={"model": LLM_CONFIG["model"], "messages": [{"role": "user", "content": polish_prompt}], "temperature": 0.7, "max_tokens": 2500},
                timeout=30,
            )
            if polish_resp.status_code == 200:
                reply = polish_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass
        if not reply or len(reply.strip()) < 20 or "\ufffd" in reply:
            reply = f"\u62ff\u597d\u5566\uff0c\u4eca\u5929\u7684\u65b0\u95fb\u6211\u5e2e\u4f60\u6293\u56de\u6765\u4e86\uff5e\n\n{formatted}"
        return {"reply": reply.strip(), "trace": {"skill": skill_name, "success": True}}

    dialogue_context = bundle.get("dialogue_context", "")
    prompt = f"""
\u7528\u6237\u8f93\u5165\uff1a{bundle['user_input']}

\u6280\u80fd\u7ed3\u679c\uff1a
{skill_response}

L4\u4eba\u683c\u4fe1\u606f\uff1a
{json.dumps(bundle['l4'], ensure_ascii=False)}

\u4f60\u5fc5\u987b\u4e25\u683c\u6309\u7167 L4 \u4eba\u683c\u4fe1\u606f\u4e2d\u7684\u98ce\u683c\u89c4\u5219\u6765\u56de\u590d\uff01

\u4eba\u683c\u98ce\u683c\u8981\u70b9\uff1a
1. \u8bed\u6c14\u8f6f\u8f6f\u7cef\u7cef\uff0c\u7231\u6492\u5a07\uff0c\u591a\u7528\u8bed\u6c14\u8bcd\uff08\u5566\u3001\u561b\u3001\u5440\u3001\u54e6\u3001\u545c\u545c\uff09
2. \u50cf\u670b\u53cb\u804a\u5929\uff0c\u63a5\u5730\u6c14\uff0c\u4e0d\u6253\u5b98\u8154
3. \u7b80\u6d01\u4e0d\u5570\u55e6\uff0c\u4e00\u53e5\u8bdd\u80fd\u8bf4\u5b8c\u4e0d\u62c6\u597d\u51e0\u6bb5
4. \u5076\u5c14\u53ef\u4ee5\u76ae\u4e00\u4e0b\u3001\u8c03\u4f83\u4e00\u4e0b\uff0c\u4e0d\u662f\u5168\u7a0b\u751c\u7f8e
5. \u8981\u628a\u6280\u80fd\u7ed3\u679c\u81ea\u7136\u878d\u8fdb\u804a\u5929\u8bed\u6c14\u91cc\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u64ad\u62a5

\u7981\u6b62\uff1a
- \u4e0d\u8981\u201c\u60a8\u597d\uff0c\u8bf7\u95ee\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u60a8\u201d\u8fd9\u79cd\u5ba2\u670d\u8154
- \u4e0d\u8981\u6ee1\u5c4f emoji
- \u4e0d\u8981\u673a\u68b0\u5957\u6a21\u677f
- \u4e0d\u8981\u628a\u6280\u80fd\u7ed3\u679c\u539f\u6837\u786c\u7529\u7ed9\u7528\u6237

\u8981\u6c42\uff1a
1. \u5fc5\u987b\u4e25\u683c\u57fa\u4e8e\u6280\u80fd\u7ed3\u679c\u56de\u7b54\uff0c\u4e0d\u80fd\u6539\u4e8b\u5b9e\u3002
2. \u6839\u636e L4 \u91cc\u7684\u98ce\u683c\u89c4\u5219\u6765\u786e\u5b9a\u8bed\u6c14\u3002
3. \u5982\u679c\u7528\u6237\u8fd9\u53e5\u8bdd\u662f\u5728\u63a5\u4e0a\u4e00\u8f6e\u7ee7\u7eed\u8ffd\u95ee\uff0c\u8981\u81ea\u7136\u63a5\u7740\u524d\u6587\u8bf4\uff0c\u4e0d\u8981\u50cf\u91cd\u65b0\u5f00\u4e86\u4e00\u4e2a\u8bdd\u9898\u3002
4. \u7528\u7edf\u4e00\u7684\u4eba\u683c\u53e3\u543b\u8f93\u51fa\uff0c\u4e0d\u8981\u50cf\u7cfb\u7edf\u63d0\u793a\u3002
5. \u4e0d\u8981\u8f93\u51fa\u601d\u8003\u8fc7\u7a0b\u3002
6. \u53ea\u8f93\u51fa\u6700\u7ec8\u56de\u590d\u3002
""".strip()
    result = S.think(prompt, dialogue_context)
    reply = result.get("reply", "") if isinstance(result, dict) else str(result)
    if (not reply) or ("\ufffd" in str(reply)) or len(str(reply).strip()) < 2:
        return {"reply": S.format_skill_fallback(skill_response), "trace": {"skill": skill_name, "success": True}}
    return {"reply": str(reply).strip(), "trace": {"skill": skill_name, "success": True}}



@router.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    msg = request.message
    user_image = request.image
    S.debug_write("input", {"message": msg, "has_image": bool(user_image)})
    S.add_to_history("user", msg)

    history = S.load_msg_history()
    history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
    S.save_msg_history(history)

    async def event_stream():
        _comp.activity = "thinking"

        async def _trace(label, detail):
            await asyncio.sleep(0.3)
            return {"event": "trace", "data": json.dumps({"label": label, "detail": detail}, ensure_ascii=False)}

        pending_awareness = S.awareness_pull()
        for evt in pending_awareness:
            yield {"event": "awareness", "data": json.dumps(evt, ensure_ascii=False)}

        # Step 1: 读取记忆
        l1 = S.get_recent_messages(history, 30)
        l2 = S.extract_session_context(history, msg)
        l2_memories = S.l2_search_relevant(msg)
        user_turns = len([m for m in l1 if isinstance(m, dict) and m.get("role") == "user"])
        mem_detail = f"\u56de\u987e\u4e86\u6700\u8fd1 {user_turns} \u8f6e\u5bf9\u8bdd" if user_turns else "\u8fd9\u662f\u7b2c\u4e00\u53e5\u5bf9\u8bdd"
        if l2.get("topics") and l2["topics"] != ["\u95f2\u804a"]:
            _topics_str = "\u3001".join(l2["topics"])
            mem_detail += f"\uff0c\u8bdd\u9898\u6d89\u53ca{_topics_str}"
        if l2_memories:
            mem_detail += f"\uff0c\u5524\u9192 {len(l2_memories)} \u6761\u6301\u4e45\u8bb0\u5fc6"
        yield await _trace("\u8bfb\u53d6\u8bb0\u5fc6", mem_detail)

        # Step 2: 加载人格和知识
        l3 = S.load_l3_long_term()
        l4 = S.load_l4_persona()
        l5 = S.load_l5_knowledge()
        persona_name = ""
        if isinstance(l4, dict):
            lp = l4.get("local_persona") or l4
            persona_name = str(lp.get("nova_name") or lp.get("name") or "")
        skill_count = len(l5.get("skills", {})) if isinstance(l5, dict) else 0
        persona_detail = f"\u4eba\u683c\u8c31\u56fe\u300c{persona_name}\u300d\u5df2\u5524\u9192" if persona_name else "\u4eba\u683c\u8c31\u56fe\u5df2\u5524\u9192"
        yield await _trace("\u52a0\u8f7d\u4eba\u683c", persona_detail)

        # Step 3: 检索知识库
        l8 = S.find_relevant_knowledge(msg, limit=3, touch=True)
        if l8:
            topics = [str(h.get("query") or h.get("name") or "") for h in l8[:2] if isinstance(h, dict)]
            topics = [t for t in topics if t]
            if topics:
                yield await _trace("\u68c0\u7d22\u77e5\u8bc6", "\u5339\u914d\u77e5\u8bc6\u5e93\uff1a" + "\u3001".join(topics))

        try:
            from core.state_loader import record_memory_stats
            record_memory_stats(
                l2_searches=1, l2_hits=1 if l2_memories else 0,
                l8_searches=1, l8_hits=1 if l8 else 0,
                l1_count=len(l1), l3_count=len(l3),
                l4_available=bool(l4 and isinstance(l4, dict) and len(l4) > 0),
                l5_count=skill_count,
            )
        except Exception:
            pass

        # Step 4: 理解意图
        dialogue_context = S.build_dialogue_context(history, msg)
        bundle = {
            "l1": l1, "l2": l2, "l2_memories": l2_memories,
            "l3": l3, "l4": l4, "l5": l5,
            "l7": S.search_relevant_rules(msg, limit=3),
            "l8": l8,
            "dialogue_context": dialogue_context, "user_input": msg,
            "image": user_image,
        }
        S.debug_write("context_bundle", {
            "l1": len(l1), "l2": len(l2), "l2_memories": len(l2_memories),
            "l3": len(l3),
            "l4_keys": list(l4.keys()) if isinstance(l4, dict) else [],
            "l5_skill_count": skill_count, "l8": len(l8 or []),
        })

        response = ""
        route = {"mode": "chat", "skill": "none", "reason": "default"}
        try:
            from brain import _detect_mode_switch
            mode_switch_reply = _detect_mode_switch(msg)
            if mode_switch_reply:
                response = mode_switch_reply
                yield await _trace("\u4eba\u683c\u5207\u6362", "\u5df2\u5207\u6362\u4eba\u683c\u6a21\u5f0f")
                yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
                _comp.activity = "idle"
                S.add_to_history("assistant", response)
                history.append({"role": "assistant", "content": response, "time": datetime.now().isoformat()})
                S.save_msg_history(history)
                return

            route = S.resolve_route(bundle)
            S.debug_write("resolved_route", route)
            mode = route.get("mode", "chat")
            skill = route.get("skill", "none")
            rewritten_input = route.get("rewritten_input") or msg

            reason_text = S.prettify_trace_reason(route)
            if reason_text:
                yield await _trace("\u7406\u89e3\u610f\u56fe", reason_text)

            if mode in ("skill", "hybrid") and skill not in ("none", "", None) and S.NOVA_CORE_READY:
                _comp.activity = "skill"
                skill_display = S.get_skill_display_name(skill)
                yield await _trace("\u8c03\u7528\u6280\u80fd", f"\u6b63\u5728\u8c03\u7528\u300c{skill_display}\u300d\u6280\u80fd\u2026")
                skill_result = unified_skill_reply(bundle, skill, rewritten_input)
                if isinstance(skill_result, dict):
                    response = str(skill_result.get("reply", "") or "")
                else:
                    response = str(skill_result or "")
            else:
                _comp.activity = "replying"
                if S.is_explicit_learning_request(msg):
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u6b63\u5728\u5206\u6790\u641c\u7d22\u4e3b\u9898\u2026")
                    _extract_prompt = (
                        "\u7528\u6237\u8bf4\u4e86\u4e0b\u9762\u8fd9\u53e5\u8bdd\uff0c\u8bf7\u4ece\u4e2d\u63d0\u53d6\u51fa\u4ed6\u771f\u6b63\u60f3\u641c\u7d22/\u5b66\u4e60\u7684\u4e3b\u9898\u5173\u952e\u8bcd\u3002"
                        "\u5982\u679c\u7528\u6237\u6ca1\u6709\u6307\u5b9a\u5177\u4f53\u4e3b\u9898\uff08\u6bd4\u5982\u53ea\u8bf4\u201c\u53bb\u5b66\u70b9\u4e1c\u897f\u201d\uff09\uff0c"
                        "\u5c31\u6839\u636e\u4e4b\u524d\u7684\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff0c\u9009\u4e00\u4e2a\u7528\u6237\u53ef\u80fd\u611f\u5174\u8da3\u7684\u4e3b\u9898\u3002"
                        "\u53ea\u8f93\u51fa\u641c\u7d22\u5173\u952e\u8bcd\uff0c\u4e0d\u8981\u89e3\u91ca\uff0c\u4e0d\u8981\u52a0\u5f15\u53f7\uff0c\u4e0d\u8d85\u8fc715\u4e2a\u5b57\u3002\n\n"
                        f"\u7528\u6237\u539f\u8bdd\uff1a{msg}\n"
                        f"\u6700\u8fd1\u5bf9\u8bdd\u4e0a\u4e0b\u6587\uff1a{bundle.get('dialogue_context', '')[:300]}"
                    )
                    _raw_topic = S.raw_llm_call(_extract_prompt)
                    search_topic = str(_raw_topic or "").strip()[:15]
                    search_topic = search_topic.strip('"\'\u201c\u201d\u300c\u300d\u3010\u3011')
                    if len(search_topic) < 2 or len(search_topic) > 40:
                        search_topic = msg
                    if search_topic == msg:
                        import re as _re
                        _stop = ["\u5e2e\u6211","\u7ed9\u6211","\u80fd\u4e0d\u80fd","\u53ef\u4ee5","\u597d\u770b\u7684","\u6700\u65b0\u7684","\u4e00\u4e0b","\u51e0\u672c","\u4e00\u4e9b","\u4f60","\u5417","\u5440","\u5462","\u4e86","\u7684","\u70b9"]
                        _cleaned = msg
                        for sw in _stop:
                            _cleaned = _cleaned.replace(sw, "")
                        _cleaned = _re.sub(r'\s+', ' ', _cleaned).strip()
                        if len(_cleaned) >= 2:
                            search_topic = _cleaned
                    S.debug_write("extract_search_topic", {"input": msg, "topic": search_topic})
                    yield await _trace("\u8054\u7f51\u641c\u7d22", "\u641c\u7d22\u4e3b\u9898\uff1a" + search_topic)
                    search_result = S.explicit_search_and_learn(search_topic)
                    S.debug_write("explicit_search", {
                        "topic": search_topic, "success": search_result.get("success"),
                        "reason": search_result.get("reason", ""), "result_count": search_result.get("result_count", 0),
                    })
                    if search_result.get("success"):
                        search_context = "\u3010\u5b9e\u65f6\u641c\u7d22\u7ed3\u679c\u3011\n"
                        for i, r in enumerate(search_result.get("results", [])[:5], 1):
                            search_context += f"{i}. {r.get('title', '')}\n   {r.get('snippet', '')}\n"
                        bundle["search_context"] = search_context
                        bundle["search_summary"] = search_result.get("summary", "")
                        yield await _trace("\u6574\u7406\u7ed3\u679c", "\u641c\u5230 " + str(search_result.get("result_count", 0)) + " \u6761\u7ed3\u679c\uff0c\u6b63\u5728\u6574\u7406\u2026")
                    else:
                        S.debug_write("explicit_search_failed", {"reason": search_result.get("reason", "")})
                        yield await _trace("\u7ec4\u7ec7\u56de\u590d", "\u641c\u7d22\u672a\u627e\u5230\u7ed3\u679c\uff0c\u7ed3\u5408\u5df2\u6709\u77e5\u8bc6\u56de\u590d\u2026")
                else:
                    yield await _trace("\u7ec4\u7ec7\u56de\u590d", f"\u300c{persona_name or 'Nova'}\u300d\u6b63\u5728\u8ba4\u771f\u601d\u8003\u5e76\u56de\u590d\u4f60\u2026")
                response = S.unified_chat_reply(bundle, route)
        except Exception as exc:
            S.debug_write("chat_exception", {"error": str(exc)})
            S.trigger_self_repair_from_error("chat_exception", {"message": msg, "error": str(exc)}, background_tasks)
            response = "\u62b1\u6b49\uff0c\u51fa\u9519\u4e86"

        # 最终回复（剥掉 markdown 格式符号）
        response = _strip_markdown(response)
        await asyncio.sleep(0.05)
        yield {"event": "reply", "data": json.dumps({"reply": response}, ensure_ascii=False)}
        _comp.activity = "idle"

        _comp.reply_id = datetime.now().isoformat()
        summary = str(response or "").replace("\n", " ").strip()
        _comp.last_reply = summary[:60] + ("..." if len(summary) > 60 else "")
        _comp.last_reply_full = summary

        # 后台任务
        feedback_rule = S.l7_record_feedback_v2(msg, history, background_tasks)
        if feedback_rule:
            awareness_evt = {
                "type": "l7_feedback",
                "summary": "\u8bb0\u5f55\u53cd\u9988\u89c4\u5219: " + feedback_rule.get("category", "\u672a\u5206\u7c7b"),
                "detail": {
                    "id": feedback_rule.get("id"),
                    "scene": feedback_rule.get("scene", ""),
                    "problem": feedback_rule.get("problem", ""),
                    "category": feedback_rule.get("category", ""),
                    "fix": feedback_rule.get("fix", ""),
                },
            }
            S.awareness_push(awareness_evt)
            yield {"event": "awareness", "data": json.dumps(awareness_evt, ensure_ascii=False)}
        S.l8_touch()
        l8_config = S.load_autolearn_config()
        if (
            l8_config.get("enabled", True)
            and l8_config.get("allow_web_search", True)
            and l8_config.get("allow_knowledge_write", True)
            and not feedback_rule
            and not (l8 or [])
            and route.get("intent") != "missing_skill"
        ):
            background_tasks.add_task(S.run_l8_autolearn_task, msg, response, route, bool(l8))

        import agent_final as _af
        repair_payload = _af.build_repair_progress_payload(route, feedback_rule)
        if repair_payload.get("show"):
            yield {"event": "repair", "data": json.dumps(repair_payload, ensure_ascii=False)}

        S.debug_write("final_response", {"reply": response, "repair": repair_payload})
        S.add_to_history("nova", response)
        history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
        S.save_msg_history(history)

        try:
            S.l2_add_memory(msg, response)
        except Exception as exc:
            S.debug_write("l2_add_error", {"error": str(exc)})

    return EventSourceResponse(event_stream())
