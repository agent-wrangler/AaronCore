"""File target resolution and safety checks for post-LLM tool runtime."""

from pathlib import Path
import re


_SYSTEM_PROTECTED_PREFIXES = (
    "C:/Windows",
    "C:/Program Files",
    "C:/Program Files (x86)",
    "C:/ProgramData",
)
_AARONCORE_PROTECTED_ROOTS = (
    Path("brain"),
    Path("core"),
    Path("routes"),
    Path("shell"),
    Path("static/js"),
    Path("static/css"),
    Path("configs"),
)
_AARONCORE_PROTECTED_FILES = (
    Path("agent_final.py"),
    Path("output.html"),
    Path("start_nova.bat"),
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
)


def _project_root(project_root=None) -> Path:
    return Path(project_root) if project_root else Path(__file__).resolve().parents[2]


def _normalize_topic_stem(value: str) -> str:
    stem = Path(str(value or "")).stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{6}_", "", stem)
    return stem.strip().lower()


def resolve_user_file_target(
    file_path: str,
    *,
    normalize_user_special_path,
    load_export_state,
    project_root=None,
):
    raw = normalize_user_special_path(str(file_path or "").replace("\\", "/").strip())
    if not raw:
        return None

    root = _project_root(project_root)
    target = Path(raw)
    if target.is_absolute():
        return target.resolve()

    target = (root / raw.lstrip("./")).resolve()
    if "/" in raw or "\\" in raw:
        return target

    state = load_export_state()
    last_dir = normalize_user_special_path(str(state.get("last_export_dir") or "").strip())
    last_path = normalize_user_special_path(str(state.get("last_export_path") or "").strip())
    if not last_dir:
        return target

    last_dir_path = Path(last_dir)
    candidate = (last_dir_path / raw).resolve()
    raw_stem = _normalize_topic_stem(raw)
    last_stem = _normalize_topic_stem(last_path)
    same_topic = bool(
        raw_stem and last_stem and (raw_stem == last_stem or raw_stem in last_stem or last_stem in raw_stem)
    )
    if candidate.exists() or same_topic:
        return candidate
    return target


def is_allowed_user_target(target) -> bool:
    if not target:
        return False
    try:
        target_path = Path(target).resolve()
    except Exception:
        return False
    target_str = str(target_path).replace("\\", "/")
    return not any(target_str.startswith(prefix) for prefix in _SYSTEM_PROTECTED_PREFIXES)


def is_system_protected_target(target) -> bool:
    if not target:
        return True
    target_str = str(target).replace("\\", "/")
    return any(target_str.startswith(prefix) for prefix in _SYSTEM_PROTECTED_PREFIXES)


def is_aaroncore_protected_write_target(target, *, project_root=None) -> bool:
    if not target:
        return True
    try:
        root = _project_root(project_root).resolve()
        target_path = Path(target).resolve()
    except Exception:
        return True

    try:
        rel = target_path.relative_to(root)
    except Exception:
        return False

    if rel in _AARONCORE_PROTECTED_FILES:
        return True
    return any(rel == protected_root or protected_root in rel.parents for protected_root in _AARONCORE_PROTECTED_ROOTS)


def is_novacore_protected_write_target(target, *, project_root=None) -> bool:
    return is_aaroncore_protected_write_target(target, project_root=project_root)


def is_allowed_read_target(target) -> bool:
    if not target:
        return False
    try:
        return Path(target).exists() and not is_system_protected_target(target)
    except Exception:
        return False


def is_allowed_write_target(target, *, project_root=None) -> bool:
    if not target:
        return False
    return not is_system_protected_target(target) and not is_aaroncore_protected_write_target(
        target,
        project_root=project_root,
    )
