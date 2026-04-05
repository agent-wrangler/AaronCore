"""技能商店路由：技能列表、启用/禁用、MCP 管理"""
import os
import re
import subprocess
import tomllib
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from core import shared as S
from core.markdown_render import render_markdown_html

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

router = APIRouter()

def _read_text_fallback(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_yaml(path: Path) -> dict:
    if not path.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(_read_text_fallback(path)) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _split_skill_markdown(text: str) -> tuple[dict, str]:
    text = str(text or "")
    if text.startswith("---"):
        match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", text, re.S)
        if match:
            front_matter = {}
            if yaml is not None:
                try:
                    front_matter = yaml.safe_load(match.group(1)) or {}
                    if not isinstance(front_matter, dict):
                        front_matter = {}
                except Exception:
                    front_matter = {}
            return front_matter, match.group(2).strip()
    return {}, text.strip()


def _strip_leading_h1(markdown_text: str) -> str:
    lines = str(markdown_text or "").splitlines()
    if lines and re.match(r"^\s*#\s+", lines[0]):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def _first_markdown_paragraph(markdown_text: str) -> str:
    text = _strip_leading_h1(markdown_text)
    parts = re.split(r"\r?\n\s*\r?\n", text, maxsplit=1)
    return (parts[0] if parts else text).strip()


def _normalize_skill_path(value) -> str:
    if not value:
        return ""
    try:
        path = Path(str(value)).expanduser()
        if path.exists():
            path = path.resolve()
        return path.as_posix().lower()
    except Exception:
        return str(value).strip().replace("\\", "/").lower()


def _load_disabled_skill_paths() -> set[str]:
    if not _CODEX_CONFIG_PATH.exists():
        return set()
    try:
        data = tomllib.loads(_CODEX_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    entries = ((data.get("skills") or {}).get("config") or [])
    disabled = set()
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("enabled", True) is False:
                normalized = _normalize_skill_path(entry.get("path", ""))
                if normalized:
                    disabled.add(normalized)
    return disabled


def _write_skill_enabled(skill_path: Path, enabled: bool) -> None:
    normalized_target = _normalize_skill_path(skill_path)
    original = _CODEX_CONFIG_PATH.read_text(encoding="utf-8") if _CODEX_CONFIG_PATH.exists() else ""
    lines = original.splitlines(keepends=True)
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "[[skills.config]]":
            block = [line]
            i += 1
            while i < len(lines) and not re.match(r"^\s*\[\[.*\]\]\s*$", lines[i]):
                block.append(lines[i])
                i += 1
            block_text = "".join(block)
            path_match = re.search(r'^\s*path\s*=\s*["\']([^"\']+)["\']\s*$', block_text, re.M)
            block_path = _normalize_skill_path(path_match.group(1)) if path_match else ""
            if block_path == normalized_target:
                continue
            kept.append(block_text)
            continue
        kept.append(line)
        i += 1

    result = "".join(kept).rstrip()
    if not enabled:
        block = (
            '[[skills.config]]\n'
            f'path = "{skill_path.resolve().as_posix()}"\n'
            "enabled = false\n"
        )
        result = (result + "\n\n" + block) if result else block
    if result and not result.endswith("\n"):
        result += "\n"
    _CODEX_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CODEX_CONFIG_PATH.write_text(result, encoding="utf-8")


def _discover_installed_skill_dirs() -> list[Path]:
    discovered: list[Path] = []
    seen = set()
    for root in _SKILL_SCAN_ROOTS:
        if not root.exists():
            continue
        for skill_md in root.rglob("SKILL.md"):
            skill_dir = skill_md.parent.resolve()
            key = skill_dir.as_posix().lower()
            if key in seen:
                continue
            seen.add(key)
            discovered.append(skill_dir)
    return discovered


def _build_installed_skill_index() -> dict[str, dict]:
    disabled_paths = _load_disabled_skill_paths()
    skills: dict[str, dict] = {}
    for skill_dir in _discover_installed_skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        front_matter, body = _split_skill_markdown(_read_text_fallback(skill_md))
        body = _strip_leading_h1(body)
        name = str(front_matter.get("name") or skill_dir.name).strip()
        if not name or name in skills:
            continue
        interface = _read_yaml(skill_dir / "agents" / "openai.yaml").get("interface") or {}
        metadata = front_matter.get("metadata") or {}
        display_name = str(interface.get("display_name") or name).strip()
        short_description = str(
            interface.get("short_description")
            or metadata.get("short-description")
            or _first_markdown_paragraph(body)
        ).strip()
        default_prompt = str(interface.get("default_prompt") or "").strip()
        icon_small = interface.get("icon_small")
        icon_large = interface.get("icon_large")
        small_icon_path = (skill_dir / str(icon_small)).resolve() if icon_small else None
        large_icon_path = (skill_dir / str(icon_large)).resolve() if icon_large else None
        if small_icon_path and not small_icon_path.exists():
            small_icon_path = None
        if large_icon_path and not large_icon_path.exists():
            large_icon_path = None
        skills[name] = {
            "id": name,
            "name": display_name or name,
            "skill_name": name,
            "description": short_description,
            "enabled": _normalize_skill_path(skill_md) not in disabled_paths,
            "source": "installed_skill",
            "path": str(skill_dir),
            "skill_md_path": str(skill_md),
            "default_prompt": default_prompt,
            "body_markdown": body,
            "body_html": render_markdown_html(body),
            "icon_small_path": str(small_icon_path) if small_icon_path else "",
            "icon_large_path": str(large_icon_path) if large_icon_path else "",
            "has_example_prompt": bool(default_prompt),
        }
    return dict(sorted(skills.items(), key=lambda item: item[1].get("name", "").lower()))

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CODEX_HOME = Path.home() / ".codex"
_CODEX_CONFIG_PATH = _CODEX_HOME / "config.toml"
_WORKFLOW_SKILLS_DIR = _REPO_ROOT / "skills" / "builtin"
_TOOL_SKILLS_DIR = _REPO_ROOT / "tools" / "agent"
_COMPAT_SKILLS_DIR = _REPO_ROOT / "core" / "skills"
_NATIVE_SKILL_DOCS_DIR = _REPO_ROOT / "skills"
_SKILL_SCAN_ROOTS = (
    _CODEX_HOME / "skills",
    _REPO_ROOT / ".agents" / "skills",
)
def _serialize_skill_items(skills_data: dict) -> list[dict]:
    skills = []
    for name, info in (skills_data or {}).items():
        skills.append({
            "id": name,
            "name": info.get("name", name),
            "keywords": info.get("keywords", []),
            "anti_keywords": info.get("anti_keywords", []),
            "description": info.get("description", ""),
            "priority": info.get("priority", 10),
            "status": info.get("status", "ready"),
            "category": info.get("category", "\u901a\u7528"),
            "enabled": info.get("enabled", True),
            "source": info.get("source", "native"),
            "capability_kind": info.get("capability_kind", "domain_skill"),
            "substrate_layer": info.get("substrate_layer", "skill"),
            "protocol_family": info.get("protocol_family", "generic"),
            "exposure_scope": info.get("exposure_scope", "tool_call"),
            "stateful": info.get("stateful", False),
            "surfacing_profile": info.get("surfacing_profile", "tool_only"),
            "discovery_tags": info.get("discovery_tags", []),
            "operation_kind": info.get("operation_kind", "inspect"),
            "effect_level": info.get("effect_level", "read_only"),
            "risk_level": info.get("risk_level", "low"),
            "protocol_subfamily": info.get("protocol_subfamily", "generic"),
            "trust_level": info.get("trust_level", "trusted_local"),
            "user_view_scope": info.get("user_view_scope", "hidden"),
        })
    skills.sort(key=lambda item: (item.get("priority", 10), item.get("name", "")))
    return skills


def _native_skill_doc_candidates(skill_id: str) -> list[Path]:
    skill_name = str(skill_id or "").strip()
    if not skill_name:
        return []
    return [
        _NATIVE_SKILL_DOCS_DIR / ".system" / skill_name / "SKILL.md",
        _NATIVE_SKILL_DOCS_DIR / skill_name / "SKILL.md",
        _NATIVE_SKILL_DOCS_DIR / f"{skill_name}.md",
    ]


def _resolve_native_skill_doc_path(skill_id: str) -> Path | None:
    for candidate in _native_skill_doc_candidates(skill_id):
        if candidate.exists():
            return candidate
    return None


def _native_skill_doc_scope(doc_path: Path | None) -> str:
    if not doc_path:
        return "inline"
    try:
        relative = doc_path.resolve().relative_to(_NATIVE_SKILL_DOCS_DIR.resolve())
        parts = relative.parts
        if parts and parts[0] == ".system":
            return "system"
        return "user"
    except Exception:
        return "user"


def _resolve_native_skill_source_path(skill_id: str) -> Path:
    doc_path = _resolve_native_skill_doc_path(skill_id)
    if doc_path:
        return doc_path
    skill_name = str(skill_id or "").strip()
    for candidate in (
        _WORKFLOW_SKILLS_DIR / f"{skill_name}.py",
        _WORKFLOW_SKILLS_DIR / f"{skill_name}.json",
        _TOOL_SKILLS_DIR / f"{skill_name}.py",
        _TOOL_SKILLS_DIR / f"{skill_name}.json",
        _COMPAT_SKILLS_DIR / f"{skill_name}.py",
        _COMPAT_SKILLS_DIR / f"{skill_name}.json",
        _WORKFLOW_SKILLS_DIR / skill_name,
        _TOOL_SKILLS_DIR / skill_name,
        _COMPAT_SKILLS_DIR / skill_name,
    ):
        if candidate.exists():
            return candidate
    return _WORKFLOW_SKILLS_DIR


def _build_native_skill_fallback_markdown(skill_id: str, entry: dict | None = None) -> str:
    entry = entry if isinstance(entry, dict) else {}
    title = str(entry.get("name") or skill_id or "Skill").strip() or "Skill"
    description = str(entry.get("description") or "").strip()
    category = str(entry.get("category") or "").strip()
    keywords = [str(item).strip() for item in entry.get("keywords", []) if str(item).strip()][:8]
    properties = ((entry.get("parameters") or {}).get("properties") or {})

    lines = [f"# {title}"]
    if description:
        lines.extend(["", description])

    if category:
        lines.extend(["", "## Category", "", f"- {category}"])

    if keywords:
        lines.extend(["", "## Good Fit", ""])
        lines.extend(f"- {keyword}" for keyword in keywords)

    if properties:
        lines.extend(["", "## Inputs", ""])
        for key, value in properties.items():
            label = str(key).strip() or "input"
            desc = str((value or {}).get("description") or "").strip()
            lines.append(f"- `{label}`" + (f": {desc}" if desc else ""))

    if len(lines) == 1:
        lines.extend(["", "This skill is available in AaronCore."])
    return "\n".join(lines).strip()


def _load_native_skill_doc(skill_id: str, entry: dict | None = None) -> dict:
    entry = entry if isinstance(entry, dict) else {}
    doc_path = _resolve_native_skill_doc_path(skill_id)
    front_matter = {}
    body_markdown = ""

    if doc_path:
        front_matter, body_markdown = _split_skill_markdown(_read_text_fallback(doc_path))
        body_markdown = _strip_leading_h1(body_markdown)

    if not body_markdown:
        body_markdown = _build_native_skill_fallback_markdown(skill_id, entry)

    metadata = front_matter.get("metadata") if isinstance(front_matter.get("metadata"), dict) else {}
    name = str(
        front_matter.get("name")
        or metadata.get("display_name")
        or metadata.get("display-name")
        or entry.get("name")
        or skill_id
    ).strip() or str(skill_id or "Skill")
    description = str(
        front_matter.get("description")
        or metadata.get("short_description")
        or metadata.get("short-description")
        or entry.get("description")
        or _first_markdown_paragraph(body_markdown)
    ).strip()
    default_prompt = str(
        front_matter.get("default_prompt")
        or front_matter.get("defaultPrompt")
        or metadata.get("default_prompt")
        or metadata.get("default-prompt")
        or entry.get("default_prompt")
        or ""
    ).strip()

    source_path = doc_path or _resolve_native_skill_source_path(skill_id)
    return {
        "id": str(skill_id or "").strip(),
        "name": name,
        "description": description,
        "enabled": entry.get("enabled", True),
        "source": entry.get("source", "native"),
        "path": str(source_path),
        "default_prompt": default_prompt,
        "body_markdown": body_markdown,
            "body_html": render_markdown_html(body_markdown),
        "has_example_prompt": bool(default_prompt),
        "doc_scope": _native_skill_doc_scope(doc_path),
    }


def _enrich_native_skill_item(item: dict) -> dict:
    if not isinstance(item, dict):
        return {}
    if str(item.get("source") or "native") != "native":
        return item
    detail = _load_native_skill_doc(item.get("id"), item)
    enriched = dict(item)
    enriched["name"] = detail.get("name") or enriched.get("name")
    enriched["description"] = detail.get("description") or enriched.get("description")
    enriched["default_prompt"] = detail.get("default_prompt", "")
    enriched["has_example_prompt"] = detail.get("has_example_prompt", False)
    enriched["path"] = detail.get("path", "")
    enriched["doc_scope"] = detail.get("doc_scope", "user")
    return enriched


@router.get("/skills")
async def get_skills():
    if not S.NOVA_CORE_READY:
        return {"skills": [], "ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        skills_data = S.get_all_skills_for_ui()
        items = [_enrich_native_skill_item(item) for item in _serialize_skill_items(skills_data)]
        return {"skills": items, "ready": True}
    except Exception as exc:
        return {"skills": [], "ready": False, "error": str(exc)}


@router.get("/skills/catalog/summary")
async def get_skill_catalog_summary():
    if not S.NOVA_CORE_READY:
        return {"ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        summary = S.get_skill_catalog_summary()
        return {"ready": True, "summary": summary}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@router.get("/skills/views/tools")
async def get_tool_view(scope: str = "tool_call"):
    if not S.NOVA_CORE_READY:
        return {"ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        view = S.get_tool_view(scope)
        return {"ready": True, "scope": scope, "skills": view}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@router.get("/skills/views/user")
async def get_user_view(scope: str = "default"):
    if not S.NOVA_CORE_READY:
        return {"ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        view = S.get_user_visible_skills(scope)
        items = [_enrich_native_skill_item(item) for item in _serialize_skill_items(view)]
        return {"ready": True, "scope": scope, "skills": items}
    except Exception as exc:
        return {"ready": False, "error": str(exc), "skills": []}


@router.get("/skills/{skill_id}/detail")
async def get_skill_detail(skill_id: str):
    if not S.NOVA_CORE_READY:
        return {"ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        all_skills = S.get_all_skills_for_ui()
        skill = all_skills.get(skill_id)
        if not skill or str(skill.get("source") or "native") != "native":
            return {"ready": False, "error": "skill_not_found"}
        base_items = _serialize_skill_items({skill_id: skill})
        base_item = base_items[0] if base_items else {"id": skill_id, "source": "native"}
        detail = _load_native_skill_doc(skill_id, base_item)
        return {"ready": True, "skill": detail}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@router.get("/skills/installed")
async def get_installed_skills():
    try:
        skills = []
        for item in _build_installed_skill_index().values():
            skills.append({
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "enabled": item["enabled"],
                "source": item["source"],
                "icon_url": f"/skills/installed/{item['id']}/icon?size=small" if item.get("icon_small_path") else "",
                "has_example_prompt": item.get("has_example_prompt", False),
            })
        return {"ready": True, "skills": skills}
    except Exception as exc:
        return {"ready": False, "error": str(exc), "skills": []}


@router.get("/skills/installed/{skill_id}/detail")
async def get_installed_skill_detail(skill_id: str):
    try:
        skill = _build_installed_skill_index().get(skill_id)
        if not skill:
            return {"ready": False, "error": "skill_not_found"}
        return {
            "ready": True,
            "skill": {
                "id": skill["id"],
                "name": skill["name"],
                "description": skill["description"],
                "enabled": skill["enabled"],
                "path": skill["path"],
                "default_prompt": skill["default_prompt"],
                "body_markdown": skill["body_markdown"],
                "body_html": skill["body_html"],
                "icon_url": f"/skills/installed/{skill_id}/icon?size=large" if skill.get("icon_large_path") else (
                    f"/skills/installed/{skill_id}/icon?size=small" if skill.get("icon_small_path") else ""
                ),
                "has_example_prompt": skill.get("has_example_prompt", False),
            },
        }
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@router.get("/skills/installed/{skill_id}/icon")
async def get_installed_skill_icon(skill_id: str, size: str = "small"):
    skill = _build_installed_skill_index().get(skill_id)
    if not skill:
        return {"ok": False, "error": "skill_not_found"}
    icon_path = skill.get("icon_large_path") if size == "large" else skill.get("icon_small_path")
    if not icon_path:
        icon_path = skill.get("icon_small_path") or skill.get("icon_large_path")
    if not icon_path or not Path(icon_path).exists():
        return {"ok": False, "error": "icon_not_found"}
    return FileResponse(icon_path)


@router.post("/skills/installed/{skill_id}/toggle")
async def toggle_installed_skill(skill_id: str):
    try:
        skill = _build_installed_skill_index().get(skill_id)
        if not skill:
            return {"ok": False, "error": "skill_not_found"}
        new_enabled = not bool(skill.get("enabled", True))
        _write_skill_enabled(Path(skill["skill_md_path"]), new_enabled)
        return {"ok": True, "enabled": new_enabled}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/installed/{skill_id}/open-folder")
async def open_installed_skill_folder(skill_id: str):
    try:
        skill = _build_installed_skill_index().get(skill_id)
        if not skill:
            return {"ok": False, "error": "skill_not_found"}
        target = Path(skill["path"])
        if os.name == "nt":
            os.startfile(str(target))
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return {"ok": True, "path": str(target)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/skills/views/surfacing")
async def get_surfacing_view(profile: str = "contextual"):
    if not S.NOVA_CORE_READY:
        return {"ready": False, "error": S.CORE_IMPORT_ERROR or "core_not_ready"}
    try:
        view = S.get_surfacing_view(profile)
        return {"ready": True, "profile": profile, "skills": view}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@router.get("/skills/news/headlines")
async def get_news_headlines():
    try:
        from core.skills.news import _parse_rss, GOOGLE_NEWS_FEEDS
        url = GOOGLE_NEWS_FEEDS.get("top", list(GOOGLE_NEWS_FEEDS.values())[0])
        items, _ = _parse_rss(url, limit=6)
        headlines = [item.get("title", "") for item in items if item.get("title")]
        return {"headlines": headlines}
    except Exception as e:
        return {"headlines": [], "error": str(e)}


@router.post("/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: str):
    if not S.NOVA_CORE_READY:
        return {"ok": False, "error": "core_not_ready"}
    try:
        all_skills = S.get_all_skills_for_ui()
        skill = all_skills.get(skill_id)
        if not skill:
            return {"ok": False, "error": "skill_not_found"}
        new_enabled = not skill.get("enabled", True)
        ok = S.set_skill_enabled(skill_id, new_enabled)
        return {"ok": ok, "enabled": new_enabled}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/{skill_id}/open-folder")
async def open_skill_folder(skill_id: str):
    try:
        target = _resolve_native_skill_source_path(skill_id)
        if os.name == "nt":
            try:
                subprocess.Popen(["explorer.exe", f"/select,{target}"])
            except Exception:
                os.startfile(str(target.parent if target.is_file() else target))
        else:
            subprocess.Popen(["xdg-open", str(target.parent if target.is_file() else target)])
        return {"ok": True, "path": str(target)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── MCP 管理端点 ──

@router.get("/skills/mcp/servers")
async def get_mcp_servers():
    try:
        from core import mcp_client
        available = mcp_client.is_available()
        servers = mcp_client.get_server_status() if available else {}
        return {"ok": True, "available": available, "servers": servers}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers")
async def add_mcp_server(request: Request):
    try:
        from core import mcp_client
        body = await request.json()
        name = body.get("name", "").strip()
        command = body.get("command", "").strip()
        args = body.get("args", [])
        transport = body.get("transport", "stdio")
        env = body.get("env")
        if not name or not command:
            return {"ok": False, "error": "\u7f3a\u5c11 name \u6216 command"}
        result = mcp_client.add_server(name, command, args, transport, env)
        if result.get("ok") and body.get("auto_connect", True):
            connect_result = await mcp_client.connect_server(name)
            result["connect"] = connect_result
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.delete("/skills/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    try:
        from core import mcp_client
        await mcp_client.disconnect_server(name)
        return mcp_client.remove_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers/{name}/connect")
async def connect_mcp_server(name: str):
    try:
        from core import mcp_client
        return await mcp_client.connect_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/skills/mcp/servers/{name}/disconnect")
async def disconnect_mcp_server(name: str):
    try:
        from core import mcp_client
        return await mcp_client.disconnect_server(name)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── MCP 注册表端点 ──

@router.get("/skills/mcp/registry")
async def get_mcp_registry():
    try:
        from core import mcp_registry
        servers = mcp_registry.fetch_registry()
        return {"ok": True, "servers": servers}
    except Exception as exc:
        return {"ok": False, "servers": [], "error": str(exc)}


@router.get("/skills/mcp/registry/search")
async def search_mcp_registry(q: str = ""):
    try:
        from core import mcp_registry
        results = mcp_registry.search_registry(q)
        return {"ok": True, "servers": results}
    except Exception as exc:
        return {"ok": False, "servers": [], "error": str(exc)}


@router.post("/skills/mcp/registry/install")
async def install_from_registry(request: Request):
    try:
        from core import mcp_registry, mcp_client
        body = await request.json()
        name = body.get("name", "").strip()
        env_overrides = body.get("env", {})
        if not name:
            return {"ok": False, "error": "\u7f3a\u5c11\u670d\u52a1\u540d\u79f0"}

        config = mcp_registry.get_install_config(name)
        if not config:
            return {"ok": False, "error": f"\u6ce8\u518c\u8868\u4e2d\u672a\u627e\u5230: {name}"}

        # 合并用户提供的环境变量
        env = config.get("env", {})
        if env_overrides:
            env.update(env_overrides)

        result = mcp_client.add_server(
            name=config["name"],
            command=config["command"],
            args=config["args"],
            transport=config["transport"],
            env=env if env else None,
        )
        if result.get("ok"):
            connect_result = await mcp_client.connect_server(name)
            result["connect"] = connect_result
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
