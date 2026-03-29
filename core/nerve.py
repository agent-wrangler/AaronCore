"""
nerve.py — 执行验证模块
检测 LLM "说了但没做"（声称执行了操作但未发起 tool_call）。

设计原则：
- 只检测，不执行。检测到异常后交回 LLM 重试，不替 LLM 做决策
- LLM 是理解层，代码不替它判断意图、不替它查 URL
- 只在 tool_used 为 None 时触发
"""

import re

from core.shared import debug_write

# ── 执行声明模式：LLM 声称执行了但实际没调工具 ──
_CLAIM_PATTERNS = re.compile(
    r'(?:✅|已打开|已执行|打开成功|执行成功|命令已发送|已启动|<function_calls>|执行打开)'
)


def detect_unfired_claim(llm_text: str, tool_used: str | None) -> bool:
    """
    检测 LLM 是否 "说了但没做"。

    条件：
    1. tool_used 为 None（LLM 没调任何工具）
    2. LLM 回复中包含执行声明（✅、已打开、执行成功等）

    返回: True = 检测到虚假执行声明，应让 LLM 重试
    """
    if tool_used is not None:
        return False

    llm_text = (llm_text or "").strip()
    if not llm_text:
        return False

    has_claim = bool(_CLAIM_PATTERNS.search(llm_text))
    if has_claim:
        debug_write("nerve_unfired_claim", {"llm_preview": llm_text[:120]})
    return has_claim
