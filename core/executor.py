# Executor - 技能执行层
# 负责：统一调用技能、处理结果、封装异常、注入用户上下文

from core.fs_protocol import attempt_fs_repair, execute_write_file_action, verify_post_condition
from core.skills import get_skill

_PROTOCOL_SKILLS = {'folder_explore', 'open_target', 'save_export', 'file_copy', 'file_move', 'file_delete', 'app_target', 'ui_interaction', 'write_file'}
_DIRECT_PROTOCOL_EXECUTORS = {
    'write_file': execute_write_file_action,
}


def _result_dict_success(result: dict, meta: dict) -> bool:
    if not isinstance(result, dict):
        return True
    if 'success' in result:
        return bool(result.get('success'))
    meta = meta if isinstance(meta, dict) else {}
    drift = meta.get('drift') if isinstance(meta.get('drift'), dict) else {}
    if str(drift.get('reason') or '').strip():
        return False
    post = meta.get('post_condition') if isinstance(meta.get('post_condition'), dict) else {}
    if post and post.get('ok') is False:
        return False
    return True


def _derive_protocol_post_check(skill_name: str, user_input: str, context: dict) -> tuple[str, str, dict] | None:
    context = context if isinstance(context, dict) else {}
    fs_action = context.get('fs_action') if isinstance(context.get('fs_action'), dict) else {}
    target = fs_action.get('target') if isinstance(fs_action.get('target'), dict) else {}

    action = str(fs_action.get('action') or '').strip()
    target_value = str(target.get('path') or target.get('url') or target.get('app') or target.get('window') or '').strip()
    extra = {}

    if action and target_value:
        if action == 'open' and str(target.get('url') or '').strip():
            action = 'open_url'
            extra['search_term'] = user_input
        if action == 'ui_interact':
            extra['window_title'] = str(target.get('window') or context.get('window_title') or '').strip()
        if action in {'copy', 'move'}:
            destination = fs_action.get('destination') if isinstance(fs_action.get('destination'), dict) else {}
            extra['destination'] = str(destination.get('path') or context.get('destination') or '').strip()
        return action, target_value, extra

    if skill_name == 'open_target':
        target_value = str(context.get('path') or context.get('url') or context.get('target') or '').strip()
        if target_value:
            action = 'open_url' if target_value.startswith(('http://', 'https://')) else 'open'
            extra['search_term'] = user_input
            return action, target_value, extra

    if skill_name == 'folder_explore':
        target_value = str(context.get('path') or context.get('target') or '').strip()
        if target_value:
            return 'inspect', target_value, {}

    if skill_name == 'save_export':
        target_value = str(context.get('path') or context.get('file_path') or context.get('save_path') or '').strip()
        if target_value:
            return 'save', target_value, {}

    if skill_name == 'write_file':
        target_value = str(context.get('file_path') or context.get('path') or context.get('target') or context.get('filename') or '').strip()
        if target_value:
            return 'write_file', target_value, {}

    if skill_name == 'app_target':
        target_value = str(context.get('target') or context.get('app') or context.get('path') or '').strip()
        if target_value:
            lowered = str(user_input or '').lower()
            action = 'close_app' if any(word in str(user_input or '') for word in ('关闭', '退出')) or any(word in lowered for word in ('close', 'quit', 'exit')) else 'launch_app'
            app_label = str(context.get('app') or context.get('label') or '').strip()
            if not app_label:
                try:
                    from pathlib import Path
                    app_label = Path(target_value).stem
                except Exception:
                    app_label = ''
            extra = {}
            if app_label:
                extra['window_title'] = app_label
                extra['app_label'] = app_label
            return action, target_value, extra

    if skill_name == 'ui_interaction':
        target_value = str(context.get('target') or context.get('window_title') or '').strip()
        if target_value:
            return 'ui_interact', target_value, {'window_title': target_value}

    if skill_name == 'file_delete':
        target_value = str(context.get('path') or context.get('target') or '').strip()
        if target_value:
            return 'delete', target_value, {}

    if skill_name == 'file_copy':
        target_value = str(context.get('path') or context.get('source') or context.get('target') or '').strip()
        destination = str(context.get('destination') or context.get('destination_path') or '').strip()
        if target_value:
            return 'copy', target_value, {'destination': destination}

    if skill_name == 'file_move':
        target_value = str(context.get('path') or context.get('source') or context.get('target') or '').strip()
        destination = str(context.get('destination') or context.get('destination_path') or '').strip()
        if target_value:
            return 'move', target_value, {'destination': destination}

    return None


def _merge_protocol_post_into_meta(meta: dict, post: dict) -> dict:
    meta = meta if isinstance(meta, dict) else {}
    post = post if isinstance(post, dict) else {}
    if not post:
        return meta

    state = meta.get('state') if isinstance(meta.get('state'), dict) else {}
    drift = meta.get('drift') if isinstance(meta.get('drift'), dict) else {}

    if not state.get('expected_state') and post.get('expected'):
        state['expected_state'] = str(post.get('expected'))
    if not state.get('observed_state') and post.get('observed'):
        state['observed_state'] = str(post.get('observed'))

    if (not drift.get('reason')) and not bool(post.get('ok', True)):
        if post.get('expected'):
            state['expected_state'] = str(post.get('expected'))
        if post.get('observed'):
            state['observed_state'] = str(post.get('observed'))
        drift['reason'] = str(post.get('drift') or '').strip()
        drift['repair_hint'] = str(post.get('hint') or '').strip()

    meta['state'] = state
    meta['drift'] = drift
    meta['post_condition'] = post
    if not bool(post.get('ok', True)):
        meta['repair_succeeded'] = False
    return meta


def execute(skill_route: dict, user_input: str, context: dict | None = None) -> dict:
    """统一执行入口

    skill_route: 路由结果 {"skill": "weather", ...}
    user_input:  用户原文
    context:     用户上下文（L4 user_profile 等），技能可按需读取
    """
    skill_name = (skill_route or {}).get('skill')
    context = context if isinstance(context, dict) else {}

    if not skill_name:
        return {
            'success': False,
            'skill': None,
            'response': '',
            'error': '未提供技能名'
        }

    direct_protocol_executor = _DIRECT_PROTOCOL_EXECUTORS.get(skill_name)
    if callable(direct_protocol_executor):
        try:
            result = direct_protocol_executor(context or {}, user_input=user_input)
            if isinstance(result, dict) and 'success' in result:
                result.setdefault('skill', skill_name)
                return result
            return {
                'success': False,
                'skill': skill_name,
                'response': '',
                'error': f'协议技能 {skill_name} 返回结果无效',
            }
        except Exception as e:
            return {
                'success': False,
                'skill': skill_name,
                'response': f'执行失败: {str(e)}',
                'error': f'执行失败: {str(e)}'
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
        # 优先尝试传 context，技能可选择接不接
        import inspect
        sig = inspect.signature(exec_func)
        if len(sig.parameters) >= 2:
            result = exec_func(user_input, context or {})
        else:
            result = exec_func(user_input)
        response = result if isinstance(result, str) else str(result)
        if isinstance(result, dict):
            meta = {
                'state': result.get('state') if isinstance(result.get('state'), dict) else {},
                'drift': result.get('drift') if isinstance(result.get('drift'), dict) else {},
                'action': result.get('action') if isinstance(result.get('action'), dict) else {},
                'repair_attempted': bool(result.get('repair_attempted', False)),
                'repair_succeeded': bool(result.get('repair_succeeded', False)),
            }
            if result.get('image_url'):
                meta['image_url'] = str(result.get('image_url')).strip()
            if skill_name in _PROTOCOL_SKILLS:
                post_spec = _derive_protocol_post_check(skill_name, user_input, context)
                if post_spec:
                    action, target_value, extra = post_spec
                    post = verify_post_condition(action, target_value, **extra)
                    meta = _merge_protocol_post_into_meta(meta, post)
            if skill_name in _PROTOCOL_SKILLS and meta.get('drift', {}).get('reason'):
                fs_action = (context.get('fs_action') or {}) if isinstance(context.get('fs_action'), dict) else {}
                action = str(fs_action.get('action') or '').strip()
                target_value = str((fs_action.get('target') or {}).get('path') or (fs_action.get('target') or {}).get('url') or (fs_action.get('target') or {}).get('app') or (fs_action.get('target') or {}).get('window') or '').strip()
                repair = attempt_fs_repair(skill_name, {**context, 'last_user_input': user_input}, meta)
                if repair.get('repairable'):
                    repaired_context = repair.get('updated_context') if isinstance(repair.get('updated_context'), dict) else context
                    repaired_input = str(repair.get('rewritten_input') or user_input)
                    sleep_before = float(repair.get('sleep_before') or 0)
                    if sleep_before > 0:
                        import time
                        time.sleep(sleep_before)
                    if len(sig.parameters) >= 2:
                        repaired_result = exec_func(repaired_input, repaired_context or {})
                    else:
                        repaired_result = exec_func(repaired_input)
                    if isinstance(repaired_result, dict):
                        repaired_post_spec = _derive_protocol_post_check(skill_name, repaired_input, repaired_context or {})
                        if repaired_post_spec:
                            action, target_value, extra = repaired_post_spec
                            post = verify_post_condition(action, target_value, **extra)
                        else:
                            post = {'ok': True, 'drift': ''}
                        repaired_meta = {
                            'state': repaired_result.get('state') if isinstance(repaired_result.get('state'), dict) else {},
                            'drift': repaired_result.get('drift') if isinstance(repaired_result.get('drift'), dict) else {},
                            'action': repaired_result.get('action') if isinstance(repaired_result.get('action'), dict) else {},
                            'repair_attempted': True,
                            'repair_succeeded': post.get('ok', False) and not bool((repaired_result.get('drift') or {}).get('reason')),
                            'post_condition': post,
                        }
                        repaired_meta = _merge_protocol_post_into_meta(repaired_meta, post)
                        return {
                            'success': _result_dict_success(repaired_result, repaired_meta),
                            'skill': skill_name,
                            'response': str(repaired_result.get('reply', '') or ''),
                            'error': None if _result_dict_success(repaired_result, repaired_meta) else str(repaired_result.get('reply', '') or ''),
                            'meta': repaired_meta,
                        }
            success = _result_dict_success(result, meta)
            return {
                'success': success,
                'skill': skill_name,
                'response': str(result.get('reply', '') or ''),
                'error': None if success else str(result.get('reply', '') or ''),
                'meta': meta,
            }
        drift_match = None
        try:
            import re
            drift_match = re.search(r'\[drift:\s*expected=([^\s\]]+)\s+observed=([^\s\]]+)\s+hint=([^\]\n]+)\]', response)
        except Exception:
            drift_match = None
        meta = {}
        if drift_match:
            meta['drift'] = {
                'expected_state': drift_match.group(1),
                'observed_state': drift_match.group(2),
                'repair_hint': drift_match.group(3).strip(),
            }
        return {
            'success': True,
            'skill': skill_name,
            'response': response,
            'error': None,
            'meta': meta,
        }
    except Exception as e:
        try:
            from core.shared import debug_write
            import traceback
            debug_write("skill_execute_exception", {"skill": skill_name, "error": str(e), "tb": traceback.format_exc()[:500]})
        except Exception:
            pass
        return {
            'success': False,
            'skill': skill_name,
            'response': f'执行失败: {str(e)}',
            'error': f'执行失败: {str(e)}'
        }
