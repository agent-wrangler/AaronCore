import json


def split_system_and_messages(messages: list) -> tuple:
    system_text = ""
    chat_messages = []
    for message in messages:
        if message.get("role") == "system":
            system_text += str(message.get("content", "")) + "\n"
        else:
            chat_messages.append(message)
    return system_text.strip(), chat_messages


def normalize_openai_messages(messages: list) -> list:
    normalized = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "") or "").strip()
        content = message.get("content", "")
        tool_calls = message.get("tool_calls") if isinstance(message.get("tool_calls"), list) else None
        if role == "nova":
            role = "assistant"
        if role not in ("system", "user", "assistant", "tool"):
            continue
        if role != "tool":
            if content is None and not (role == "assistant" and tool_calls):
                continue
            if content is None:
                content = ""
            else:
                content = str(content)
            if not content.strip() and not (role == "assistant" and tool_calls):
                continue
        item = dict(message)
        item["role"] = role
        if role != "tool":
            item["content"] = content
        if (
            normalized
            and normalized[-1].get("role") == role
            and role in ("system", "user", "assistant")
            and not normalized[-1].get("tool_calls")
            and not tool_calls
        ):
            normalized[-1]["content"] = str(normalized[-1].get("content", "")) + "\n" + str(item.get("content", ""))
        else:
            normalized.append(item)
    return normalized


def normalize_reasoning_details(value) -> list[dict]:
    if isinstance(value, str):
        value = [{"type": "reasoning.text", "index": 0, "text": value}]
    elif isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []

    normalized = []
    for idx, item in enumerate(value):
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
        text = item.get("text") or item.get("content") or item.get("thinking") or item.get("reasoning") or ""
        text = str(text or "")
        if not text.strip():
            continue
        detail = dict(item)
        detail["text"] = text
        detail.setdefault("type", "reasoning.text")
        detail.setdefault("index", idx)
        normalized.append(detail)
    return normalized


def convert_messages_for_anthropic(messages: list) -> list:
    result = []
    for message in messages:
        role = message.get("role", "user")
        if role not in ("user", "assistant"):
            role = "user"
        content = message.get("content", "")
        if isinstance(content, str):
            result.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            result.append({"role": role, "content": "\n".join(text_parts) if text_parts else ""})
        else:
            result.append({"role": role, "content": str(content)})
    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": "."})

    merged = []
    for message in result:
        if merged and merged[-1]["role"] == message["role"]:
            merged[-1]["content"] += "\n" + message["content"]
        else:
            merged.append(message)
    return merged


def convert_messages_for_anthropic_tools(messages: list) -> list:
    def text_block(text: str) -> dict:
        return {"type": "text", "text": str(text or "")}

    def content_to_blocks(content) -> list:
        if isinstance(content, list):
            blocks = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        blocks.append({"type": "text", "text": str(item.get("text", ""))})
                    elif item.get("type") in ("tool_use", "tool_result"):
                        blocks.append(dict(item))
            return blocks
        if content is None:
            return []
        return [text_block(content)]

    result = []
    for message in messages:
        role = str(message.get("role", "user") or "user")
        if role == "tool":
            result.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": str(message.get("tool_call_id", "") or ""),
                            "content": str(message.get("content", "") or ""),
                        }
                    ],
                }
            )
            continue

        if role not in ("user", "assistant"):
            role = "user"

        if role == "assistant" and message.get("tool_calls"):
            blocks = content_to_blocks(message.get("content"))
            for tool_call in message.get("tool_calls") or []:
                function = tool_call.get("function") or {}
                raw_args = function.get("arguments", "{}")
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
                except Exception:
                    parsed_args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(tool_call.get("id", "") or f"toolu_{len(blocks)}"),
                        "name": str(function.get("name", "") or ""),
                        "input": parsed_args if isinstance(parsed_args, dict) else {},
                    }
                )
            result.append({"role": "assistant", "content": blocks})
            continue

        result.append({"role": role, "content": content_to_blocks(message.get("content"))})

    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": [text_block(".")]})

    merged = []
    for message in result:
        if merged and merged[-1]["role"] == message["role"]:
            merged[-1]["content"].extend(message["content"])
        else:
            merged.append({"role": message["role"], "content": list(message["content"])})
    return merged


def convert_tools_for_anthropic(tools: list | None) -> list | None:
    if not tools:
        return None
    converted = []
    for tool in tools:
        function = (tool or {}).get("function") or {}
        if not function.get("name"):
            continue
        converted.append(
            {
                "name": function.get("name"),
                "description": function.get("description", ""),
                "input_schema": function.get("parameters") or {"type": "object", "properties": {}, "required": []},
            }
        )
    return converted or None


def anthropic_blocks_to_tool_calls(content_blocks: list) -> list:
    tool_calls = []
    for block in content_blocks or []:
        if str(block.get("type", "")) != "tool_use":
            continue
        tool_calls.append(
            {
                "id": str(block.get("id", "") or ""),
                "type": "function",
                "function": {
                    "name": str(block.get("name", "") or ""),
                    "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                },
            }
        )
    return tool_calls
