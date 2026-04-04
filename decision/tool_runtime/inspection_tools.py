"""Inspection-oriented runtime helpers for post-LLM tool calls."""

from pathlib import Path


_PATH_FIXES = {
    "frontend/css/": "static/css/",
    "frontend/js/": "static/js/",
    "css/": "static/css/",
    "js/": "static/js/",
}
_SPECIAL_USER_DIRS = ("Desktop", "Documents", "Downloads")
_BROWSER_HINTS = [
    "chrome",
    "edge",
    "firefox",
    "brave",
    "opera",
    "safari",
    "\u6d4f\u89c8\u5668",
]


def _project_root(project_root=None) -> Path:
    return Path(project_root) if project_root else Path(__file__).resolve().parents[2]


def _normalize_file_hint(raw_path: str) -> str:
    path = str(raw_path or "").strip().replace("\\", "/").lstrip("./")
    for wrong, right in _PATH_FIXES.items():
        if path.startswith(wrong):
            return path.replace(wrong, right, 1)
    return path


def execute_read_file(
    arguments: dict,
    *,
    allowed_prefixes,
    resolve_user_file_target,
    is_allowed_user_target,
    debug_write,
    project_root=None,
) -> dict:
    root = _project_root(project_root)
    file_path = _normalize_file_hint(arguments.get("file_path", ""))

    if not file_path:
        return {
            "success": False,
            "response": (
                f"\u8bf7\u63d0\u4f9b\u6587\u4ef6\u8def\u5f84\u3002"
                f"\u53ef\u8bfb\u53d6\u7684\u76ee\u5f55\uff1a{', '.join(allowed_prefixes)}"
            ),
        }

    target = resolve_user_file_target(file_path)
    if not target:
        return {
            "success": False,
            "response": (
                f"\u8bf7\u63d0\u4f9b\u6587\u4ef6\u8def\u5f84\u3002"
                f"\u53ef\u8bfb\u53d6\u7684\u76ee\u5f55\uff1a{', '.join(allowed_prefixes)}"
            ),
        }

    if not target.exists():
        filename = Path(file_path).name
        candidates = []
        for prefix in allowed_prefixes:
            prefix_dir = root / prefix
            if prefix_dir.exists():
                candidates.extend(prefix_dir.rglob(filename))
        if len(candidates) == 1:
            target = candidates[0]
            file_path = str(target.relative_to(root)).replace("\\", "/")
        elif candidates:
            options = [str(item.relative_to(root)).replace("\\", "/") for item in candidates[:5]]
            return {
                "success": False,
                "response": (
                    f"\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a {file_path}\n"
                    f"\u627e\u5230\u7c7b\u4f3c\u6587\u4ef6\uff1a{', '.join(options)}"
                ),
            }
        else:
            return {"success": False, "response": f"\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a {file_path}"}

    if not is_allowed_user_target(target):
        return {
            "success": False,
            "response": (
                "\u5b89\u5168\u9650\u5236\uff1a"
                "\u53ea\u80fd\u8bfb\u53d6\u5de5\u4f5c\u533a\u3001\u684c\u9762\u3001"
                "\u6587\u6863\u6216\u4e0b\u8f7d\u76ee\u5f55\u4e2d\u7684\u6587\u4ef6"
            ),
        }

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {"success": False, "response": f"\u8bfb\u53d6\u5931\u8d25: {exc}"}

    lines = content.split("\n")
    total = len(lines)
    if total > 200:
        content = "\n".join(lines[:200])
        content += f"\n\n... (\u5171{total} \u884c\uff0c\u5df2\u622a\u65ad\u524d 200 \u884c)"

    debug_write("read_file", {"file": file_path, "lines": total})
    return {
        "success": True,
        "response": f"\u300a{file_path}\u300b {total} \u884c\n{content}",
    }


def execute_list_files_v3(
    arguments: dict,
    *,
    resolve_user_file_target,
    normalize_user_special_path,
    is_allowed_user_target,
    project_root=None,
) -> dict:
    root = _project_root(project_root)
    raw_directory = str(arguments.get("directory", "")).strip()
    normalized = normalize_user_special_path(raw_directory).replace("\\", "/").strip().rstrip("/")
    directory = normalized.lstrip("./")

    if not directory:
        lines = ["\u53ef\u8bbf\u95ee\u7684\u76ee\u5f55\uff1a", f"\n\U0001F4C1 {root}"]
        root_dirs = sorted([item.name + "/" for item in root.iterdir() if item.is_dir()])
        root_files = sorted([item.name for item in root.iterdir() if item.is_file()])
        for directory_name in root_dirs:
            lines.append(f"  \U0001F4C1 {directory_name}")
        for file_name in root_files:
            lines.append(f"  \U0001F4C4 {file_name}")
        for special_name in _SPECIAL_USER_DIRS:
            special_dir = Path.home() / special_name
            if special_dir.exists():
                lines.append(f"\n\U0001F4C1 {special_dir}")
        return {"success": True, "response": "\n".join(lines)}

    target = resolve_user_file_target(directory)
    if target is None:
        target = root / directory

    if not is_allowed_user_target(target):
        return {
            "success": False,
            "response": (
                "\u5b89\u5168\u9650\u5236\uff1a"
                "\u53ea\u80fd\u6d4f\u89c8\u5de5\u4f5c\u533a\u3001\u684c\u9762\u3001"
                "\u6587\u6863\u6216\u4e0b\u8f7d\u76ee\u5f55\u4e2d\u7684\u6587\u4ef6\u5939"
            ),
        }

    if not target.exists() or not target.is_dir():
        return {
            "success": False,
            "response": f"\u76ee\u5f55\u4e0d\u5b58\u5728\uff1a {raw_directory or directory}",
        }

    files = sorted([item.name for item in target.iterdir() if item.is_file()])
    dirs = sorted([item.name + "/" for item in target.iterdir() if item.is_dir()])
    display_dir = str(target).replace("\\", "/")
    lines = [f"\U0001F4C1 {display_dir}/"]
    for directory_name in dirs:
        lines.append(f"  \U0001F4C1 {directory_name}")
    for file_name in files:
        lines.append(f"  \U0001F4C4 {file_name}")
    return {"success": True, "response": "\n".join(lines)}


def execute_discover_tools(arguments: dict, *, debug_write, get_all_skills) -> dict:
    intent = str(arguments.get("intent", "")).strip()
    debug_write("discover_tools", {"intent": intent})
    try:
        all_skills = get_all_skills()
    except Exception:
        return {"success": False, "error": "\u6280\u80fd\u7cfb\u7edf\u672a\u5c31\u7eea"}
    if not all_skills:
        return {
            "success": True,
            "response": "\u5f53\u524d\u6ca1\u6709\u5df2\u6ce8\u518c\u7684\u6280\u80fd\u5de5\u5177\u3002",
        }

    lines = ["\u4ee5\u4e0b\u662f\u5f53\u524d\u53ef\u7528\u7684\u6280\u80fd\u5de5\u5177\uff1a"]
    for name, info in all_skills.items():
        if not info or not callable(info.get("execute")):
            continue
        desc = str(info.get("description") or info.get("name") or name).strip()
        lines.append(f"- {name}\uff1a{desc}")
    lines.append(
        "\n\u8bf7\u6839\u636e\u7528\u6237\u610f\u56fe\u9009\u62e9\u5408\u9002\u7684\u5de5\u5177\uff0c"
        "\u7528 tool_call \u8c03\u7528\u5b83\u3002"
    )
    return {"success": True, "response": "\n".join(lines)}


def execute_sense_environment(arguments: dict, *, debug_write, get_vision_context=None) -> dict:
    detail_level = str(arguments.get("detail_level", "basic")).strip().lower()
    if detail_level in {"high", "full", "detailed", "detail"}:
        detail_level = "full"
    else:
        detail_level = "basic"
    debug_write("sense_environment", {"detail_level": detail_level})

    lines = []
    active_title = ""
    try:
        import pygetwindow as gw

        active = gw.getActiveWindow()
        if active and getattr(active, "title", None):
            active_title = str(active.title).strip()
    except Exception:
        pass
    unknown_window_label = "\u672a\u77e5"
    lines.append(f"\u5f53\u524d\u6d3b\u8dc3\u7a97\u53e3\uff1a{active_title or unknown_window_label}")

    is_browser = any(hint in active_title.lower() for hint in _BROWSER_HINTS) if active_title else False
    browser_label = "\u6d4f\u89c8\u5668"
    desktop_label = "\u684c\u9762\u5e94\u7528"
    lines.append(f"\u7a97\u53e3\u7c7b\u578b\uff1a{browser_label if is_browser else desktop_label}")

    try:
        import pygetwindow as gw

        all_windows = [window.title for window in gw.getAllWindows() if window.title.strip()]
        lines.append(f"\u5df2\u6253\u5f00\u7a97\u53e3\uff08{len(all_windows)}\u4e2a\uff09\uff1a")
        for window_title in all_windows[:15]:
            lines.append(f"  - {window_title}")
        if len(all_windows) > 15:
            lines.append(f"  ...\u8fd8\u6709 {len(all_windows) - 15} \u4e2a\u7a97\u53e3")
    except Exception:
        lines.append("\u7a97\u53e3\u5217\u8868\uff1a\u83b7\u53d6\u5931\u8d25")

    if detail_level == "full":
        try:
            import pyautogui

            screen_size = pyautogui.size()
            mouse_pos = pyautogui.position()
            lines.append(
                f"\u5c4f\u5e55\u5206\u8fa8\u7387\uff1a{screen_size.width}x{screen_size.height}"
            )
            lines.append(f"\u9f20\u6807\u4f4d\u7f6e\uff1a({mouse_pos.x}, {mouse_pos.y})")
        except Exception:
            pass

        if is_browser and callable(get_vision_context):
            try:
                vision_context = get_vision_context()
                if vision_context.get("description"):
                    lines.append(f"\u89c6\u89c9\u611f\u77e5\uff1a{vision_context['description']}")
            except Exception:
                pass

    return {"success": True, "response": "\n".join(lines)}
