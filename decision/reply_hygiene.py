"""Reply hygiene cleanup helpers."""


def strip_chat_emphasis_markdown(response: str, *, re_mod) -> str:
    text = str(response or "")
    if "**" not in text and "__" not in text:
        return text

    protected_segments: list[str] = []

    def _protect(match):
        protected_segments.append(match.group(0))
        return f"\u0000MDPROTECT{len(protected_segments) - 1}\u0000"

    protected = re_mod.sub(r"```.*?```|`[^`\n]*`", _protect, text, flags=re_mod.S)
    protected = re_mod.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"\1", protected)
    protected = re_mod.sub(r"__(?=\S)(.+?)(?<=\S)__", r"\1", protected)
    protected = protected.replace("**", "").replace("__", "")

    for index, original in enumerate(protected_segments):
        protected = protected.replace(f"\u0000MDPROTECT{index}\u0000", original)
    return protected


def _strip_decorative_markdown(response: str, *, re_mod) -> str:
    return strip_chat_emphasis_markdown(response, re_mod=re_mod)


def _strip_trailing_list_punctuation(text: str) -> str:
    return str(text or "").strip().rstrip(" \t\uff0c,\uff1b;\u3002.!?\uff01\uff1f")


def _looks_like_explicit_structure_label(text: str) -> bool:
    label = str(text or "").strip()
    if not label:
        return False
    explicit_markers = (
        "\u6b65\u9aa4",
        "\u6e05\u5355",
        "\u5217\u8868",
        "\u5bf9\u6bd4",
        "\u5982\u4e0b",
        "\u5206\u4e3a",
        "\u5206\u6210",
        "\u5305\u62ec",
        "\u8ba1\u5212",
    )
    return any(marker in label for marker in explicit_markers)


def flatten_simple_chat_list(response: str, *, re_mod) -> str:
    text = str(response or "").strip()
    if not text or "```" in text or "`" in text or "|" in text:
        return text

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or len(lines) > 5:
        return text

    list_item_re = re_mod.compile(r"^\s*(?:[-*•]\s+|(?:\d+|[A-Za-z]|[一二三四五六七八九十]+)[\.\)\u3001]\s+)(.+?)\s*$")
    first_list_index = next((index for index, line in enumerate(lines) if list_item_re.match(line)), None)
    if first_list_index is None:
        return text

    prefix_lines = lines[:first_list_index]
    list_lines = lines[first_list_index:]
    if len(prefix_lines) > 1:
        return text

    prefix = prefix_lines[0] if prefix_lines else ""
    if prefix:
        if len(prefix) > 24:
            return text
        if not prefix.endswith(("\uff1a", ":")):
            return text
        if _looks_like_explicit_structure_label(prefix):
            return text

    items: list[str] = []
    for line in list_lines:
        match = list_item_re.match(line)
        if not match:
            return text
        item = match.group(1).strip()
        if (
            not item
            or len(item) > 28
            or "`" in item
            or "http://" in item
            or "https://" in item
            or "|" in item
            or item.endswith(("\uff1a", ":"))
        ):
            return text
        items.append(_strip_trailing_list_punctuation(item))

    if len(items) < 2 or len(items) > 4 or any(not item for item in items):
        return text

    flattened = "\uff1b".join(items) + "\u3002"
    if prefix:
        prefix_label = prefix.rstrip("\uff1a: ")
        return f"{prefix_label}\uff1a{flattened}"
    return flattened


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
    response = _strip_decorative_markdown(response, re_mod=re_mod).strip()
    response = flatten_simple_chat_list(response, re_mod=re_mod).strip()

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
