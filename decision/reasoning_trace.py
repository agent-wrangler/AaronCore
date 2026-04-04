"""Assistant reasoning-detail normalization helpers."""


def normalize_reasoning_details(reasoning_details) -> list[dict]:
    if isinstance(reasoning_details, str):
        reasoning_details = [{"type": "reasoning.text", "index": 0, "text": reasoning_details}]
    elif isinstance(reasoning_details, dict):
        reasoning_details = [reasoning_details]
    if not isinstance(reasoning_details, list):
        return []

    normalized = []
    for idx, item in enumerate(reasoning_details):
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            normalized.append(
                {
                    "type": "reasoning.text",
                    "index": idx,
                    "text": text,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or item.get("thinking") or item.get("reasoning") or "")
        if not text.strip():
            continue
        detail = dict(item)
        detail["text"] = text
        detail.setdefault("type", "reasoning.text")
        detail.setdefault("index", idx)
        normalized.append(detail)
    return normalized


def reasoning_details_from_chunks(chunks: list[str]) -> list[dict]:
    text = "".join(str(chunk or "") for chunk in chunks).strip()
    if not text:
        return []
    return [{"type": "reasoning.text", "index": 0, "text": text}]


def build_assistant_history_message(
    content,
    *,
    tool_calls: list[dict] | None = None,
    reasoning_details=None,
    normalize_reasoning_details,
) -> dict:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    normalized_reasoning = normalize_reasoning_details(reasoning_details)
    if normalized_reasoning:
        message["reasoning_details"] = normalized_reasoning
    return message
