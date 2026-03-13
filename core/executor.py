# Executor - 技能执行层
# 负责：统一调用技能、处理结果、封装异常

from core.skills import get_skill


def execute(skill_route: dict, user_input: str) -> dict:
    """统一执行入口"""
    skill_name = (skill_route or {}).get('skill')

    if not skill_name:
        return {
            'success': False,
            'skill': None,
            'response': '',
            'error': '未提供技能名'
        }

    skill = get_skill(skill_name)
    if not skill:
        return {
            'success': False,
            'skill': skill_name,
            'response': '',
            'error': f'技能 {skill_name} 未找到'
        }

    exec_func = skill.get('execute')
    if not callable(exec_func):
        return {
            'success': False,
            'skill': skill_name,
            'response': '',
            'error': f'技能 {skill_name} 没有可执行函数'
        }

    try:
        result = exec_func(user_input)
        return {
            'success': True,
            'skill': skill_name,
            'response': result if isinstance(result, str) else str(result),
            'error': None,
        }
    except Exception as e:
        return {
            'success': False,
            'skill': skill_name,
            'response': '',
            'error': f'执行失败: {str(e)}'
        }
