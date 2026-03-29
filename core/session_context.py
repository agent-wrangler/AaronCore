# L2 会话上下文兼容层
# 当前真实主链已经不再依赖这里做规则式话题/意图路由。
# 这个模块现在主要保留接口兼容性，默认返回空结构，避免把旧心智模型重新带回来。


def extract_session_context(history: list, current_input: str = "") -> dict:
    """返回空的 L2 结构，占位兼容旧调用方，不承担当前主链理解职责。"""
    return {
        "topics": [],
        "mood": "",
        "intents": [],
        "follow_up": {},
        "stage": "",
        "attitude": "",
    }
