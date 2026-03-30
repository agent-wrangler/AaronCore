"""数据查询路由：memory, docs, history, stats, nova_name"""
import json
import re
from datetime import datetime
from fastapi import APIRouter
from core import shared as S
from core.l2_memory import classify_retention_bucket
from core.l8_learn import classify_l8_entry_kind, should_show_l8_timeline_entry
from core.state_loader import get_model_price, MODEL_PRICES

router = APIRouter()


def _is_live_skill_name(skill_name: str) -> bool:
    skill_name = str(skill_name or "").strip()
    if not skill_name:
        return False

    checker = getattr(S, "is_registered_skill_name", None)
    if callable(checker):
        try:
            if checker(skill_name):
                return True
        except Exception:
            pass

    registry_loader = getattr(S, "get_all_skills", None)
    if callable(registry_loader):
        try:
            skills = registry_loader() or {}
            return skill_name in skills
        except Exception:
            pass

    return False


def _l8_source_label(kind: str) -> str:
    if kind == "dialogue_crystal":
        return "对话结晶"
    if kind == "feedback_relearn":
        return "纠偏补学"
    return "自主学习"


def _l2_type_label(memory_type: str) -> str:
    memory_type = str(memory_type or "").strip().lower()
    mapping = {
        "fact": "事实印象",
        "preference": "偏好印象",
        "rule": "规则印象",
        "project": "项目线索",
        "goal": "目标意图",
        "decision": "决策印象",
        "knowledge": "知识线索",
        "correction": "纠正印象",
        "skill_demand": "需求线索",
        "general": "对话印象",
    }
    return mapping.get(memory_type, "对话印象")


def _build_l2_meta(item: dict, ai_brief: str, *, hit_count: int | None = None, crystallized: bool | None = None) -> dict:
    memory_type = str(item.get("memory_type") or "general").strip().lower() or "general"
    retention_entry = dict(item)
    if hit_count is not None:
        retention_entry["hit_count"] = int(hit_count or 0)
    if crystallized is not None:
        retention_entry["crystallized"] = bool(crystallized)
    retention = classify_retention_bucket(retention_entry)
    return {
        "kind": "l2_impression",
        "memory_type": memory_type,
        "type_label": _l2_type_label(memory_type),
        "user_text": str(item.get("user_text") or "").strip(),
        "ai_brief": ai_brief,
        "hit_count": int(retention_entry.get("hit_count") or 0),
        "crystallized": bool(retention_entry.get("crystallized")),
        "retention_tier": retention["tier"],
        "retention_label": retention["label"],
        "retention_reason": retention["reason"],
        "age_days": retention["age_days"],
    }


def _build_l2_ai_brief(ai_text: str) -> str:
    ai_text = str(ai_text or "").strip()
    ai_clean = re.sub(r'^[\s\uff08\u0028][^\uff09\u0029]*[\uff09\u0029]\s*', '', ai_text)
    ai_clean = ai_clean.replace("\n", " ").strip()
    if not ai_clean:
        ai_clean = ai_text.replace("\n", " ").strip()
    ai_brief = ai_clean
    for sep in ["。", "！", "？", "～", "~"]:
        if sep in ai_brief:
            ai_brief = ai_brief[:ai_brief.index(sep) + 1]
            break
    if len(ai_brief) > 40:
        ai_brief = ai_brief[:40] + "…"
    return ai_brief


def _build_l2_event(item: dict, ai_brief: str, repeat_count: int = 1, hit_count: int | None = None, crystallized: bool | None = None) -> dict:
    user_text = str(item.get("user_text") or "").strip()
    content = f"“{user_text}”"
    if ai_brief:
        content += f" —— {ai_brief}"
    meta = _build_l2_meta(item, ai_brief, hit_count=hit_count, crystallized=crystallized)
    meta["repeat_count"] = max(1, int(repeat_count or 1))
    return {
        "time": S.normalize_event_time(item.get("created_at") or item.get("time")),
        "layer": "L2",
        "event_type": "impression",
        "title": _l2_type_label(item.get("memory_type")),
        "content": content,
        "meta": meta,
    }


def _safe_stringify(value) -> str:
    formatter = getattr(S, "stringify_event_value", None)
    if callable(formatter):
        try:
            return formatter(value)
        except Exception:
            pass
    return str(value or "").strip()


@router.get("/memory")
async def get_memory():
    S.ensure_long_term_clean()
    events = []
    counts = {"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0, "L8": 0}

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

    l2_file = S.PRIMARY_STATE_DIR / "l2_short_term.json"
    if l2_file.exists():
        try:
            l2_data = json.loads(l2_file.read_text(encoding="utf-8"))
            if isinstance(l2_data, list):
                counts["L2"] = len(l2_data)
                general_groups = {}
                for item in l2_data:
                    imp = item.get("importance") or 0
                    if imp >= 0.7:
                        user_text = str(item.get("user_text") or "").strip()
                        if not user_text:
                            continue
                        ai_brief = _build_l2_ai_brief(item.get("ai_text"))
                        memory_type = str(item.get("memory_type") or "general").strip().lower() or "general"
                        if memory_type == "general":
                            group = general_groups.get(user_text)
                            raw_time = str(item.get("created_at") or item.get("time") or "").strip()
                            if not group:
                                general_groups[user_text] = {
                                    "item": item,
                                    "ai_brief": ai_brief,
                                    "time_raw": raw_time,
                                    "repeat_count": 1,
                                    "hit_count": int(item.get("hit_count") or 0),
                                    "crystallized": bool(item.get("crystallized")),
                                }
                            else:
                                group["repeat_count"] += 1
                                group["hit_count"] += int(item.get("hit_count") or 0)
                                group["crystallized"] = group["crystallized"] or bool(item.get("crystallized"))
                                if raw_time and (not group["time_raw"] or raw_time >= group["time_raw"]):
                                    group["item"] = item
                                    group["ai_brief"] = ai_brief
                                    group["time_raw"] = raw_time
                            continue

                        events.append(_build_l2_event(item, ai_brief))

                for group in general_groups.values():
                    events.append(
                        _build_l2_event(
                            group["item"],
                            group["ai_brief"],
                            repeat_count=group["repeat_count"],
                            hit_count=group["hit_count"],
                            crystallized=group["crystallized"],
                        )
                    )
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
            visible_l5_skills = [
                item for item in l5_skills
                if isinstance(item, dict) and str(item.get("source") or "").strip() != "l2_demand"
            ]
            for item in visible_l5_skills:
                skill_name = item.get("name") or item.get("\u6838\u5fc3\u6280\u80fd") or "skill"
                skill_count = len(visible_l5_skills)
                source = str(item.get("source") or "").strip()
                if source == "l6_success_path":
                    content = str(item.get("summary") or item.get("\u5e94\u7528\u793a\u4f8b") or "").strip()
                    if not content:
                        content = f"\u6c89\u6dc0\u4e86\u300c{skill_name}\u300d\u7684\u7a33\u5b9a\u6210\u529f\u7ecf\u9a8c"
                    success_count = int(item.get("success_count", item.get("\u4f7f\u7528\u6b21\u6570", 0)) or 0)
                    events.append({
                        "time": S.normalize_event_time(item.get("learned_at") or item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")),
                        "layer": "L5", "event_type": "method_experience", "title": "\u65b9\u6cd5\u7ecf\u9a8c",
                        "content": f"{skill_name} / {content} / \u5df2\u6c89\u6dc0 {success_count} \u6b21",
                        "meta": {
                            "kind": "method_experience",
                            "skill": skill_name,
                            "summary": content,
                            "success_count": success_count,
                            "source": source,
                        },
                    })
                    counts["L5"] += 1
                    continue
                events.append({
                    "time": S.normalize_event_time(item.get("learned_at") or item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")),
                    "layer": "L5", "event_type": "ability_hint", "title": "\u80fd\u529b\u7ebf\u7d22",
                    "content": f"\u8bb0\u5f55\u4e86\u300c{skill_name}\u300d\u8fd9\u6761\u80fd\u529b\u7ebf\u7d22\uff08\u5f53\u524d L5 \u53ef\u89c1 {skill_count} \u9879\uff09",
                    "meta": {
                        "kind": "ability_hint",
                        "skill": skill_name,
                        "visible_count": skill_count,
                        "source": source,
                    },
                })
                counts["L5"] += 1
        except Exception:
            pass

    l6_file = S.PRIMARY_STATE_DIR / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skill_runs = l6_data.get("skill_runs", [])
            if isinstance(skill_runs, list) and skill_runs:
                for item in reversed(skill_runs[-80:]):
                    if not isinstance(item, dict):
                        continue
                    skill_name = str(item.get("skill") or "").strip()
                    if not _is_live_skill_name(skill_name):
                        continue
                    verified = item.get("verified")
                    observed = str(item.get("observed_state") or "").strip()
                    drift_reason = str(item.get("drift_reason") or "").strip()
                    summary = str(item.get("summary") or "").strip()
                    verification_mode = str(item.get("verification_mode") or "").strip()
                    verification_detail = str(item.get("verification_detail") or "").strip()
                    parts = [skill_name]
                    if summary:
                        parts.append(summary)
                    if verified is True:
                        parts.append("verified")
                    elif drift_reason:
                        parts.append(f"drift={drift_reason}")
                    if observed:
                        parts.append(f"observed={observed}")
                    events.append({
                        "time": S.normalize_event_time(item.get("at")),
                        "layer": "L6", "event_type": "execution_trace", "title": "\u6267\u884c\u8f68\u8ff9",
                        "content": " / ".join([p for p in parts if p]),
                        "meta": {
                            "kind": "execution_trace",
                            "skill": skill_name,
                            "summary": summary,
                            "verified": verified,
                            "observed_state": observed,
                            "drift_reason": drift_reason,
                            "verification_mode": verification_mode,
                            "verification_detail": verification_detail,
                        },
                    })
                    counts["L6"] += 1
            else:
                skills_used = l6_data.get("skills_used", {})
                for skill_name, data in skills_used.items():
                    if not _is_live_skill_name(skill_name):
                        continue
                    count = data.get("count", 0)
                    tail = "\u8d8a\u6765\u8d8a\u719f\u7ec3\u4e86" if count >= 3 else "\u5df2\u7ecf\u7559\u4e0b\u7b2c\u4e00\u6b21\u6267\u884c\u75d5\u8ff9"
                    events.append({
                        "time": S.normalize_event_time(data.get("last_used")),
                        "layer": "L6", "event_type": "execution_trace", "title": "\u6267\u884c\u8f68\u8ff9",
                        "content": f"\u4f7f\u7528\u4e86\uff1a\u300c{skill_name}\u300d \uff08{tail}\uff0c\u7d2f\u8ba1 {count} \u6b21\uff09",
                        "meta": {
                            "kind": "execution_count",
                            "skill": skill_name,
                            "count": count,
                            "status_note": tail,
                        },
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
                if not should_show_l8_timeline_entry(item):
                    continue
                kind = classify_l8_entry_kind(item)
                query = str(item.get("query") or item.get("name") or "已学知识").strip()
                summary = _safe_stringify(item.get("summary") or item.get("应用示例") or "")
                primary_scene = str(item.get("一级场景") or "").strip()
                secondary_scene = str(item.get("二级场景") or "").strip()
                hit_count = int(item.get("hit_count", 0) or 0)
                source_label = _l8_source_label(kind)
                content = f"学到「{query}」"
                if summary:
                    content += f"：{summary}"
                else:
                    content += "，已沉淀为新的知识卡片"
                events.append({
                    "time": S.normalize_event_time(item.get("last_used") or item.get("最近使用时间") or item.get("time") or item.get("created_at")),
                    "layer": "L8", "event_type": kind, "title": source_label,
                    "content": content,
                    "meta": {
                        "kind": kind,
                        "query": query,
                        "summary": summary,
                        "source": str(item.get("source") or "").strip(),
                        "source_label": source_label,
                        "hit_count": hit_count,
                        "primary_scene": primary_scene,
                        "secondary_scene": secondary_scene,
                        "keywords": item.get("keywords") or item.get("trigger") or [],
                    },
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


@router.get("/history")
async def get_history(limit: int = 40, offset: int = 0):
    history = S.load_msg_history()
    total = len(history)
    # offset=0 表示最新的，从末尾往前取
    if offset <= 0:
        chunk = history[-limit:] if limit < total else history
    else:
        end = total - offset
        start = max(0, end - limit)
        chunk = history[start:end] if end > 0 else []
    formatted = []
    for item in chunk:
        row = dict(item)
        if "time" in row:
            try:
                row["time"] = datetime.fromisoformat(row["time"]).strftime("%m-%d %H:%M")
            except Exception:
                pass
        formatted.append(row)
    return {"history": formatted, "text_history": S.get_text_history(20), "total": total, "has_more": (total - offset - limit) > 0}


@router.get("/stats")
async def get_stats():
    stats = S.load_stats_data()
    stats["prices"] = get_model_price(stats.get("model", ""))
    stats["all_prices"] = MODEL_PRICES
    # ── 补充真实的 L3/L5 计数（快照值不可靠，直接读文件）──────────
    mem = stats.setdefault("memory", {})
    try:
        l3_raw = json.loads((S.PRIMARY_STATE_DIR / "long_term.json").read_text("utf-8"))
        real_l3 = sum(1 for i in l3_raw if isinstance(i, dict) and not S.is_legacy_l3_skill_log(i))
        mem["real_l3_count"] = real_l3
    except Exception:
        mem["real_l3_count"] = mem.get("l3_count", 0)
    try:
        from core.skills_loader import get_all_skills
        mem["real_l5_count"] = len(get_all_skills())
    except Exception:
        try:
            kb = json.loads((S.PRIMARY_STATE_DIR / "knowledge.json").read_text("utf-8"))
            mem["real_l5_count"] = len(kb) if isinstance(kb, list) else 0
        except Exception:
            mem["real_l5_count"] = mem.get("l5_count", 0)
    try:
        persona = json.loads((S.PRIMARY_STATE_DIR / "persona.json").read_text("utf-8"))
        if not isinstance(persona, dict):
            persona = {}
        active_mode = str(persona.get("active_mode") or "").strip()
        persona_modes = persona.get("persona_modes") or {}
        mode_cfg = persona_modes.get(active_mode) if isinstance(persona_modes, dict) else {}
        if not isinstance(mode_cfg, dict):
            mode_cfg = {}
        speech_style = persona.get("speech_style") or {}
        if not isinstance(speech_style, dict):
            speech_style = {}

        def _count_nonempty(value):
            if isinstance(value, dict):
                return sum(_count_nonempty(v) for v in value.values())
            if isinstance(value, list):
                return sum(1 for item in value if str(item or "").strip())
            return 1 if str(value or "").strip() else 0

        def _recent_update_count(changelog, limit_days=7):
            now = datetime.now()
            total = 0
            for item in changelog if isinstance(changelog, list) else []:
                if not isinstance(item, dict):
                    continue
                raw = str(item.get("time") or item.get("created_at") or "").strip()
                if not raw:
                    continue
                try:
                    ts = datetime.fromisoformat(raw.replace("/", "-"))
                except Exception:
                    try:
                        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M")
                    except Exception:
                        continue
                if (now - ts).days <= limit_days:
                    total += 1
            return total

        user_profile = persona.get("user_profile") or {}
        relationship_profile = persona.get("relationship_profile") or {}
        ai_profile = persona.get("ai_profile") or {}
        rules = persona.get("interaction_rules") or []
        tone = mode_cfg.get("tone") or speech_style.get("tone") or []
        particles = mode_cfg.get("particles") or speech_style.get("particles") or []
        avoid = mode_cfg.get("avoid") or speech_style.get("avoid") or []
        style_prompt = str(mode_cfg.get("style_prompt") or persona.get("style_prompt") or "").strip()
        changelog = persona.get("_changelog") or []

        mem["real_l4_active_mode"] = active_mode or "default"
        mem["real_l4_rule_count"] = len(rules) if isinstance(rules, list) else 0
        mem["real_l4_profile_count"] = (
            _count_nonempty(user_profile) +
            _count_nonempty(relationship_profile) +
            _count_nonempty(ai_profile)
        )
        mem["real_l4_tone_count"] = len(tone) if isinstance(tone, list) else 0
        mem["real_l4_particle_count"] = len(particles) if isinstance(particles, list) else 0
        mem["real_l4_avoid_count"] = len(avoid) if isinstance(avoid, list) else 0
        mem["real_l4_style_prompt"] = 1 if style_prompt else 0
        mem["real_l4_changelog_count"] = len(changelog) if isinstance(changelog, list) else 0
        mem["real_l4_recent_updates"] = _recent_update_count(changelog, limit_days=7)
    except Exception:
        mem.setdefault("real_l4_active_mode", "default")
        mem.setdefault("real_l4_rule_count", 0)
        mem.setdefault("real_l4_profile_count", 0)
        mem.setdefault("real_l4_tone_count", 0)
        mem.setdefault("real_l4_particle_count", 0)
        mem.setdefault("real_l4_avoid_count", 0)
        mem.setdefault("real_l4_style_prompt", 0)
        mem.setdefault("real_l4_changelog_count", 0)
        mem.setdefault("real_l4_recent_updates", 0)
    return {"stats": stats}


@router.post("/stats")
async def update_stats(request: dict):
    inp = int(request.get("input_tokens", 0)) if isinstance(request, dict) else 0
    out = int(request.get("output_tokens", 0)) if isinstance(request, dict) else 0
    scene = str(request.get("scene", "chat")) if isinstance(request, dict) else "chat"
    cache_write = int(request.get("cache_write", 0)) if isinstance(request, dict) else 0
    cache_read = int(request.get("cache_read", 0)) if isinstance(request, dict) else 0
    model = str(request.get("model", "")) if isinstance(request, dict) else ""
    stats = S.record_stats(
        input_tokens=inp,
        output_tokens=out,
        scene=scene,
        cache_write=cache_write,
        cache_read=cache_read,
        model=model,
    )
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
