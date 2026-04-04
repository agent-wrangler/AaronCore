"""Reply hygiene cleanup helpers."""


def l1_hygiene_clean(
    response: str,
    history: list,
    window: int = 8,
    min_repeat: int = 3,
    *,
    prefer_tool_grounded_tail,
    strip_mid_reply_restart,
    re_mod,
):
    response = str(response or "").strip()
    response = prefer_tool_grounded_tail(response)
    response, restart_removed = strip_mid_reply_restart(response)

    if not response or not history:
        return response, restart_removed

    recent_nova = []
    for item in reversed(history):
        if isinstance(item, dict) and item.get("role") in ("nova", "assistant"):
            content = str(item.get("content") or "").strip()
            if content:
                recent_nova.append(content)
        if len(recent_nova) >= window:
            break

    if len(recent_nova) < min_repeat:
        return response, restart_removed

    toxic_phrases = []

    first_line = response.lstrip().split("\n")[0].strip()
    if len(first_line) >= 5:
        prefix = first_line[: min(20, len(first_line))]
        match_count = sum(1 for item in recent_nova if item.lstrip().startswith(prefix))
        if match_count >= min_repeat:
            toxic_phrases.append(first_line)

    lines = [line.strip() for line in response.split("\n") if line.strip()]
    for line in lines:
        if len(line) < 5 or len(line) > 50:
            continue
        if line in ("---", "...", "```", "```python", "```json"):
            continue
        if all(ord(ch) > 0x2000 or ch in " \t" for ch in line):
            continue
        match_count = sum(1 for item in recent_nova if line in item)
        if match_count >= min_repeat and line not in toxic_phrases:
            toxic_phrases.append(line)

    if not toxic_phrases:
        return response, restart_removed

    cleaned = response
    for phrase in toxic_phrases:
        cleaned = cleaned.replace(phrase, "", 1).strip()

    cleaned = re_mod.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re_mod.sub(r"^\s*---\s*$", "", cleaned, flags=re_mod.MULTILINE)
    cleaned = re_mod.sub(r"\n{3,}", "\n\n", cleaned).strip()

    removed = list(restart_removed) + toxic_phrases
    return (cleaned if cleaned else response), removed
