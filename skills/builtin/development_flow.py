import json
import re

from core.fs_protocol import build_operation_result
from core.task_store import (
    get_active_task_plan_snapshot,
    get_active_task_working_state,
    get_structured_fs_target_for_task_plan,
)
from decision.tool_runtime.ask_user import execute_ask_user
from tasks.store import (
    append_task_event,
    create_project,
    create_relation,
    create_task,
    get_active_task_for_project,
    get_latest_active_task_by_kind,
    resolve_task_for_goal,
    update_project,
    update_task,
)

PROJECT_TITLE = 'Default development pipeline'


def _llm_plan(goal: str) -> dict:
    try:
        from core.skills.article import _llm_call
    except Exception:
        _llm_call = None
    if not _llm_call:
        return {
            'understanding': '当前目标更像开发/修复任务，需要先确认问题范围、涉及文件和验证方式。',
            'next_steps': ['定位相关文件', '确认复现方式', '决定先改哪里'],
        }
    prompt = (
        '你是软件工程任务规划助手。请把下面这个开发目标先整理成一个非常短的理解摘要和 3 个下一步。\n'
        '输出严格为 JSON：{"understanding":"...","next_steps":["...","...","..."]}\n\n'
        f'目标：{goal}'
    )
    raw = str(_llm_call(prompt, max_tokens=300, temperature=0.2) or '').strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```$', '', raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {
                'understanding': str(data.get('understanding') or '').strip(),
                'next_steps': [str(x).strip() for x in (data.get('next_steps') or []) if str(x).strip()][:3],
            }
    except Exception:
        pass
    lines = [line.strip('-• \n\r\t') for line in raw.splitlines() if line.strip()]
    return {
        'understanding': lines[0] if lines else '这是一个开发任务，需要先理解目标与上下文。',
        'next_steps': lines[1:4] if len(lines) > 1 else ['定位相关文件', '确认复现方式', '决定先改哪里'],
    }


def _get_or_create_project():
    from tasks.store import load_task_projects
    projects = load_task_projects()
    for item in projects:
        if isinstance(item, dict) and item.get('kind') == 'development' and item.get('title') == PROJECT_TITLE:
            return item
    return create_project(
        'development',
        PROJECT_TITLE,
        status='active',
        goal={'summary': '持续推进开发/修复任务'},
        memory={'tags': ['development']},
    )


def _build_reply(task: dict) -> str:
    result = task.get('result') or {}
    plan = task.get('plan') or {}
    understanding = (result.get('understanding') or '').strip()
    next_steps = result.get('next_steps') or plan.get('steps') or []
    lines = ['这个开发任务我先接住了。']
    if understanding:
        lines.append(f'\n理解：{understanding}')
    if next_steps:
        lines.append('下一步：')
        lines.extend([f'- {s}' for s in next_steps[:5]])
    lines.append('\n我已经把这些下一步落成子任务了，你现在可以继续让我展开其中一步。')
    return '\n'.join(lines)


def _extract_ask_user_answer(result: dict) -> str:
    response = str((result or {}).get("response") or "").strip()
    if "：" in response:
        return response.split("：", 1)[-1].strip()
    if ":" in response:
        return response.split(":", 1)[-1].strip()
    return response


def _same_task_plan(left: dict | None, right: dict | None) -> bool:
    left_id = str((left or {}).get("task_id") or "").strip()
    right_id = str((right or {}).get("task_id") or "").strip()
    return bool(left_id and right_id and left_id == right_id)


def _load_open_task_plan_context(query: str) -> tuple[dict, dict, dict, dict]:
    latest_plan = get_active_task_plan_snapshot("") or {}
    matched_plan = get_active_task_plan_snapshot(query) or {}
    working_state = get_active_task_working_state("") or {}
    plan_target = get_structured_fs_target_for_task_plan(latest_plan) or {}
    return latest_plan, matched_plan, working_state, plan_target


def _build_existing_task_summary(latest_plan: dict, working_state: dict) -> str:
    goal = str((working_state or {}).get("goal") or (latest_plan or {}).get("goal") or "").strip()
    current_step = str((working_state or {}).get("current_step") or "").strip()
    blocker = str((working_state or {}).get("blocker") or "").strip()
    if goal and current_step:
        return f"{goal}（当前步骤：{current_step}）"
    if goal and blocker:
        return f"{goal}（当前卡点：{blocker}）"
    return goal or "上一个开发任务"


def _build_existing_development_task_summary(task: dict) -> str:
    raw = task if isinstance(task, dict) else {}
    title = str(raw.get("title") or (raw.get("input") or {}).get("query") or "").strip()
    stage = str(raw.get("stage") or "").strip()
    if title and stage:
        return f"{title}（当前阶段：{stage}）"
    return title or "上一个开发任务"


def _build_continue_existing_result(latest_plan: dict, working_state: dict, latest_dev_task: dict | None = None) -> dict:
    goal = str((working_state or {}).get("goal") or (latest_plan or {}).get("goal") or "").strip()
    if not goal:
        goal = str((latest_dev_task or {}).get("title") or ((latest_dev_task or {}).get("input") or {}).get("query") or "").strip()
    goal = goal or "上一个开发任务"
    current_step = str((working_state or {}).get("current_step") or "").strip()
    if not current_step:
        current_step = str((latest_dev_task or {}).get("stage") or "").strip()
    blocker = str((working_state or {}).get("blocker") or "").strip()
    lines = ["这轮我先不新开开发任务，继续上一个。", f"当前目标：{goal}"]
    if current_step:
        lines.append(f"当前步骤：{current_step}")
    if blocker:
        lines.append(f"当前卡点：{blocker}")
    lines.append("如果你其实想新开一个开发任务，直接说一声就行。")
    reply = "\n".join(lines)
    detail_parts = [f"goal={goal}"]
    if current_step:
        detail_parts.append(f"current_step={current_step}")
    result = build_operation_result(
        reply,
        expected_state="development_task_selected",
        observed_state="existing_task_selected",
        action_kind="development_flow",
        target_kind="task",
        target=goal[:160],
        outcome="selected",
        display_hint="继续上一个开发任务",
        verification_mode="task_plan_selection",
        verification_detail=" | ".join(detail_parts),
    )
    result["verification"] = {
        "verified": True,
        "observed_state": "existing_task_selected",
        "detail": " | ".join(detail_parts),
    }
    if isinstance(latest_plan, dict) and latest_plan:
        result["task_plan"] = latest_plan
    return result


def _maybe_disambiguate_open_task(query: str) -> dict | None:
    latest_plan, matched_plan, working_state, plan_target = _load_open_task_plan_context(query)
    latest_dev_task = get_latest_active_task_by_kind("development") or {}
    matched_dev_task = resolve_task_for_goal("development", query) or {}
    latest_plan_is_dev_like = bool(str((plan_target or {}).get("path") or "").strip())

    if not latest_dev_task and not (latest_plan and latest_plan_is_dev_like):
        return None
    if latest_dev_task and matched_dev_task and str(latest_dev_task.get("id") or "").strip() == str(matched_dev_task.get("id") or "").strip():
        return _build_continue_existing_result(latest_plan, working_state, latest_dev_task=latest_dev_task)
    if latest_plan and latest_plan_is_dev_like and _same_task_plan(latest_plan, matched_plan):
        return _build_continue_existing_result(latest_plan, working_state, latest_dev_task=latest_dev_task)

    summary = (
        _build_existing_development_task_summary(latest_dev_task)
        if latest_dev_task
        else _build_existing_task_summary(latest_plan, working_state)
    )
    selection = execute_ask_user(
        {
            "question": f"我这边还有一个没收住的开发任务：{summary}。这次要继续它，还是按新开发任务处理？",
            "options": ["继续上一个开发任务", "按新开发任务处理"],
        }
    )
    if not bool(selection.get("success")):
        detail = str(selection.get("response") or "").strip() or "未收到继续/新开选择"
        reply = "我先停在开发任务分流这里，等你决定是继续上一个还是新开一个。"
        result = build_operation_result(
            reply,
            expected_state="development_task_selected",
            observed_state="selection_timeout",
            drift_reason="user_choice_timeout",
            repair_hint="retry_development_task_choice",
            action_kind="development_flow",
            target_kind="task",
            target=str((latest_dev_task or {}).get("title") or (latest_plan or {}).get("goal") or query or "")[:160],
            outcome="blocked",
            display_hint="等待开发任务分流选择",
            verification_mode="ask_user",
            verification_detail=detail,
        )
        result["verification"] = {
            "verified": False,
            "observed_state": "selection_timeout",
            "detail": detail,
        }
        if latest_plan and latest_plan_is_dev_like:
            result["task_plan"] = latest_plan
        return result

    answer = _extract_ask_user_answer(selection)
    if "继续" in answer:
        return _build_continue_existing_result(latest_plan, working_state, latest_dev_task=latest_dev_task)
    return None


def execute(query, context=None):
    raw = str(query or '').strip()
    disambiguation = _maybe_disambiguate_open_task(raw)
    if disambiguation is not None:
        return disambiguation
    project = _get_or_create_project()
    planning = _llm_plan(raw)
    next_steps = planning.get('next_steps') or []
    task = create_task(
        'development',
        raw[:80] or 'development task',
        project_id=project.get('id'),
        status='planned',
        stage='understand',
        intent={'source': 'development_flow', 'summary': raw},
        input={'query': raw},
        plan={'steps': next_steps},
        result={'understanding': planning.get('understanding') or '', 'next_steps': next_steps},
        memory={'last_user_reference': raw, 'resume_tokens': ['继续', '处理', '修复', '开始'], 'last_active_at': None},
        domain={'development': {'source': 'task_intake'}},
        events=[],
    )
    append_task_event(task['id'], 'created', 'Development task created')
    for idx, step in enumerate(next_steps):
        child = create_task(
            'plan_step',
            step,
            project_id=project.get('id'),
            parent_task_id=task.get('id'),
            status='planned',
            stage='queued',
            intent={'source': 'development_substep', 'summary': step},
            input={'query': step},
            domain={'development_step': {'index': idx + 1}},
            events=[],
        )
        create_relation(task['id'], child['id'], 'parent_of', index=idx + 1)
    update_project(project.get('id'), {'current_task_id': task.get('id')})
    update_task(task['id'], {'stage': 'planned', 'status': 'planned'})
    return _build_reply(task)
