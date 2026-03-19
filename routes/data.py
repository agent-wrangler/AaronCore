"""数据查询路由：memory, docs, skills, history, stats, nova_name"""
import json
from datetime import datetime
from fastapi import APIRouter
from core import shared as S

router = APIRouter()


@router.get("/memory")
async def get_memory():
    S.ensure_long_term_clean()
    events = []
    counts = {"L1": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0, "L8": 0}

    l1_file = S.PRIMARY_HISTORY_FILE
    if l1_file.exists():
        try:
            l1_data = json.loads(l1_file.read_text(encoding="utf-8"))
            for item in l1_data:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                counts["L1"] += 1
        except Exception:
            pass

    l3_file = S.PRIMARY_STATE_DIR / "long_term.json"
    if l3_file.exists():
        try:
            l3_data = json.loads(l3_file.read_text(encoding="utf-8"))
            for item in l3_data:
                if S.is_legacy_l3_skill_log(item):
                    continue
                content = S.event_text(item)
                if not content:
                    continue
                events.append({
                    "time": S.normalize_event_time(item.get("timestamp") or item.get("time") or item.get("created_at")),
                    "layer": "L3",
                    "event_type": item.get("category", "memory"),
                    "title": "\u8bb0\u5fc6\u7ed3\u6676",
                    "content": f"\u6c89\u6dc0\u4e86\u4e00\u6bb5\u957f\u671f\u8bb0\u5fc6\uff1a{content}",
                })
                counts["L3"] += 1
        except Exception:
            pass

    l4_file = S.PRIMARY_STATE_DIR / "persona.json"
    if l4_file.exists():
        try:
            l4_data = json.loads(l4_file.read_text(encoding="utf-8"))
            l4_init_time = S.normalize_event_time(l4_data.get("created_at") or "2026-03-10 00:00")
            for item in S.build_persona_events(l4_data, l4_init_time):
                events.append(item)
                counts["L4"] += 1
        except Exception:
            pass

    l5_file = S.PRIMARY_STATE_DIR / "knowledge.json"
    if l5_file.exists():
        try:
            l5_skills = json.loads(l5_file.read_text(encoding="utf-8"))
            for item in l5_skills:
                skill_name = item.get("name") or item.get("\u6838\u5fc3\u6280\u80fd") or "skill"
                skill_count = len(l5_skills)
                events.append({
                    "time": S.normalize_event_time(item.get("learned_at") or item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")),
                    "layer": "L5", "event_type": "skill", "title": "\u6280\u80fd\u77e9\u9635",
                    "content": f"\u89e3\u9501\u65b0\u6280\u80fd\uff1a\u300c{skill_name}\u300d\uff08\u5df2\u638c\u63e1 {skill_count} \u9879\u6280\u80fd\uff09",
                })
                counts["L5"] += 1
        except Exception:
            pass

    l6_file = S.PRIMARY_STATE_DIR / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skills_used = l6_data.get("skills_used", {})
            for skill_name, data in skills_used.items():
                if not S.is_registered_skill_name(skill_name):
                    continue
                count = data.get("count", 0)
                tail = "\u8d8a\u6765\u8d8a\u719f\u7ec3\u4e86" if count >= 3 else "\u5df2\u7ecf\u7559\u4e0b\u7b2c\u4e00\u6b21\u6267\u884c\u75d5\u8ff9"
                events.append({
                    "time": S.normalize_event_time(data.get("last_used")),
                    "layer": "L6", "event_type": "evolution", "title": "\u6280\u80fd\u6267\u884c",
                    "content": f"\u4f7f\u7528\u4e86\uff1a\u300c{skill_name}\u300d \uff08{tail}\uff0c\u7d2f\u8ba1 {count} \u6b21\uff09",
                })
                counts["L6"] += 1
        except Exception:
            pass

    l7_file = S.PRIMARY_STATE_DIR / "feedback_rules.json"
    if l7_file.exists():
        try:
            l7_data = json.loads(l7_file.read_text(encoding="utf-8"))
            for item in l7_data:
                feedback = str(item.get("user_feedback") or "").strip()
                fix = str(item.get("fix") or "").strip()
                category = str(item.get("category") or "").strip()
                scene = str(item.get("scene") or "general").strip()
                content = feedback or "\u6536\u5230\u4e00\u6761\u65b0\u7684\u53cd\u9988\u4fee\u6b63\u89c4\u5219"
                if fix:
                    content = f"\u6536\u5230\u53cd\u9988\uff1a{content}\uff08\u4fee\u6b63\u65b9\u5411\uff1a{fix}\uff09"
                title = category or "\u53cd\u9988\u5b66\u4e60"
                events.append({
                    "time": S.normalize_event_time(item.get("created_at") or item.get("time")),
                    "layer": "L7", "event_type": "feedback", "title": title,
                    "content": content, "scene": scene,
                })
                counts["L7"] += 1
        except Exception:
            pass

    l8_file = S.PRIMARY_STATE_DIR / "knowledge_base.json"
    if l8_file.exists():
        try:
            l8_data = json.loads(l8_file.read_text(encoding="utf-8"))
            for item in l8_data:
                if not S.should_surface_knowledge_entry(item):
                    continue
                scene = str(item.get("\u4e8c\u7ea7\u573a\u666f") or item.get("\u6838\u5fc3\u6280\u80fd") or item.get("name") or "").strip()
                scene_name = scene.replace("\u81ea\u4e3b\u5b66\u4e60-", "") if scene else "\u65b0\u7ecf\u9a8c"
                summary = S.stringify_event_value(item.get("summary") or item.get("\u5e94\u7528\u793a\u4f8b") or "")
                content = f"\u4e60\u5f97\u7ecf\u9a8c\uff1a\u300c{scene_name}\u300d"
                if summary:
                    content += f"\uff1a{summary}"
                else:
                    content += "\uff08\u5c06\u8f6c\u5316\u4e3a\u6280\u80fd\u4f18\u5316\u4f9d\u636e\uff09"
                events.append({
                    "time": S.normalize_event_time(item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4") or item.get("time") or item.get("created_at")),
                    "layer": "L8", "event_type": "knowledge", "title": "\u80fd\u529b\u8fdb\u5316",
                    "content": content,
                })
                counts["L8"] += 1
        except Exception:
            pass

    return {"events": sorted(events, key=lambda item: item["time"], reverse=True), "counts": counts}


@router.get("/docs/index")
async def get_docs_index():
    sections = S.build_docs_index()
    default_path = ""
    for section in sections:
        docs = section.get("docs", [])
        if docs:
            default_path = docs[0].get("path", "")
            break
    return {"sections": sections, "default_path": default_path}


@router.get("/docs/content")
async def get_doc_content(path: str):
    doc_path = S.resolve_doc_path(path)
    if not doc_path or not doc_path.exists():
        return {"ok": False, "error": "doc_not_found"}
    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "path": doc_path.relative_to(S.ENGINE_DIR).as_posix(),
        "title": S.extract_doc_title(text, doc_path.stem),
        "content": text,
    }


@router.get("/skills")
async def get_skills():
    if not S.NOVA_CORE_READY:
        return {"skills": [], "ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        skills_data = S.get_all_skills()
        skills = []
        for name, info in skills_data.items():
            skills.append({
                "name": info.get("name", name),
                "keywords": info.get("keywords", []),
                "description": info.get("description", ""),
                "priority": info.get("priority", 10),
                "status": info.get("status", "ready"),
                "category": info.get("category", "\u901a\u7528"),
            })
        skills.sort(key=lambda item: (item.get("priority", 10), item.get("name", "")))
        return {"skills": skills, "ready": True}
    except Exception as exc:
        return {"skills": [], "ready": False, "error": str(exc)}


@router.get("/skills/news/headlines")
async def get_news_headlines():
    try:
        from core.skills.news import _parse_rss, GOOGLE_NEWS_FEEDS
        url = GOOGLE_NEWS_FEEDS.get("top", list(GOOGLE_NEWS_FEEDS.values())[0])
        items, _ = _parse_rss(url, limit=6)
        headlines = [item.get("title", "") for item in items if item.get("title")]
        return {"headlines": headlines}
    except Exception as e:
        return {"headlines": [], "error": str(e)}


@router.get("/history")
async def get_history():
    history = S.load_msg_history()
    formatted = []
    for item in history[-40:]:
        row = dict(item)
        if "time" in row:
            try:
                row["time"] = datetime.fromisoformat(row["time"]).strftime("%m-%d %H:%M")
            except Exception:
                pass
        formatted.append(row)
    return {"history": formatted, "text_history": S.get_text_history(20)}


@router.get("/stats")
async def get_stats():
    return {"stats": S.load_stats_data()}


@router.post("/stats")
async def update_stats(request: dict):
    inp = int(request.get("input_tokens", 0)) if isinstance(request, dict) else 0
    out = int(request.get("output_tokens", 0)) if isinstance(request, dict) else 0
    scene = str(request.get("scene", "chat")) if isinstance(request, dict) else "chat"
    stats = S.record_stats(input_tokens=inp, output_tokens=out, scene=scene)
    return {"ok": True, "stats": stats}


@router.get("/nova_name")
async def get_nova_name():
    persona_path = S.PRIMARY_STATE_DIR / "persona.json"
    if persona_path.exists():
        try:
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            return {"name": persona.get("nova_name", "NovaCore")}
        except Exception:
            pass
    return {"name": "NovaCore"}
