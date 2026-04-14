import importlib.util
import json
from pathlib import Path

_REGISTRY_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _REGISTRY_DIR.parent
_STORE_PATH = _REPO_ROOT / "memory_db" / "skill_store.json"
_WORKFLOW_SKILLS_DIR = _REPO_ROOT / "skills" / "builtin"
_NATIVE_SKILL_DIRS = (
    _REPO_ROOT / "tools" / "agent",
    _WORKFLOW_SKILLS_DIR,
)
_skill_registry = {}

_VALID_CAPABILITY_KINDS = {
    "protocol_tool",
    "workflow_skill",
    "domain_skill",
    "memory_tool",
    "mcp_capability",
}
_VALID_SUBSTRATE_LAYERS = {
    "state",
    "protocol",
    "skill",
    "integration",
}
_VALID_EXPOSURE_SCOPES = {
    "tool_call",
    "tool_call_cod",
    "ui_catalog",
    "catalog_only",
}
_VALID_SURFACING_PROFILES = {
    "tool_only",
    "contextual",
    "manual_only",
}
_VALID_USER_VIEW_SCOPES = {
    "default",
    "advanced",
    "hidden",
}
_VALID_OPERATION_KINDS = {
    "inspect",
    "mutate",
    "execute",
    "interact",
    "configure",
    "query",
    "generate",
    "plan",
}
_VALID_EFFECT_LEVELS = {
    "read_only",
    "state_write",
    "local_write",
    "local_side_effect",
    "external_lookup",
}
_VALID_RISK_LEVELS = {
    "low",
    "medium",
    "high",
}
_VALID_TRUST_LEVELS = {
    "trusted_local",
    "trusted_state",
    "external_data",
    "remote_untrusted",
}

_PROTOCOL_TOOL_SKILLS = {
    "app_target",
    "computer_use",
    "draw",
    "file_copy",
    "file_delete",
    "file_move",
    "folder_explore",
    "model_config",
    "open_target",
    "run_code",
    "run_command",
    "save_export",
    "screen_capture",
    "ui_interaction",
    "write_file",
    "edit_file",
    "search_replace",
    "apply_unified_diff",
}
_WORKFLOW_SKILLS = {
    "article",
    "content_task",
    "development_flow",
    "task_plan",
}
_DOMAIN_SKILLS = {
    "news",
    "stock",
    "story",
    "weather",
}
_MEMORY_SKILLS = set()
_STATEFUL_SKILLS = {"task_plan"}
_PROTOCOL_FAMILY_BY_SKILL = {
    "app_target": "desktop",
    "computer_use": "desktop",
    "draw": "creative_output",
    "file_copy": "filesystem",
    "file_delete": "filesystem",
    "file_move": "filesystem",
    "folder_explore": "filesystem",
    "model_config": "runtime",
    "open_target": "target_resolution",
    "run_code": "shell",
    "run_command": "shell",
    "save_export": "filesystem",
    "screen_capture": "desktop",
    "ui_interaction": "desktop",
    "write_file": "filesystem",
    "edit_file": "filesystem",
    "search_replace": "filesystem",
    "apply_unified_diff": "filesystem",
    "article": "content_workflow",
    "content_task": "content_workflow",
    "development_flow": "planning",
    "task_plan": "planning",
    "news": "live_data",
    "stock": "live_data",
    "story": "creative_output",
    "weather": "live_data",
}


def _load_store() -> dict:
    if _STORE_PATH.exists():
        try:
            return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"native": {}, "mcp": {}}


def _save_store(store: dict):
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _coerce_string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _pick_first_string(*values, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _pick_first_dict(*values):
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def _infer_capability_kind(skill_name: str, meta: dict, source: str) -> str:
    raw_kind = _pick_first_string(
        meta.get("capability_kind"),
        meta.get("kind"),
    ).lower()
    if raw_kind in _VALID_CAPABILITY_KINDS:
        return raw_kind
    if source == "mcp":
        return "mcp_capability"
    if skill_name in _MEMORY_SKILLS:
        return "memory_tool"
    if skill_name in _PROTOCOL_TOOL_SKILLS:
        return "protocol_tool"
    if skill_name in _WORKFLOW_SKILLS:
        return "workflow_skill"
    if skill_name in _DOMAIN_SKILLS:
        return "domain_skill"
    category = _pick_first_string(meta.get("category")).lower()
    if "memory" in category:
        return "memory_tool"
    if "\u4efb\u52a1" in _pick_first_string(meta.get("category")):
        return "workflow_skill"
    return "domain_skill"


def _infer_substrate_layer(capability_kind: str, meta: dict) -> str:
    raw_layer = _pick_first_string(meta.get("substrate_layer")).lower()
    if raw_layer in _VALID_SUBSTRATE_LAYERS:
        return raw_layer
    if capability_kind == "memory_tool":
        return "state"
    if capability_kind == "protocol_tool":
        return "protocol"
    if capability_kind == "mcp_capability":
        return "integration"
    return "skill"


def _infer_protocol_family(skill_name: str, capability_kind: str, meta: dict) -> str:
    raw_family = _pick_first_string(meta.get("protocol_family")).lower()
    if raw_family:
        return raw_family
    if capability_kind == "mcp_capability":
        return "mcp"
    return _PROTOCOL_FAMILY_BY_SKILL.get(skill_name, "generic")


def _infer_exposure_scope(capability_kind: str, meta: dict) -> str:
    raw_scope = _pick_first_string(meta.get("exposure_scope")).lower()
    if raw_scope in _VALID_EXPOSURE_SCOPES:
        return raw_scope
    if capability_kind == "mcp_capability":
        return "ui_catalog"
    return "tool_call"


def _infer_stateful(skill_name: str, meta: dict) -> bool:
    raw = meta.get("stateful")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return skill_name in _STATEFUL_SKILLS


def _infer_surfacing_profile(capability_kind: str, exposure_scope: str, meta: dict) -> str:
    raw_profile = _pick_first_string(meta.get("surfacing_profile"), meta.get("discovery_profile")).lower()
    if raw_profile in _VALID_SURFACING_PROFILES:
        return raw_profile
    if exposure_scope == "catalog_only":
        return "manual_only"
    if capability_kind in {"workflow_skill", "domain_skill", "memory_tool"}:
        return "contextual"
    if capability_kind == "mcp_capability":
        return "manual_only"
    return "tool_only"


def _infer_discovery_tags(skill_name: str, meta: dict, *, capability_kind: str, protocol_family: str) -> list[str]:
    tags = []
    seen = set()

    def _add(value):
        text = str(value or "").strip().lower()
        if not text:
            return
        normalized = text.replace("/", "_").replace("\\", "_").replace(" ", "_")
        if normalized not in seen:
            seen.add(normalized)
            tags.append(normalized)

    _add(capability_kind)
    _add(protocol_family)
    _add(meta.get("category"))
    for value in _coerce_string_list(meta.get("keywords"))[:12]:
        _add(value)
    for value in _coerce_string_list(meta.get("anti_keywords"))[:6]:
        _add(f"anti:{value}")
    for key in (meta.get("parameters") or {}).get("properties", {}).keys():
        _add(f"arg:{key}")
    if "task" in skill_name or "plan" in skill_name:
        _add("planning")
    return tags


def _infer_operation_kind(skill_name: str, meta: dict, *, capability_kind: str, protocol_family: str) -> str:
    raw_kind = _pick_first_string(meta.get("operation_kind")).lower()
    if raw_kind in _VALID_OPERATION_KINDS:
        return raw_kind
    if capability_kind == "workflow_skill":
        return "plan"
    if capability_kind == "domain_skill":
        if protocol_family == "live_data":
            return "query"
        return "generate"
    if skill_name in {"folder_explore", "screen_capture"}:
        return "inspect"
    if skill_name in {"file_copy", "file_move", "file_delete", "save_export"}:
        return "mutate"
    if skill_name in {"open_target", "app_target"}:
        return "interact"
    if skill_name in {"ui_interaction"}:
        return "interact"
    if skill_name in {"run_code", "run_command", "computer_use"}:
        return "execute"
    if skill_name in {"model_config"}:
        return "configure"
    return "inspect"


def _infer_effect_level(skill_name: str, meta: dict, *, capability_kind: str, protocol_family: str, operation_kind: str) -> str:
    raw_level = _pick_first_string(meta.get("effect_level")).lower()
    if raw_level in _VALID_EFFECT_LEVELS:
        return raw_level
    if capability_kind == "workflow_skill":
        return "state_write"
    if capability_kind == "domain_skill":
        if protocol_family == "live_data":
            return "external_lookup"
        return "read_only"
    if operation_kind == "inspect":
        return "read_only"
    if skill_name in {"model_config"}:
        return "state_write"
    if skill_name in {"run_code", "run_command", "computer_use", "open_target", "app_target", "ui_interaction"}:
        return "local_side_effect"
    return "local_write"


def _infer_risk_level(skill_name: str, meta: dict, *, operation_kind: str, effect_level: str) -> str:
    raw_level = _pick_first_string(meta.get("risk_level")).lower()
    if raw_level in _VALID_RISK_LEVELS:
        return raw_level
    if skill_name in {"file_delete", "run_command", "run_code", "computer_use"}:
        return "high"
    if effect_level in {"local_side_effect", "local_write", "state_write"}:
        return "medium"
    if operation_kind in {"query", "inspect", "generate"}:
        return "low"
    return "medium"


def _infer_protocol_subfamily(skill_name: str, meta: dict, *, capability_kind: str, protocol_family: str, operation_kind: str) -> str:
    raw_value = _pick_first_string(meta.get("protocol_subfamily")).lower()
    if raw_value:
        return raw_value
    if capability_kind == "mcp_capability":
        return "mcp_remote"
    if capability_kind == "workflow_skill":
        if protocol_family == "planning":
            return "workflow_planning"
        return "workflow_orchestration"
    if capability_kind == "domain_skill":
        if protocol_family == "live_data":
            return "live_data_query"
        if protocol_family == "creative_output":
            return "creative_generation"
        return "content_generation"
    if protocol_family == "filesystem":
        if operation_kind == "inspect":
            return "filesystem_read"
        return "filesystem_write"
    if protocol_family == "desktop":
        if operation_kind == "inspect":
            return "desktop_perception"
        return "desktop_control"
    if protocol_family == "shell":
        return "shell_exec"
    if protocol_family == "runtime":
        return "runtime_config"
    if protocol_family == "target_resolution":
        return "target_resolution"
    if protocol_family == "content_workflow":
        return "workflow_content"
    return protocol_family or "generic"


def _infer_trust_level(source: str, meta: dict, *, effect_level: str) -> str:
    raw_value = _pick_first_string(meta.get("trust_level")).lower()
    if raw_value in _VALID_TRUST_LEVELS:
        return raw_value
    if source == "mcp":
        return "remote_untrusted"
    if effect_level == "state_write":
        return "trusted_state"
    if effect_level == "external_lookup":
        return "external_data"
    return "trusted_local"


def _infer_user_view_scope(source: str, meta: dict, *, capability_kind: str, surfacing_profile: str) -> str:
    raw_value = _pick_first_string(
        meta.get("user_view_scope"),
        meta.get("ui_view_scope"),
    ).lower()
    if raw_value in _VALID_USER_VIEW_SCOPES:
        return raw_value
    if surfacing_profile == "manual_only":
        return "advanced"
    if capability_kind in {"workflow_skill", "domain_skill"}:
        return "default"
    if source == "mcp":
        return "advanced"
    return "hidden"


def _normalize_selector_values(values, *, default: str) -> set[str]:
    if isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = [values]
    normalized = {
        part.strip().lower()
        for value in raw_values
        for part in str(value or "").split(",")
        if part.strip()
    }
    return normalized or {default}


def _normalize_exposure_scope_values(scope) -> set[str]:
    return _normalize_selector_values(scope, default="tool_call")


def _normalize_surfacing_profile_values(profile) -> set[str]:
    return _normalize_selector_values(profile, default="contextual")


def _normalize_user_view_scope_values(scope) -> set[str]:
    return _normalize_selector_values(scope, default="default")


def _skill_matches_exposure_scope(entry: dict, scope="tool_call") -> bool:
    if not isinstance(entry, dict):
        return False
    allowed_scopes = _normalize_exposure_scope_values(scope)
    entry_scope = str(entry.get("exposure_scope") or "tool_call").strip().lower() or "tool_call"
    return entry_scope in allowed_scopes


def _skill_matches_user_view_scope(entry: dict, scope="default") -> bool:
    if not isinstance(entry, dict):
        return False
    allowed_scopes = _normalize_user_view_scope_values(scope)
    entry_scope = str(entry.get("user_view_scope") or "hidden").strip().lower() or "hidden"
    return entry_scope in allowed_scopes


def _skill_store_payload(entry: dict) -> dict:
    payload = {
        "name": entry.get("name"),
        "keywords": entry.get("keywords") or [],
        "anti_keywords": entry.get("anti_keywords") or [],
        "description": entry.get("description") or "",
        "parameters": entry.get("parameters") if isinstance(entry.get("parameters"), dict) else None,
        "priority": entry.get("priority", 10),
        "category": entry.get("category", "\u901a\u7528"),
        "status": entry.get("status", "ready"),
        "enabled": bool(entry.get("enabled", True)),
        "source": entry.get("source", "native"),
        "capability_kind": entry.get("capability_kind", "domain_skill"),
        "substrate_layer": entry.get("substrate_layer", "skill"),
        "protocol_family": entry.get("protocol_family", "generic"),
        "exposure_scope": entry.get("exposure_scope", "tool_call"),
        "stateful": bool(entry.get("stateful", False)),
        "surfacing_profile": entry.get("surfacing_profile", "tool_only"),
        "discovery_tags": entry.get("discovery_tags") or [],
        "operation_kind": entry.get("operation_kind", "inspect"),
        "effect_level": entry.get("effect_level", "read_only"),
        "risk_level": entry.get("risk_level", "low"),
        "protocol_subfamily": entry.get("protocol_subfamily", "generic"),
        "trust_level": entry.get("trust_level", "trusted_local"),
        "user_view_scope": entry.get("user_view_scope", "hidden"),
    }
    metadata = entry.get("metadata")
    if isinstance(metadata, dict) and metadata:
        payload["metadata"] = metadata
    return payload


def _build_skill_entry(
    skill_name: str,
    *,
    meta: dict | None = None,
    enabled: bool = True,
    source: str = "native",
    execute=None,
    raw_info: dict | None = None,
) -> dict:
    raw_info = raw_info if isinstance(raw_info, dict) else {}
    metadata = {}
    if isinstance(meta, dict):
        metadata.update(meta)
    extra_meta = _pick_first_dict(raw_info.get("metadata"))
    if extra_meta:
        for key, value in extra_meta.items():
            metadata.setdefault(key, value)
    for key in (
        "name",
        "keywords",
        "trigger",
        "anti_keywords",
        "description",
        "parameters",
        "priority",
        "category",
        "capability_kind",
        "kind",
        "substrate_layer",
        "protocol_family",
        "exposure_scope",
        "stateful",
        "surfacing_profile",
        "discovery_profile",
        "discovery_tags",
        "operation_kind",
        "effect_level",
        "risk_level",
        "protocol_subfamily",
        "trust_level",
        "user_view_scope",
    ):
        if key in raw_info and key not in metadata:
            metadata[key] = raw_info.get(key)

    keywords = _coerce_string_list(metadata.get("keywords") or metadata.get("trigger"))
    anti_keywords = _coerce_string_list(metadata.get("anti_keywords"))
    capability_kind = _infer_capability_kind(skill_name, metadata, source)
    substrate_layer = _infer_substrate_layer(capability_kind, metadata)
    protocol_family = _infer_protocol_family(skill_name, capability_kind, metadata)
    exposure_scope = _infer_exposure_scope(capability_kind, metadata)
    stateful = _infer_stateful(skill_name, metadata)
    surfacing_profile = _infer_surfacing_profile(capability_kind, exposure_scope, metadata)
    user_view_scope = _infer_user_view_scope(
        source,
        metadata,
        capability_kind=capability_kind,
        surfacing_profile=surfacing_profile,
    )
    operation_kind = _infer_operation_kind(
        skill_name,
        metadata,
        capability_kind=capability_kind,
        protocol_family=protocol_family,
    )
    effect_level = _infer_effect_level(
        skill_name,
        metadata,
        capability_kind=capability_kind,
        protocol_family=protocol_family,
        operation_kind=operation_kind,
    )
    risk_level = _infer_risk_level(
        skill_name,
        metadata,
        operation_kind=operation_kind,
        effect_level=effect_level,
    )
    protocol_subfamily = _infer_protocol_subfamily(
        skill_name,
        metadata,
        capability_kind=capability_kind,
        protocol_family=protocol_family,
        operation_kind=operation_kind,
    )
    trust_level = _infer_trust_level(
        source,
        metadata,
        effect_level=effect_level,
    )
    discovery_tags = _infer_discovery_tags(
        skill_name,
        metadata,
        capability_kind=capability_kind,
        protocol_family=protocol_family,
    )
    status = "ready" if enabled else "disabled"

    return {
        "name": _pick_first_string(metadata.get("name"), raw_info.get("name"), skill_name),
        "keywords": keywords,
        "trigger": list(keywords),
        "catalog_keywords": list(keywords),
        "anti_keywords": anti_keywords,
        "catalog_anti_keywords": list(anti_keywords),
        "description": _pick_first_string(metadata.get("description"), raw_info.get("description")),
        "parameters": _pick_first_dict(metadata.get("parameters"), raw_info.get("parameters")),
        "priority": int(metadata.get("priority", raw_info.get("priority", 10)) or 10),
        "category": _pick_first_string(
            metadata.get("category"),
            raw_info.get("category"),
            default="\u901a\u7528",
        ),
        "status": status,
        "enabled": enabled,
        "source": source,
        "capability_kind": capability_kind,
        "substrate_layer": substrate_layer,
        "protocol_family": protocol_family,
        "exposure_scope": exposure_scope,
        "stateful": stateful,
        "surfacing_profile": surfacing_profile,
        "discovery_tags": discovery_tags,
        "operation_kind": operation_kind,
        "effect_level": effect_level,
        "risk_level": risk_level,
        "protocol_subfamily": protocol_subfamily,
        "trust_level": trust_level,
        "user_view_scope": user_view_scope,
        "execute": execute if callable(execute) else raw_info.get("execute"),
        "metadata": metadata,
    }


def load_skill_metadata(skill_path):
    json_path = skill_path.with_suffix(".json")
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[Skills] Failed to load metadata {json_path.name}: {exc}")
    return {}


def _iter_native_skill_files():
    seen = set()
    for skill_dir in _NATIVE_SKILL_DIRS:
        if not skill_dir.exists():
            continue
        for skill_path in sorted(skill_dir.iterdir()):
            if not skill_path.is_file() or skill_path.suffix != ".py" or skill_path.name.startswith("_"):
                continue
            skill_name = skill_path.stem
            if skill_name in seen:
                continue
            seen.add(skill_name)
            yield skill_name, skill_path


def load_skills():
    _skill_registry.clear()
    store = _load_store()
    native = store.get("native", {})

    for skill_name, skill_path in _iter_native_skill_files():
        meta = load_skill_metadata(Path(skill_path))
        try:
            spec = importlib.util.spec_from_file_location(f"native_skill_{skill_name}", skill_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            exec_func = getattr(module, "execute", None) or getattr(module, "run", None)
            if not callable(exec_func):
                print(f"[Skills] Skipped {skill_name}: no execute/run function")
                continue

            enabled = bool(native.get(skill_name, {}).get("enabled", True))
            _skill_registry[skill_name] = _build_skill_entry(
                skill_name,
                meta=meta,
                enabled=enabled,
                source="native",
                execute=exec_func,
            )
            print(f"[Skills] Loaded: {skill_name}" + ("" if enabled else " (disabled)"))
        except Exception as exc:
            print(f"[Skills] Failed to load {skill_name}: {exc}")

    for skill_id, info in store.get("mcp", {}).items():
        if skill_id in _skill_registry:
            continue
        enabled = bool(info.get("enabled", True)) if isinstance(info, dict) else True
        _skill_registry[skill_id] = _build_skill_entry(
            skill_id,
            enabled=enabled,
            source="mcp",
            raw_info=info if isinstance(info, dict) else {},
        )

    return _skill_registry


def get_skill(name):
    if not _skill_registry:
        load_skills()
    skill = _skill_registry.get(name)
    if skill and skill.get("status") == "disabled":
        return None
    return skill


def get_all_skills():
    if not _skill_registry:
        load_skills()
    return {key: value for key, value in _skill_registry.items() if value.get("status") != "disabled"}


def get_exposed_skills(scope="tool_call"):
    if not _skill_registry:
        load_skills()
    return {
        key: value
        for key, value in _skill_registry.items()
        if value.get("status") != "disabled" and _skill_matches_exposure_scope(value, scope)
    }


def get_surfaced_skills(profile="contextual"):
    if not _skill_registry:
        load_skills()
    profiles = _normalize_surfacing_profile_values(profile)
    return {
        key: value
        for key, value in _skill_registry.items()
        if value.get("status") != "disabled"
        and str(value.get("surfacing_profile") or "tool_only").strip().lower() in profiles
    }


def get_user_visible_skills(scope="default") -> dict:
    if not _skill_registry:
        load_skills()
    return {
        key: value
        for key, value in _skill_registry.items()
        if value.get("status") != "disabled" and _skill_matches_user_view_scope(value, scope)
    }


def _entry_view(entry: dict, *, include_fields: tuple[str, ...]) -> dict:
    return {field: entry.get(field) for field in include_fields if field in entry}


def get_tool_view(scope="tool_call") -> dict:
    fields = (
        "name",
        "description",
        "parameters",
        "source",
        "capability_kind",
        "substrate_layer",
        "protocol_family",
        "protocol_subfamily",
        "exposure_scope",
        "operation_kind",
        "effect_level",
        "risk_level",
        "trust_level",
    )
    return {
        key: _entry_view(value, include_fields=fields)
        for key, value in get_exposed_skills(scope).items()
    }


def get_surfacing_view(profile="contextual") -> dict:
    fields = (
        "name",
        "description",
        "priority",
        "category",
        "source",
        "capability_kind",
        "protocol_family",
        "protocol_subfamily",
        "surfacing_profile",
        "discovery_tags",
        "operation_kind",
        "effect_level",
        "risk_level",
        "trust_level",
    )
    return {
        key: _entry_view(value, include_fields=fields)
        for key, value in get_surfaced_skills(profile).items()
    }


def get_user_view(scope="default") -> dict:
    fields = (
        "name",
        "description",
        "priority",
        "category",
        "status",
        "enabled",
        "source",
        "capability_kind",
        "substrate_layer",
        "protocol_family",
        "protocol_subfamily",
        "surfacing_profile",
        "stateful",
        "operation_kind",
        "effect_level",
        "risk_level",
        "trust_level",
        "user_view_scope",
    )
    return {
        key: _entry_view(value, include_fields=fields)
        for key, value in get_user_visible_skills(scope).items()
    }


def get_skill_catalog_summary() -> dict:
    if not _skill_registry:
        load_skills()
    summary = {
        "total": 0,
        "enabled": 0,
        "by_kind": {},
        "by_layer": {},
        "by_exposure_scope": {},
        "by_surfacing_profile": {},
        "by_operation_kind": {},
        "by_effect_level": {},
        "by_risk_level": {},
        "by_protocol_subfamily": {},
        "by_trust_level": {},
        "by_user_view_scope": {},
    }
    for name, info in _skill_registry.items():
        if not isinstance(info, dict):
            continue
        summary["total"] += 1
        if info.get("status") != "disabled":
            summary["enabled"] += 1
        kind = str(info.get("capability_kind") or "unknown")
        layer = str(info.get("substrate_layer") or "unknown")
        scope = str(info.get("exposure_scope") or "unknown")
        profile = str(info.get("surfacing_profile") or "unknown")
        operation = str(info.get("operation_kind") or "unknown")
        effect = str(info.get("effect_level") or "unknown")
        risk = str(info.get("risk_level") or "unknown")
        subfamily = str(info.get("protocol_subfamily") or "unknown")
        trust = str(info.get("trust_level") or "unknown")
        user_scope = str(info.get("user_view_scope") or "unknown")
        summary["by_kind"][kind] = summary["by_kind"].get(kind, 0) + 1
        summary["by_layer"][layer] = summary["by_layer"].get(layer, 0) + 1
        summary["by_exposure_scope"][scope] = summary["by_exposure_scope"].get(scope, 0) + 1
        summary["by_surfacing_profile"][profile] = summary["by_surfacing_profile"].get(profile, 0) + 1
        summary["by_operation_kind"][operation] = summary["by_operation_kind"].get(operation, 0) + 1
        summary["by_effect_level"][effect] = summary["by_effect_level"].get(effect, 0) + 1
        summary["by_risk_level"][risk] = summary["by_risk_level"].get(risk, 0) + 1
        summary["by_protocol_subfamily"][subfamily] = summary["by_protocol_subfamily"].get(subfamily, 0) + 1
        summary["by_trust_level"][trust] = summary["by_trust_level"].get(trust, 0) + 1
        summary["by_user_view_scope"][user_scope] = summary["by_user_view_scope"].get(user_scope, 0) + 1
    return summary


def get_all_skills_for_ui():
    if not _skill_registry:
        load_skills()
    return _skill_registry


def set_skill_enabled(name: str, enabled: bool) -> bool:
    if not _skill_registry:
        load_skills()
    skill = _skill_registry.get(name)
    if not skill:
        return False

    skill["enabled"] = enabled
    skill["status"] = "ready" if enabled else "disabled"

    store = _load_store()
    section = store.setdefault(skill.get("source", "native"), {})
    current = section.get(name, {}) if isinstance(section.get(name), dict) else {}
    current["enabled"] = enabled
    if skill.get("source") == "mcp":
        current.update(_skill_store_payload(skill))
    section[name] = current
    _save_store(store)
    return True


def register_mcp_skill(skill_id: str, skill_info: dict):
    if not _skill_registry:
        load_skills()
    entry = _build_skill_entry(
        skill_id,
        enabled=bool(skill_info.get("enabled", True)) if isinstance(skill_info, dict) else True,
        source="mcp",
        raw_info=skill_info if isinstance(skill_info, dict) else {},
    )
    _skill_registry[skill_id] = entry

    store = _load_store()
    mcp = store.setdefault("mcp", {})
    mcp[skill_id] = _skill_store_payload(entry)
    _save_store(store)


def unregister_mcp_skill(skill_id: str):
    _skill_registry.pop(skill_id, None)
    store = _load_store()
    store.get("mcp", {}).pop(skill_id, None)
    _save_store(store)


def execute_skill(skill_name, user_input):
    skill = get_skill(skill_name)
    if skill and callable(skill.get("execute")):
        try:
            return skill["execute"](user_input)
        except Exception as exc:
            return f"\u6267\u884c\u5931\u8d25: {str(exc)[:50]}"
    return None


load_skills()
