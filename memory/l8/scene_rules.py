"""Scene classification rules for L8 knowledge learning."""

from __future__ import annotations


FEEDBACK_SCENE_TO_PRIMARY = {
    "joke": "内容创作",
    "story": "内容创作",
    "routing": "系统能力",
    "chat": "系统功能",
    "general": "",
}


def infer_primary_scene(
    query: str = "",
    *,
    feedback_scene: str = "",
    route_result: dict | None = None,
) -> str:
    if feedback_scene:
        mapped = FEEDBACK_SCENE_TO_PRIMARY.get(feedback_scene, "")
        if mapped:
            return mapped

    if route_result and isinstance(route_result, dict):
        mode = route_result.get("mode", "")
        skill = route_result.get("skill", "")
        if mode in ("skill", "hybrid") and skill and skill != "none":
            return "工具应用"

    return "自主学习"
