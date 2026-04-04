"""Self-fix runtime helpers for post-LLM repair tool calls."""

from pathlib import Path
import re


SAFE_FILE_PREFIXES = [
    "static/",
    "configs/",
    "tools/agent/",
    "skills/builtin/",
    "app_data/",
    "workers/",
    "state_data/",
]

PATH_FIXES = {
    "frontend/css/": "static/css/",
    "frontend/js/": "static/js/",
    "css/": "static/css/",
    "js/": "static/js/",
}


def normalize_file_hint(file_path: str) -> str:
    normalized = str(file_path or "").strip().replace("\\", "/").lstrip("./")
    for wrong, right in PATH_FIXES.items():
        if normalized.startswith(wrong):
            return normalized.replace(wrong, right, 1)
    return normalized


def _project_root(project_root=None) -> Path:
    return Path(project_root) if project_root else Path(__file__).resolve().parents[2]


def _match_target_by_filename(root: Path, file_path: str, allowed_prefixes: list[str]) -> tuple[Path | None, str | None, str | None]:
    filename = Path(file_path).name
    candidates = []
    for prefix in allowed_prefixes:
        prefix_dir = root / prefix
        if prefix_dir.exists():
            candidates.extend(prefix_dir.rglob(filename))
    if len(candidates) == 1:
        target = candidates[0]
        corrected = str(target.relative_to(root)).replace("\\", "/")
        return target, corrected, None
    if candidates:
        options = [str(item.relative_to(root)).replace("\\", "/") for item in candidates[:5]]
        return None, None, f"文件不存在： {file_path}\n找到类似文件：{', '.join(options)}"
    return None, None, f"文件不存在： {file_path}"


def _build_self_fix_prompt(file_path: str, problem: str, content: str, content_lines: list[str]) -> str:
    is_large_file = len(content_lines) > 300
    if is_large_file:
        preview_lines = [f"=== 文件前50行 ==="]
        preview_lines.extend(f"{index + 1}: {line}" for index, line in enumerate(content_lines[:50]))
        start_line = max(1, len(content_lines) - 49)
        preview_lines.append(f"\n=== 文件后50行（第{start_line}行起）===")
        preview_lines.extend(
            f"{start_line + index}: {line}" for index, line in enumerate(content_lines[-50:])
        )
        preview = "\n".join(preview_lines)
        return (
            f"你是代码修复专家。文件很大（{len(content_lines)}行），请用补丁方式修复。\n\n"
            f"文件: {file_path}\n"
            f"问题: {problem}\n\n"
            f"文件概览:\n{preview}\n\n"
            "请输出修复指令，严格使用以下格式（可以有多组）：\n\n"
            "===APPEND===\n"
            "（要追加到文件末尾的新代码）\n"
            "===END===\n\n"
            "或者：\n\n"
            "===FIND===\n"
            "（要替换的原始代码片段，必须能在文件中精确匹配）\n"
            "===REPLACE===\n"
            "（替换后的新代码）\n"
            "===END===\n\n"
            "要求：\n"
            "1. 只修复描述的问题\n"
            "2. 不要加解释，只输出修复指令\n"
            "3. 如果是添加新样式/功能，用 APPEND\n"
            "4. 如果是修改已有代码，用 FIND/REPLACE，FIND 内容必须精确匹配原文"
        )
    return (
        "你是代码修复专家。请修复以下文件中的问题。\n\n"
        f"文件: {file_path}\n"
        f"问题: {problem}\n\n"
        f"当前内容:\n```\n{content}\n```\n\n"
        "要求:\n"
        "1. 只修复描述的问题，不做其他改动\n"
        "2. 直接输出修复后的完整文件内容\n"
        "3. 不要加解释，不要加 markdown 标记\n"
        "4. 保持代码可运行"
    )


def _trim_markdown_fence(text: str) -> str:
    value = str(text or "").strip()
    if not value.startswith("```"):
        return value
    lines = value.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _apply_patch_style_output(content: str, llm_output: str) -> tuple[str, list[str]]:
    new_content = content
    applied = []
    for match in re.finditer(r"===APPEND===\s*\n(.*?)\n===END===", llm_output, re.DOTALL):
        append_code = match.group(1).strip()
        if append_code:
            new_content = new_content.rstrip() + "\n\n" + append_code + "\n"
            applied.append(f"追加 {len(append_code)} 字符")

    for match in re.finditer(r"===FIND===\s*\n(.*?)\n===REPLACE===\s*\n(.*?)\n===END===", llm_output, re.DOTALL):
        find_str = match.group(1).strip()
        replace_str = match.group(2).strip()
        if find_str and find_str in new_content:
            new_content = new_content.replace(find_str, replace_str, 1)
            applied.append(f"替换 '{find_str[:30]}...'")
        elif find_str:
            applied.append(f"未匹配 '{find_str[:30]}...'（跳过）")

    return new_content, applied


def execute_self_fix(
    arguments: dict,
    *,
    debug_write,
    llm_config,
    llm_call_stream,
    allowed_prefixes=None,
    project_root=None,
) -> dict:
    allowed_prefixes = list(allowed_prefixes or SAFE_FILE_PREFIXES)
    file_path = normalize_file_hint(arguments.get("file_path", ""))
    problem = str(arguments.get("problem", "") or arguments.get("fix_description", "") or "").strip()

    debug_write("self_fix_call", {"file_path": file_path, "problem": problem})

    if not file_path or not problem:
        return {
            "success": False,
            "response": f"缺少文件路径或问题描述。可修改的目录：{', '.join(allowed_prefixes)}",
        }

    if not any(file_path.startswith(prefix) for prefix in allowed_prefixes):
        return {
            "success": False,
            "response": f"安全限制：只能修改 {', '.join(allowed_prefixes)} 下的文件",
        }

    root = _project_root(project_root)
    target = root / file_path
    if not target.exists():
        matched_target, corrected_path, error_message = _match_target_by_filename(root, file_path, allowed_prefixes)
        if matched_target is None:
            return {"success": False, "response": error_message}
        target = matched_target
        file_path = corrected_path
        debug_write("self_fix_path_corrected", {"corrected_to": file_path})

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {"success": False, "response": f"读取失败: {exc}"}

    content_lines = content.split("\n")
    is_large_file = len(content_lines) > 300
    prompt = _build_self_fix_prompt(file_path, problem, content, content_lines)

    try:
        cfg = dict(llm_config)
        chunks = []
        for token in llm_call_stream(
            cfg,
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
            timeout=60,
        ):
            if isinstance(token, str):
                chunks.append(token)
        llm_output = _trim_markdown_fence("".join(chunks))
    except Exception as exc:
        return {"success": False, "response": f"LLM 调用失败: {type(exc).__name__}: {exc}"}

    if not llm_output or len(llm_output) < 5:
        return {"success": False, "response": "LLM 返回为空，修复失败"}

    if is_large_file:
        new_content, applied = _apply_patch_style_output(content, llm_output)
        if not applied:
            return {
                "success": False,
                "response": f"LLM 返回了修复指令但无法应用。原始输出：\n{llm_output[:500]}",
            }
        debug_write("self_fix_patch", {"applied": applied})
    else:
        new_content = llm_output
        if len(new_content) < len(content) * 0.5:
            return {"success": False, "response": "修复结果异常（内容大幅缩短），已拒绝"}

    try:
        backup_path = target.with_suffix(target.suffix + ".bak")
        backup_path.write_text(content, encoding="utf-8")
        target.write_text(new_content, encoding="utf-8")
    except Exception as exc:
        return {"success": False, "response": f"写入失败: {exc}"}

    debug_write(
        "self_fix",
        {"file": file_path, "problem": problem, "old_len": len(content), "new_len": len(new_content)},
    )
    return {
        "success": True,
        "response": f"已修复 {file_path}（备份: {backup_path.name}），刷新页面生效。",
    }
