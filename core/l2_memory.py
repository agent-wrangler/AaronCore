"""
L2 持久记忆引擎 — 评分入库 + 关键词检索 + 自动结晶 + 每20轮摘要
存储：memory_db/l2_short_term.json（不设上限）
"""

import re
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from core.json_store import load_json, write_json
from core.state_loader import PRIMARY_STATE_DIR

# ── 文件路径 ──
L2_FILE = PRIMARY_STATE_DIR / "l2_short_term.json"
L2_CFG  = PRIMARY_STATE_DIR / "l2_config.json"
L3_FILE = PRIMARY_STATE_DIR / "long_term.json"
L4_FILE = PRIMARY_STATE_DIR / "persona.json"
L5_FILE = PRIMARY_STATE_DIR / "knowledge.json"
L7_FILE = PRIMARY_STATE_DIR / "feedback_rules.json"
L8_FILE = PRIMARY_STATE_DIR / "knowledge_base.json"

# ── 依赖注入 ──
_debug_write = lambda stage, data: None
_think = None

def init(*, debug_write=None, think=None):
    global _debug_write, _think
    if debug_write: _debug_write = debug_write
    if think: _think = think

# ── 重要性关键词 ──
_HIGH = ['我叫','我在','我住','喜欢','想要','目标','决定','讨厌','记住','偏好','绝对','必须']
_MED  = ['在做','项目','开发','研究','计划','AI','产品']
_LOW  = ['你好','哈哈','嗯','啊','哦']

def score_importance(text: str) -> float:
    s = 0.5
    for kw in _HIGH:
        if kw in text:
            s = max(s, 0.85); break
    for kw in _MED:
        if kw in text:
            s = max(s, 0.6); break
    for kw in _LOW:
        if kw in text and len(text) < 10:
            s = min(s, 0.25)
    return s

def _detect_type(text: str) -> str:
    t = text.lower()
    # 纠正/不满 → L7
    if any(k in t for k in ['不对','错了','不好','太短','太长','不是这个','说错']): return 'correction'
    # 技能需求（"帮我做/能不能/怎么用" + 不存在的能力）→ L5
    if any(k in t for k in ['帮我做','能不能','你会不会','有没有功能','可以帮我']): return 'skill_demand'
    # 知识类（"什么是/为什么/怎么回事/是什么意思/谁是"）→ L8
    if any(k in t for k in ['什么是','是什么','为什么','怎么回事','是谁','意思是','原理']): return 'knowledge'
    if any(k in t for k in ['喜欢','偏好','讨厌']): return 'preference'
    if any(k in t for k in ['想要','目标','计划']): return 'goal'
    if any(k in t for k in ['项目','在做','开发','产品']): return 'project'
    if any(k in t for k in ['决定','选择']): return 'decision'
    if any(k in t for k in ['我叫','我是','我在','我住','人在','定居','坐标']): return 'fact'
    if any(k in t for k in ['记住','不要','必须','规则']): return 'rule'
    return 'general'

# ── 关键词提取 ──
_KW_MAP = {
    '天气':'天气','气温':'天气','温度':'天气',
    '股票':'股票','股价':'股票',
    '画':'画图','海报':'画图',
    '故事':'故事','小说':'故事',
    '代码':'编程','编程':'编程','python':'编程','bug':'编程',
    '笑话':'笑话',
    '喜欢':'喜欢','偏好':'偏好','讨厌':'讨厌',
    '目标':'目标','想要':'想要','计划':'计划',
    '项目':'项目','开发':'开发','产品':'产品',
    'AI':'AI','人工智能':'AI',
    '创业':'创业','研究':'研究',
}

def _extract_kw(text: str) -> list:
    found = []
    tl = text.lower()
    for trigger, kw in _KW_MAP.items():
        if trigger in tl and kw not in found:
            found.append(kw)
    chars = re.sub(r'[^\u4e00-\u9fff\w]', '', text)
    for i in range(len(chars)-1):
        bg = chars[i:i+2]
        if len(bg)==2 and bg not in found:
            found.append(bg)
    return found[:20]

# ── 文本相关度 ──
def _relevance(query: str, stored: str, stored_kw: list) -> float:
    qkw = _extract_kw(query)
    # keyword overlap
    if qkw and stored_kw:
        ov = len(set(qkw) & set(stored_kw))
        ks = min(ov / max(len(qkw),1), 1.0)
    else:
        ks = 0.0
    # bigram overlap
    qc = re.sub(r'\s+','',query.lower())
    sc = re.sub(r'\s+','',stored.lower())
    bs = 0.0
    if len(qc)>=2:
        m = sum(1 for i in range(len(qc)-1) if qc[i:i+2] in sc)
        bs = m / max(len(qc)-1, 1)
    # direct substring
    ds = 0.8 if (query.lower() in stored.lower() or stored.lower() in query.lower()) else 0.0
    return max(ks, bs, ds)

def _freshness(created_at: str) -> float:
    try:
        d = (datetime.now() - datetime.fromisoformat(created_at)).total_seconds() / 86400
        return 1.0 / (1.0 + 0.1 * d)
    except: return 0.5

# ── 存储操作 ──
def _load():  return load_json(L2_FILE, [])
def _save(d): write_json(L2_FILE, d)
def _cfg():   return load_json(L2_CFG, {"total_rounds":0,"last_summary_round":0,"total_summaries":0})
def _save_cfg(c): write_json(L2_CFG, c)

THRESHOLD = 0.35

def add_memory(user_input: str, ai_response: str):
    """每轮对话后调用，评分入库+结晶+摘要检查"""
    if not user_input or not user_input.strip():
        return None
    imp = score_importance(user_input)
    if imp < THRESHOLD:
        _debug_write("l2_skip", {"input": user_input[:50], "imp": imp})
        return None
    mtype = _detect_type(user_input)
    kws = _extract_kw(user_input)
    mid = f"l2_{int(time.time()*1000)}"
    entry = {
        "id": mid, "user_text": user_input, "ai_text": ai_response,
        "importance": imp, "memory_type": mtype, "keywords": kws,
        "created_at": datetime.now().isoformat(),
        "hit_count": 0, "crystallized": False,
    }
    store = _load()
    store.append(entry)
    _save(store)
    _debug_write("l2_add", {"id":mid,"imp":imp,"type":mtype})
    # 结晶
    _try_crystallize(entry)
    # 摘要检查
    cfg = _cfg()
    cfg["total_rounds"] = cfg.get("total_rounds",0) + 1
    _save_cfg(cfg)
    _auto_summary(cfg, store)
    # 每50轮自动清理一次低价值记忆
    if cfg["total_rounds"] % 50 == 0:
        cleanup_stale_memories()
    return {"id": mid, "importance": imp, "type": mtype}

def search_relevant(query: str, limit: int = 8) -> list:
    """关键词+文本匹配检索，final = relevance*0.7 + freshness*0.3"""
    if not query or not query.strip():
        return []
    store = _load()
    if not store:
        return []
    scored = []
    for m in store:
        rel = _relevance(query, m.get("user_text",""), m.get("keywords",[]))
        frs = _freshness(m.get("created_at",""))
        fs = rel * 0.7 + frs * 0.3
        if fs > 0.15:
            scored.append({**m, "relevance":round(rel,3), "freshness":round(frs,3), "final_score":round(fs,3)})
    scored.sort(key=lambda x: x["final_score"], reverse=True)
    result = scored[:limit]
    if result:
        _bump_hits([r["id"] for r in result])
    return result

def _bump_hits(ids):
    try:
        store = _load()
        changed = False
        for m in store:
            if m.get("id") in ids:
                m["hit_count"] = m.get("hit_count",0)+1
                changed = True
        if changed: _save(store)
    except: pass

# ── 自动结晶（L2 中枢分发）──
def _try_crystallize(entry):
    imp = entry.get("importance",0)
    mtype = entry.get("memory_type","general")
    text = entry.get("user_text","")
    ai_text = entry.get("ai_text","")

    # L7: 纠正/不满 — 不要求高分，只要检测到就推
    if mtype == "correction":
        _to_l7(text, ai_text)

    # L5: 技能需求 — 不要求高分，记录需求信号
    if mtype == "skill_demand":
        _to_l5(text)

    # L8: 知识类 — 不要求高分，用户问了知识问题且Nova回答了就存
    if mtype == "knowledge" and len(ai_text) > 20:
        _to_l8(text, ai_text)

    # 城市提取 — 不受分数限制，用户提到"我在X"就更新L4
    _try_update_city(text)

    # 以下需要高分才结晶
    if imp <= 0.7:
        return
    _mark_crystal(entry["id"])
    if mtype in ("event","milestone","general","decision"):
        _to_l3(text, mtype)
    if mtype in ("fact","preference","goal","rule"):
        _to_l4(text, mtype)

def _mark_crystal(mid):
    try:
        store = _load()
        for m in store:
            if m.get("id")==mid:
                m["crystallized"]=True; break
        _save(store)
    except: pass

def _to_l3(text, mtype):
    try:
        l3 = load_json(L3_FILE, [])
        for it in l3[-20:]:
            if text in str(it.get("summary","")) or str(it.get("summary","")) in text:
                return
        l3.append({
            "summary": text,
            "type": "event" if mtype in ("event","general","decision") else mtype,
            "source": "l2_crystallize",
            "created_at": datetime.now().isoformat(),
        })
        write_json(L3_FILE, l3)
        _debug_write("l2_crystal_l3", {"text":text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l3_err", {"err":str(e)})

_KNOWN_CITIES = [
    "常州","北京","上海","苏州","南京","杭州","广州","深圳",
    "大理","成都","重庆","武汉","长沙","西安","天津","青岛",
    "厦门","昆明","贵阳","郑州","济南","合肥","福州","南昌",
    "哈尔滨","长春","沈阳","大连","无锡","宁波","温州","东莞",
    "佛山","珠海","三亚","拉萨","乌鲁木齐","呼和浩特","银川",
    "兰州","西宁","海口","南宁","石家庄","太原",
]

def _append_l4_changelog(persona: dict, content: str):
    """在 persona.json 里追加一条变更日志，供记忆页展示"""
    changelog = persona.setdefault("_changelog", [])
    changelog.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
    })
    # 只保留最近 50 条
    if len(changelog) > 50:
        persona["_changelog"] = changelog[-50:]

def _try_update_city(text):
    """独立的城市提取，不受重要性分数限制"""
    try:
        city_m = re.search(r'(?:\u6211\u5728|\u6211\u4f4f|\u5750\u6807|\u4eba\u5728|\u5b9a\u5c45)([^\s\uff0c,\u3002\u3001\uff01!\uff1f?\u7684\u4e86]+)', text)
        if not city_m:
            return
        candidate = city_m.group(1).strip()
        for city in _KNOWN_CITIES:
            if city in candidate:
                persona = load_json(L4_FILE, {})
                up = persona.setdefault("user_profile",{})
                old_city = str(up.get("city","")).strip()
                if old_city != city:
                    up["city"] = city
                    _append_l4_changelog(persona, f"\u7528\u6237\u66f4\u65b0\u4e86\u5730\u5740\uff1a{city}")
                    write_json(L4_FILE, persona)
                    _debug_write("l2_city_update", {"old": old_city, "new": city})
                return
    except Exception as e:
        _debug_write("l2_city_update_err", {"err": str(e)})

def _to_l4(text, mtype):
    try:
        persona = load_json(L4_FILE, {})
        updated = False
        if '\u6211\u53eb' in text:
            m = re.search(r'\u6211\u53eb([^\s\uff0c,\u3002\u3001\uff01!\uff1f?]+)', text)
            if m:
                up = persona.setdefault("user_profile",{})
                eid = str(up.get("identity",""))
                name = m.group(1)
                if name not in eid:
                    up["identity"] = (eid+"\uff0c"+f"\u53eb{name}").strip("\uff0c")
                    updated = True
        if mtype == "preference":
            up = persona.setdefault("user_profile",{})
            ep = str(up.get("preference",""))
            short = text[:60]
            if short not in ep:
                up["preference"] = (ep+"\uff1b"+short).strip("\uff1b")
                updated = True
        if mtype == "rule":
            rules = persona.setdefault("interaction_rules",[])
            if not any(text[:30] in str(r) for r in rules):
                rules.append(text)
                updated = True
        if updated:
            _append_l4_changelog(persona, text[:60])
            write_json(L4_FILE, persona)
            _debug_write("l2_crystal_l4", {"text":text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l4_err", {"err":str(e)})

def _to_l5(text):
    """L2→L5：记录技能需求信号，帮助发现用户需要但还没有的技能"""
    try:
        l5 = load_json(L5_FILE, [])
        # 检查是否已有此需求记录
        for item in l5:
            if isinstance(item, dict) and item.get("source") == "l2_demand":
                if text[:30] in str(item.get("trigger", [])):
                    # 已有，累加计数
                    item["demand_count"] = item.get("demand_count", 1) + 1
                    item["last_demand"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    write_json(L5_FILE, l5)
                    return
        # 新增需求记录
        l5.append({
            "source": "l2_demand",
            "trigger": [text[:50]],
            "demand_count": 1,
            "last_demand": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "unmet",
        })
        write_json(L5_FILE, l5)
        _debug_write("l2_crystal_l5", {"text": text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l5_err", {"err": str(e)})

def _to_l7(text, ai_text):
    """L2→L7：检测到纠正/不满时，带上对话上下文推给L7，让反馈更精准"""
    try:
        l7 = load_json(L7_FILE, [])
        # 去重：同样的反馈不重复记
        for item in l7:
            if isinstance(item, dict) and text[:20] in str(item.get("user_feedback", "")):
                return
        l7.append({
            "id": f"l2_fb_{int(time.time()*1000)}",
            "source": "l2_context",
            "created_at": datetime.now().isoformat(),
            "enabled": True,
            "user_feedback": text,
            "last_answer": ai_text[:200] if ai_text else "",
            "l2_context": "L2检测到用户纠正/不满",
        })
        write_json(L7_FILE, l7)
        _debug_write("l2_crystal_l7", {"text": text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l7_err", {"err": str(e)})

def _to_l8(text, ai_text):
    """L2→L8：知识类对话沉淀到知识库，Nova下次就记住了"""
    try:
        l8 = load_json(L8_FILE, [])
        # 去重：相同问题不重复存
        for item in l8:
            if isinstance(item, dict):
                existing_q = str(item.get("query", ""))
                if text[:20] in existing_q or existing_q in text:
                    return
        # 上限500条（和L8原有逻辑一致）
        if len(l8) >= 500:
            l8 = l8[-499:]
        kws = _extract_kw(text)
        l8.append({
            "id": f"l2_k_{int(time.time()*1000)}",
            "source": "l2_crystallize",
            "type": "knowledge",
            "query": text,
            "name": text[:30],
            "summary": ai_text[:500] if ai_text else "",
            "keywords": kws[:10],
            "hit_count": 0,
            "created_at": datetime.now().isoformat(),
        })
        write_json(L8_FILE, l8)
        _debug_write("l2_crystal_l8", {"text": text[:50]})
    except Exception as e:
        _debug_write("l2_crystal_l8_err", {"err": str(e)})

# ── 每20轮自动摘要 ──
SUMMARY_INTERVAL = 20

def _auto_summary(cfg, store):
    total = cfg.get("total_rounds",0)
    last = cfg.get("last_summary_round",0)
    if total - last < SUMMARY_INTERVAL:
        return
    recent = store[-SUMMARY_INTERVAL:]
    if len(recent) < 10:
        return
    summary = _gen_summary(recent, last+1, total)
    if not summary:
        return
    try:
        l3 = load_json(L3_FILE, [])
        l3.append({
            "summary": summary,
            "type": "event",
            "source": "l2_auto_summary",
            "metadata": {"start_round":last+1, "end_round":total},
            "created_at": datetime.now().isoformat(),
        })
        write_json(L3_FILE, l3)
    except: pass
    cfg["last_summary_round"] = total
    cfg["total_summaries"] = cfg.get("total_summaries",0) + 1
    _save_cfg(cfg)
    _debug_write("l2_summary", {"rounds":f"{last+1}-{total}"})

def _gen_summary(mems, start, end):
    if _think:
        try:
            dialog = ""
            for m in mems[-SUMMARY_INTERVAL:]:
                dialog += f"\u7528\u6237: {m.get('user_text','')}\nNova: {m.get('ai_text','')[:100]}\n\n"
            prompt = (
                f"\u4ee5\u4e0b\u662f\u7b2c{start}\u8f6e\u5230\u7b2c{end}\u8f6e\u7684\u5bf9\u8bdd\u8bb0\u5f55\uff0c"
                "\u8bf7\u75281-2\u53e5\u8bdd\u63d0\u70bc\u8981\u70b9\uff08\u5173\u6ce8\u7528\u6237\u63d0\u5230\u7684\u4e8b\u5b9e\u3001\u504f\u597d\u3001\u91cd\u8981\u4e8b\u4ef6\uff09\uff0c"
                "\u4e0d\u8981\u5217\u6e05\u5355\uff0c\u7528\u81ea\u7136\u7684\u53d9\u8ff0\u8bed\u6c14\uff1a\n\n"
                + dialog[:2000]
            )
            result = _think(prompt, "")
            if isinstance(result, dict):
                txt = str(result.get("reply","")).strip()
            else:
                txt = str(result or "").strip()
            if len(txt) > 5:
                return txt
        except: pass
    # fallback
    kps = []
    imp_kw = ['\u9879\u76ee','\u76ee\u6807','\u559c\u6b22','\u51b3\u5b9a','\u6b63\u5728','\u5f00\u53d1','\u60f3\u505a','AI','\u521b\u4e1a','\u8bb0\u4f4f']
    for m in mems:
        ut = m.get("user_text","")
        if any(k in ut for k in imp_kw) and len(ut)>5:
            kps.append(ut[:40])
    if kps:
        return f"\u5bf9\u8bdd\u8981\u70b9\uff08\u7b2c{start}-{end}\u8f6e\uff09\uff1a" + "\uff1b".join(kps[:5])
    return f"\u7b2c{start}-{end}\u8f6e\u4e3a\u4e00\u822c\u6027\u4ea4\u6d41\u3002"

# ── 格式化（供prompt注入）──
def format_l2_context(memories: list) -> str:
    if not memories:
        return ""
    lines = []
    for m in memories:
        ut = m.get("user_text","")[:80]
        at = m.get("ai_text","")[:60]
        imp = m.get("importance",0)
        marker = "\u2605" if imp >= 0.7 else "\u00b7"
        line = f"{marker} {ut}"
        if at:
            line += f" \u2192 {at}"
        lines.append(line)
    return "\n".join(lines)

# ── 统计 ──
def get_stats() -> dict:
    store = _load()
    cfg = _cfg()
    return {
        "total_memories": len(store),
        "total_rounds": cfg.get("total_rounds",0),
        "total_summaries": cfg.get("total_summaries",0),
        "high_value": sum(1 for m in store if m.get("importance",0) >= 0.7),
        "crystallized": sum(1 for m in store if m.get("crystallized")),
    }

# ── 定期清理低分记忆 ──
# 规则：
#   永久保留：importance >= 0.7 或 已结晶(crystallized=True)
#   30天清理：importance < 0.5 且 hit_count == 0（存了30天没人检索过）
#   60天清理：importance < 0.5 且 hit_count <= 2（60天内几乎没用过）
#   90天清理：importance < 0.7 且 hit_count <= 1（90天兜底）

def cleanup_stale_memories() -> dict:
    """定期清理低价值记忆，返回清理统计"""
    store = _load()
    if not store:
        return {"before": 0, "after": 0, "removed": 0}

    now = datetime.now()
    kept = []
    removed = 0

    for m in store:
        imp = m.get("importance", 0.5)
        hits = m.get("hit_count", 0)
        crystal = m.get("crystallized", False)

        # 已结晶的永远保留
        if crystal:
            kept.append(m)
            continue
        # 高分永远保留
        if imp >= 0.7:
            kept.append(m)
            continue

        # 算天数
        try:
            age_days = (now - datetime.fromisoformat(m.get("created_at", ""))).days
        except Exception:
            age_days = 999

        # 30天：低分+零检索 → 清掉
        if age_days >= 30 and imp < 0.5 and hits == 0:
            removed += 1
            continue
        # 60天：低分+几乎没用 → 清掉
        if age_days >= 60 and imp < 0.5 and hits <= 2:
            removed += 1
            continue
        # 90天：中分+几乎没用 → 清掉
        if age_days >= 90 and imp < 0.7 and hits <= 1:
            removed += 1
            continue

        kept.append(m)

    if removed > 0:
        _save(kept)
        _debug_write("l2_cleanup", {
            "before": len(store), "after": len(kept), "removed": removed
        })

    return {"before": len(store), "after": len(kept), "removed": removed}
