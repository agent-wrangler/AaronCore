import json
import re

from tasks.store import create_project, create_task, update_task, update_project, get_active_task_for_project, create_relation, append_task_event

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


def execute(query, context=None):
    raw = str(query or '').strip()
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
