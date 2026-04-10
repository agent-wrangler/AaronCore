from __future__ import annotations

"""Reusable mini-game template scripts for run_code.

This package is not a skill entry and is not routed to directly.
It only exposes browser-side template code used by the run_code workflow.
"""

from tools.agent.game_templates.brick_breaker import SCRIPT as BRICK_BREAKER_SCRIPT
from tools.agent.game_templates.dodge import SCRIPT as DODGE_SCRIPT
from tools.agent.game_templates.snake import SCRIPT as SNAKE_SCRIPT

_SCRIPT_BY_TEMPLATE = {
    "brick_breaker": BRICK_BREAKER_SCRIPT,
    "snake": SNAKE_SCRIPT,
    "dodge": DODGE_SCRIPT,
}


def get_template_script(template_name: str) -> str:
    return _SCRIPT_BY_TEMPLATE.get(str(template_name or "").strip(), BRICK_BREAKER_SCRIPT)
