import json
import re
from pathlib import Path

from core.skills.save_export import execute as save_export_execute
from core.skills.article import _llm_call, _fetch_news
from core.runtime_state.state_loader import load_content_topic_registry, save_content_topic_registry
from core.task_store import (
    ensure_content_project_migrated,
    create_project,
    create_task,
    update_task,
    update_project,
    append_task_event,
    get_active_task_for_project,
    load_task_projects,
)

PROJECT_TITLE = "Default content pipeline"


def _strip_code_fence(text: str) -> str:
    raw = str(text or "").strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


def _normalize_topic_key(text: str) -> str:
    raw = str(text or "").lower().strip()
    raw = re.sub(r'https?://\S+', '', raw)
    raw = re.sub(r'\[[^\]]*\]', '', raw)
    raw = re.sub(r'[\W_]+', ' ', raw, flags=re.UNICODE)
    raw = re.sub(r'\s+', ' ', raw).strip()
    return raw[:120]


def _get_or_create_project():
    ensure_content_project_migrated()
    projects = load_task_projects()
    for item in projects:
        if isinstance(item, dict) and item.get("kind") == "content" and item.get("title") == PROJECT_TITLE:
            return item
    return create_project(
        "content",
        PROJECT_TITLE,
        status="active",
        goal={"summary": "持续产出内容选题与草稿"},
        settings={"source_mode": "news", "avoid_recent_days": 30},
        memory={"tags": ["content"]},
    )


def _topic_used(title: str, registry: dict) -> bool:
    key = _normalize_topic_key(title)
    for item in registry.get("used_topics", []):
        if not isinstance(item, dict):
            continue
        if item.get("normalized_key") == key:
            return True
        aliases = item.get("aliases") or []
        if key and key in [_normalize_topic_key(x) for x in aliases]:
            return True
    return False


def _register_topic(task: dict, project: dict, registry: dict):
    topic = ((task.get("artifacts") or {}).get("selected_topic") or {})
    title = topic.get("title") or ""
    if not title:
        return
    key = _normalize_topic_key(title)
    for item in registry.get("used_topics", []):
        if isinstance(item, dict) and item.get("normalized_key") == key:
            item["status"] = "drafted"
            return
    materials = ((task.get("artifacts") or {}).get("materials") or [])
    registry.setdefault("used_topics", []).append({
        "normalized_key": key,
        "display_title": title,
        "source_task_id": task.get("id"),
        "source_project_id": project.get("id"),
        "status": "drafted",
        "first_used_at": task.get("updated_at"),
        "last_used_at": task.get("updated_at"),
        "aliases": [title],
        "source_links": [m.get("link") for m in materials if isinstance(m, dict) and m.get("link")],
    })


def _pick_fresh_topic(materials, registry):
    fresh = [m for m in materials if not _topic_used(m.get("title", ""), registry)]
    if not fresh:
        return None, len(materials)
    titles = "\n".join(f"{i+1}. {m.get('title','')} [{m.get('source','')}]" for i, m in enumerate(fresh))
    prompt = (
        "你是内容策划编辑。下面是候选新闻素材。\n"
        "请从中选出一个最适合继续展开成长文/视频脚本前半段的题目。\n"
        "标准：有新鲜感、有展开空间、不是纯播报、容易形成观点。\n"
        "只返回序号数字。\n\n" + titles
    )
    picked = _llm_call(prompt, max_tokens=20, temperature=0.2) or "1"
    match = re.search(r'(\d+)', picked)
    idx = int(match.group(1)) - 1 if match else 0
    if idx < 0 or idx >= len(fresh):
        idx = 0
    return fresh[idx], len(materials) - len(fresh)


def _generate_angle(topic_title: str):
    prompt = (
        "你是内容策划编辑。请围绕下面这个题目，给出一个中文内容立意。\n"
        "输出格式严格为 JSON：{\"title\":\"...\",\"summary\":\"...\"}\n"
        "要求：summary 40-90字，强调为什么值得现在写。\n\n"
        f"题目：{topic_title}"
    )
    raw = _strip_code_fence(_llm_call(prompt, max_tokens=300, temperature=0.5) or "")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("summary"):
            return {"title": str(data.get("title") or topic_title), "summary": str(data.get("summary") or "").strip()}
    except Exception:
        pass
    return {"title": topic_title, "summary": str(raw).strip()[:120] or "从影响、背景和现实意义切入，形成可持续展开的内容观点。"}


def _generate_outline(topic_title: str, angle_summary: str):
    prompt = (
        "你是内容策划编辑。请根据题目和立意，生成一份中文内容提纲。\n"
        "输出严格为 JSON：{\"sections\":[\"...\",\"...\",\"...\",\"...\"]}\n"
        "要求：4段左右，每段一句话。\n\n"
        f"题目：{topic_title}\n立意：{angle_summary}"
    )
    raw = _strip_code_fence(_llm_call(prompt, max_tokens=400, temperature=0.5) or "")
    try:
        data = json.loads(raw)
        sections = data.get("sections") if isinstance(data, dict) else None
        if isinstance(sections, list) and sections:
            return {"sections": [str(x).strip() for x in sections if str(x).strip()]}
    except Exception:
        pass
    lines = [line.strip('-• \n\r\t') for line in raw.splitlines() if line.strip()]
    return {"sections": lines[:4] if lines else ["事件是什么", "为什么值得关注", "背后原因", "带来的影响"]}


def _generate_draft(topic_title: str, angle_summary: str, outline_sections):
    outline_text = "\n".join(f"- {s}" for s in (outline_sections or []))
    prompt = (
        "你是内容创作助手。请根据题目、立意和提纲，写一篇中文初稿。\n"
        "要求：700-1100字，信息清晰，像可继续修改的第一版，不要假装已经发布。\n"
        "输出格式：# 标题 + 正文。\n\n"
        f"题目：{topic_title}\n立意：{angle_summary}\n提纲：\n{outline_text}"
    )
    return (_strip_code_fence(_llm_call(prompt, max_tokens=2200, temperature=0.7) or "")).strip()


def _task_title_from_topic(topic_title: str) -> str:
    return topic_title.strip() or "content task"


def _export_task_artifact(task: dict, query: str) -> str:
    artifacts = task.get('artifacts') or {}
    draft = (artifacts.get('draft') or {}).get('content', '')
    topic = (artifacts.get('selected_topic') or {}).get('title', '') or 'content_draft'
    if not draft:
        return '当前还没有可导出的 draft。'
    destination = str(Path.home() / 'Desktop') if '桌面' in str(query or '') else ''
    return save_export_execute(
        query,
        {
            'fs_action': {
                'payload': {'content': draft, 'format': 'md'},
                'destination': {'path': destination} if destination else {},
            },
            'save_filename': topic,
            'save_content': draft,
            'save_format': 'md',
            'save_destination': destination,
        },
    )


def _build_reply(task: dict, duplicate_count: int = 0, continued: bool = False) -> str:
    artifacts = task.get("artifacts") or {}
    topic = (artifacts.get("selected_topic") or {}).get("title", "")
    angle = (artifacts.get("angle") or {}).get("summary", "")
    outline = (artifacts.get("outline") or {}).get("sections", [])
    draft = (artifacts.get("draft") or {}).get("content", "")
    lines = []
    lines.append("这轮内容任务我继续推进下去了。" if continued else "这轮内容规划已经跑完第一版了。")
    if duplicate_count:
        lines.append(f"已排除 {duplicate_count} 个重复选题。")
    if topic:
        lines.append(f"\n选题：{topic}")
    if angle:
        lines.append(f"立意：{angle}")
    if outline:
        lines.append("提纲：")
        lines.extend([f"- {s}" for s in outline[:6]])
    if draft:
        lines.append("\n初稿已经生成，可以继续让我换题、改立意、扩写或重写初稿。")
    return "\n".join(lines).strip()


def _run_new_cycle(project):
    registry = load_content_topic_registry()
    materials = _fetch_news(None) or []
    if not materials:
        return {"ok": False, "reply": "没抓到可用素材，这轮内容任务先跑不起来。"}
    topic_item, duplicate_count = _pick_fresh_topic(materials, registry)
    if not topic_item:
        return {"ok": False, "reply": "这批素材和历史选题重叠太多，暂时没有适合的新题。"}

    selected_topic = {
        "title": topic_item.get("title", ""),
        "normalized_key": _normalize_topic_key(topic_item.get("title", "")),
        "reason": "已从候选素材中选出可展开的新题。",
        "source": topic_item.get("source", ""),
        "link": topic_item.get("link", ""),
    }
    angle = _generate_angle(selected_topic["title"])
    outline = _generate_outline(selected_topic["title"], angle.get("summary", ""))
    draft = _generate_draft(selected_topic["title"], angle.get("summary", ""), outline.get("sections", []))

    task = create_task(
        "content",
        _task_title_from_topic(selected_topic["title"]),
        project_id=project.get("id"),
        status="draft_ready",
        stage="draft",
        intent={"source": "user_request", "summary": "Generate a new content draft from fresh news material"},
        input={"query": "content_task", "constraints": {"avoid_recent_topics": True}},
        plan={"steps": ["collect_materials", "select_topic", "generate_angle", "generate_outline", "generate_draft"]},
        artifacts={
            "materials": materials,
            "selected_topic": selected_topic,
            "angle": angle,
            "outline": outline,
            "draft": {"title": selected_topic["title"], "content": draft, "version": 1},
        },
        result={"summary": ""},
        memory={"resume_tokens": ["继续", "换题", "初稿"], "last_active_at": None},
        domain={"content": {"source_mode": "news", "topic_key": selected_topic["normalized_key"], "draft_version": 1}},
        events=[],
    )
    update_task(task["id"], {
        "result": {"summary": _build_reply({"artifacts": task.get("artifacts") or {}}, duplicate_count=duplicate_count)},
        "memory": {"resume_tokens": ["继续", "换题", "初稿"], "last_active_at": task.get("updated_at")},
    })
    task = update_task(task["id"], {"title": _task_title_from_topic(selected_topic["title"])}) or task
    append_task_event(task["id"], "created", "Task created")
    append_task_event(task["id"], "stage_changed", "Stage moved to draft")
    project["current_task_id"] = task["id"]
    project = update_project(project.get("id"), {"current_task_id": task.get("id")}) or project
    _register_topic(task, project, registry)
    save_content_topic_registry(registry)
    return {"ok": True, "task": get_active_task_for_project(project.get("id")), "duplicate_count": duplicate_count}


def _continue_task(project, query):
    task = get_active_task_for_project(project.get("id"))
    if not task:
        return _run_new_cycle(project)
    raw = str(query or "")
    if any(w in raw for w in ("换个题", "换题", "重新选题", "重选")):
        return _run_new_cycle(project)
    artifacts = task.get("artifacts") or {}
    if any(w in raw for w in ("写初稿", "继续写", "扩写", "继续这个项目", "继续", "继续这个内容任务")):
        if not ((artifacts.get("draft") or {}).get("content")):
            draft = _generate_draft(
                (artifacts.get("selected_topic") or {}).get("title", ""),
                (artifacts.get("angle") or {}).get("summary", ""),
                (artifacts.get("outline") or {}).get("sections", []),
            )
            artifacts["draft"] = {
                "title": (artifacts.get("selected_topic") or {}).get("title", ""),
                "content": draft,
                "version": 1,
            }
            update_task(task["id"], {"artifacts": artifacts, "stage": "draft", "status": "draft_ready"})
            append_task_event(task["id"], "stage_changed", "Stage moved to draft")
        updated = update_task(task["id"], {"result": {"summary": _build_reply({"artifacts": artifacts}, continued=True)}})
        return {"ok": True, "task": updated or task, "duplicate_count": 0, "continued": True}
    updated = update_task(task["id"], {"result": {"summary": _build_reply({"artifacts": artifacts}, continued=True)}})
    return {"ok": True, "task": updated or task, "duplicate_count": 0, "continued": True}


def execute(query, context=None):
    project = _get_or_create_project()
    raw = str(query or "").strip()
    active_task = get_active_task_for_project(project.get("id"))
    if any(w in raw for w in ('导出', '保存', '存到')) and active_task:
        return _export_task_artifact(active_task, raw)
    is_continue = any(w in raw for w in ("继续", "换个题", "换题", "初稿", "这个项目", "内容任务")) and active_task
    result = _continue_task(project, raw) if is_continue else _run_new_cycle(project)
    if not result.get("ok"):
        return result.get("reply", "这轮内容任务没有跑起来。")
    task = result.get("task") or {}
    return _build_reply(task, duplicate_count=result.get("duplicate_count", 0), continued=result.get("continued", False))
