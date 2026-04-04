import ast
import json
import re


LEGACY_TOOL_MARKUP_RE = re.compile(r'<\s*(?:invoke|function_calls|minimax:tool_call|tool_call)|DSML|\[\s*TOOL_CALL\s*\]', re.I)
LEGACY_TOOL_BLOCK_RE = re.compile(r'\[\s*TOOL_CALL\s*\](.*?)\[\s*/\s*TOOL_CALL\s*\]', re.I | re.S)
LEGACY_MINIMAX_TOOL_RE = re.compile(r'<\s*minimax:tool_call\s*>(.*?)<\s*/\s*minimax:tool_call\s*>', re.I | re.S)
LEGACY_JSON_TOOL_RE = re.compile(r'<\s*tool_call\s*>(.*?)<\s*/\s*tool_call\s*>', re.I | re.S)


def extract_json_object_text(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def salvage_string_field(raw: str, key: str) -> str:
    text = str(raw or "")
    patterns = [
        rf'"{key}"\s*:\s*"((?:\\.|[^"\\])*)"',
        rf"'{key}'\s*:\s*'((?:\\.|[^'\\])*)'",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.S)
        if not match:
            continue
        value = match.group(1)
        try:
            return bytes(value, "utf-8").decode("unicode_escape")
        except Exception:
            return value
    return ""


def coerce_tool_args(raw_args, user_input: str = "") -> dict:
    args = {}
    if isinstance(raw_args, dict):
        args = dict(raw_args)
    else:
        raw = str(raw_args or "").strip()
        if raw:
            candidates = [raw]
            object_text = extract_json_object_text(raw)
            if object_text and object_text not in candidates:
                candidates.append(object_text)
            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        args = parsed
                        break
                except Exception:
                    try:
                        parsed = ast.literal_eval(candidate)
                        if isinstance(parsed, dict):
                            args = parsed
                            break
                    except Exception:
                        continue
            if not args:
                for key in (
                    "file_path",
                    "path",
                    "target",
                    "filename",
                    "content",
                    "description",
                    "change_request",
                    "instructions",
                    "problem",
                    "query",
                    "topic",
                ):
                    value = salvage_string_field(raw, key)
                    if value:
                        args[key] = value

    for nested_key in ("parameters", "args"):
        nested = args.get(nested_key)
        if isinstance(nested, dict):
            merged = dict(nested)
            if "user_input" in args and "user_input" not in merged:
                merged["user_input"] = args["user_input"]
            args = merged

    if user_input and "user_input" not in args:
        args["user_input"] = user_input
    return args


def sanitize_tool_call_payload(tc: dict, tool_args: dict) -> dict:
    clean_tc = dict(tc or {})
    function = dict(clean_tc.get("function") or {})
    function["arguments"] = json.dumps(tool_args or {}, ensure_ascii=False)
    clean_tc["function"] = function
    return clean_tc


def contains_legacy_tool_markup(text: str) -> bool:
    return bool(LEGACY_TOOL_MARKUP_RE.search(str(text or "")))


def parse_legacy_tool_call_text(text: str, user_input: str = "") -> dict | None:
    raw = str(text or "")
    blocks = []
    blocks.extend(LEGACY_TOOL_BLOCK_RE.findall(raw))
    blocks.extend(LEGACY_MINIMAX_TOOL_RE.findall(raw))
    blocks.extend(LEGACY_JSON_TOOL_RE.findall(raw))
    if not blocks and raw.strip().startswith("{"):
        blocks = [raw]
    for block in blocks:
        args = coerce_tool_args(block, user_input=user_input)
        tool_name = str(args.pop("tool_name", "") or args.pop("name", "") or "").strip()
        if not tool_name:
            continue
        return {
            "id": "legacy_tool_call_0",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(args or {}, ensure_ascii=False),
            },
        }
    return None
