"""数据查询路由：memory, docs, history, stats, nova_name"""
import ast
import json
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from core import shared as S
from core.markdown_render import render_markdown_html
from core.runtime_memory.l2_memory import classify_retention_bucket
from core.l8_learn import classify_l8_entry_kind, should_show_l8_timeline_entry
from core.runtime_state.state_loader import get_model_price, MODEL_PRICES

router = APIRouter()

RUNTIME_GRAPH_EXTENSIONS = {".py", ".js", ".html", ".css"}
RUNTIME_GRAPH_EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    "memory_db",
    "logs",
    "archive",
    "brain",
    "home",
    "desktop_runtime",
    "desktop_runtime_35",
}
RUNTIME_GRAPH_CLUSTER_META = {
    "runtime": {"label": "运行节点", "rank": 0, "color": "#0f766e"},
    "root": {"label": "主入口", "rank": 10, "color": "#334155"},
    "pages": {"label": "页面壳子", "rank": 20, "color": "#7c3aed"},
    "static_js": {"label": "前端脚本", "rank": 30, "color": "#2563eb"},
    "static_css": {"label": "页面样式", "rank": 40, "color": "#0f766e"},
    "routes": {"label": "路由层", "rank": 50, "color": "#ea580c"},
    "core": {"label": "核心执行", "rank": 60, "color": "#dc2626"},
    "tools": {"label": "辅助工具", "rank": 70, "color": "#0891b2"},
    "skills": {"label": "技能实现", "rank": 75, "color": "#b45309"},
    "tests": {"label": "测试验证", "rank": 80, "color": "#475569"},
    "misc": {"label": "其他模块", "rank": 90, "color": "#64748b"},
    "external": {"label": "当前任务目标", "rank": 100, "color": "#ca8a04"},
}
RUNTIME_GRAPH_FILE_ZH_OVERRIDES = {
    "agent_final.py": "后端主入口",
    "output.html": "主聊天页面",
    "runtime_graph_view.html": "独立图谱页面",
    "companion.html": "陪伴页面",
    "AI_Agent研究进展.html": "研究进展页面",
    "routes/__init__.py": "路由层初始化",
    "routes/chat.py": "聊天主路由",
    "routes/chat_recovered.py": "恢复聊天路由",
    "routes/companion.py": "陪伴路由",
    "routes/data.py": "数据路由",
    "routes/health.py": "健康检查路由",
    "routes/lab.py": "实验路由",
    "routes/models.py": "模型路由",
    "routes/settings.py": "设置路由",
    "routes/skills.py": "技能路由",
    "core/config.py": "核心配置",
    "core/context_builder.py": "上下文构建器",
    "core/context_pull.py": "上下文拉取器",
    "core/events.py": "事件定义",
    "core/executor.py": "执行器",
    "core/feedback_classifier.py": "反馈分类器",
    "core/feedback_loop.py": "反馈闭环",
    "core/flashback.py": "闪回回溯",
    "core/fs_protocol.py": "文件系统协议",
    "core/history_recall.py": "历史召回",
    "core/json_store.py": "JSON存储",
    "core/l2_memory.py": "L2记忆模块",
    "core/l8_learn.py": "L8学习模块",
    "core/lab.py": "实验核心",
    "core/logger.py": "日志模块",
    "core/mcp_client.py": "MCP客户端",
    "core/mcp_registry.py": "MCP注册表",
    "core/memory_consolidator.py": "记忆凝结器",
    "core/nerve.py": "神经中枢",
    "core/network_protocol.py": "网络协议",
    "core/nova_brain.py": "Nova大脑",
    "core/reply_formatter.py": "回复格式整理",
    "core/router.py": "内部路由器",
    "core/route_resolver.py": "路由解析器",
    "core/rule_runtime.py": "规则运行时",
    "core/self_repair.py": "自修复模块",
    "core/session_context.py": "会话上下文",
    "core/shared.py": "共享状态",
    "capability_registry/__init__.py": "技能注册表",
    "capability_registry/loader.py": "技能加载器",
    "core/state_loader.py": "状态加载器",
    "core/target_protocol.py": "目标协议",
    "core/task_store.py": "任务存储",
    "core/test_search.py": "测试搜索",
    "core/tool_adapter.py": "工具适配器",
    "core/vision.py": "视觉模块",
    "tools/agent/open_target.py": "打开目标工具",
    "tools/agent/app_target.py": "应用目标工具",
    "tools/agent/ui_interaction.py": "界面交互工具",
    "skills/builtin/article.py": "文章技能",
    "skills/builtin/content_task.py": "内容任务技能",
    "skills/builtin/development_flow.py": "开发流技能",
    "skills/builtin/news.py": "新闻技能",
    "skills/builtin/stock.py": "股票技能",
    "skills/builtin/story.py": "故事技能",
    "skills/builtin/task_plan.py": "任务规划技能",
    "skills/builtin/weather.py": "天气技能",
    "static/js/app.js": "主页面控制脚本",
    "static/js/awareness.js": "感知面板脚本",
    "static/js/chat.js": "聊天脚本",
    "static/js/companion.js": "陪伴页脚本",
    "static/js/docs.js": "文档页脚本",
    "static/js/entity.js": "实体页脚本",
    "static/js/i18n.js": "国际化脚本",
    "static/js/lab.js": "实验页脚本",
    "static/js/memory.js": "记忆页脚本",
    "static/js/runtime_graph.js": "运行图谱脚本",
    "static/js/settings.js": "设置页脚本",
    "static/js/stats.js": "统计页脚本",
    "static/js/utils.js": "前端工具集",
    "static/css/main.css": "主页面样式",
    "static/css/companion.css": "陪伴页样式",
    "tests/test_runtime_graph_route.py": "图谱路由测试",
}
RUNTIME_GRAPH_TOKEN_ZH = {
    "agent": "代理",
    "ai": "AI",
    "app": "应用",
    "awareness": "感知",
    "brain": "大脑",
    "builder": "构建",
    "chat": "聊天",
    "classifier": "分类",
    "companion": "陪伴",
    "config": "配置",
    "context": "上下文",
    "core": "核心",
    "css": "样式",
    "data": "数据",
    "decision": "决策",
    "docs": "文档",
    "entity": "实体",
    "event": "事件",
    "events": "事件",
    "executor": "执行",
    "feedback": "反馈",
    "fetch": "请求",
    "file": "文件",
    "final": "最终",
    "flashback": "闪回",
    "formatter": "格式整理",
    "fs": "文件系统",
    "graph": "图谱",
    "health": "健康",
    "history": "历史",
    "i18n": "国际化",
    "import": "导入",
    "init": "初始化",
    "json": "JSON",
    "js": "脚本",
    "knowledge": "知识",
    "lab": "实验",
    "learn": "学习",
    "loader": "加载",
    "logger": "日志",
    "main": "主界面",
    "mcp": "MCP",
    "memory": "记忆",
    "model": "模型",
    "models": "模型",
    "network": "网络",
    "nova": "Nova",
    "output": "输出",
    "page": "页面",
    "path": "路径",
    "plan": "计划",
    "planning": "规划",
    "preference": "偏好",
    "protocol": "协议",
    "pull": "拉取",
    "query": "查询",
    "recall": "召回",
    "recover": "恢复",
    "recovered": "恢复",
    "registry": "注册表",
    "repair": "修复",
    "reply": "回复",
    "resolver": "解析",
    "route": "路由",
    "router": "路由器",
    "rule": "规则",
    "runtime": "运行时",
    "search": "搜索",
    "self": "自我",
    "session": "会话",
    "settings": "设置",
    "shared": "共享",
    "skill": "技能",
    "skills": "技能",
    "stage": "阶段",
    "state": "状态",
    "stats": "统计",
    "store": "存储",
    "target": "目标",
    "task": "任务",
    "test": "测试",
    "tests": "测试",
    "tool": "工具",
    "utils": "工具集",
    "view": "视图",
    "vision": "视觉",
}
RUNTIME_GRAPH_ROUTE_PATTERN = re.compile(r'@router\.(?:get|post|put|delete|patch)\(\s*[\'"]([^\'"]+)[\'"]')
RUNTIME_GRAPH_FETCH_PATTERN = re.compile(r'(?:fetch|EventSource)\(\s*[\'"]([^\'"]+)[\'"]')
RUNTIME_GRAPH_JS_IMPORT_PATTERN = re.compile(r'import(?:[\s\w{},*]+from\s+)?[\'"]([^\'"]+)[\'"]')
RUNTIME_GRAPH_HTML_REF_PATTERN = re.compile(r'(?:src|href)=["\']([^"\']+)["\']', re.IGNORECASE)
RUNTIME_GRAPH_CSS_IMPORT_PATTERN = re.compile(r'@import\s+[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
RUNTIME_GRAPH_FILE_PATH_PATTERN = re.compile(
    r'([A-Za-z]:[\\/][^\r\n"“”<>|]+?\.(?:py|js|html|css|json|md|txt))',
    re.IGNORECASE,
)
RUNTIME_GRAPH_DIR_PATH_PATTERN = re.compile(
    r'(?:目录|路径|目标|文件夹)[:：]\s*([A-Za-z]:[^\r\n]+)',
    re.IGNORECASE,
)


def _runtime_graph_root() -> Path:
    engine_dir = getattr(S, "ENGINE_DIR", None)
    if engine_dir:
        try:
            path = Path(engine_dir)
            if path.exists():
                return path
        except Exception:
            pass
    return Path(__file__).resolve().parents[1]


def _runtime_graph_cluster_meta(cluster: str) -> dict:
    return dict(RUNTIME_GRAPH_CLUSTER_META.get(cluster, RUNTIME_GRAPH_CLUSTER_META["misc"]))


def _runtime_graph_cluster_for(rel_path: Path) -> str:
    rel_posix = rel_path.as_posix()
    if rel_posix.endswith(".html"):
        return "pages"
    if rel_posix.startswith("static/js/"):
        return "static_js"
    if rel_posix.startswith("static/css/"):
        return "static_css"
    if rel_posix.startswith("routes/"):
        return "routes"
    if rel_posix.startswith("capability_registry/"):
        return "core"
    if rel_posix.startswith("core/"):
        return "core"
    if rel_posix.startswith("tests/"):
        return "tests"
    if rel_posix.startswith("tools/"):
        return "tools"
    if rel_posix.startswith("skills/builtin/"):
        return "skills"
    if rel_path.parent == Path("."):
        return "root"
    return "misc"


def _runtime_graph_kind_for(rel_path: Path, cluster: str) -> str:
    suffix = rel_path.suffix.lower()
    if cluster == "routes":
        return "route"
    if cluster == "core":
        return "core"
    if cluster == "skills":
        return "skill"
    if cluster == "tests":
        return "test"
    if suffix == ".html":
        return "page"
    if suffix == ".js":
        return "script"
    if suffix == ".css":
        return "style"
    return "file"


def _runtime_graph_split_stem_tokens(stem: str) -> list[str]:
    text = str(stem or "").strip()
    if not text:
        return []
    if text == "__init__":
        return ["init"]
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return [part for part in re.split(r"[_\-\s]+", text) if part]


def _runtime_graph_translate_stem(stem: str) -> str:
    parts: list[str] = []
    for token in _runtime_graph_split_stem_tokens(stem):
        lowered = token.lower()
        if re.fullmatch(r"l\d+", lowered):
            parts.append(lowered.upper())
            continue
        translated = RUNTIME_GRAPH_TOKEN_ZH.get(lowered)
        if translated:
            parts.append(translated)
            continue
        if re.search(r"[\u4e00-\u9fff]", token):
            parts.append(token)
            continue
        parts.append(token.upper() if token.isupper() else token)
    if not parts:
        return ""
    if any(re.search(r"[\u4e00-\u9fff]", part) for part in parts):
        return "".join(parts)
    return " ".join(parts)


def _runtime_graph_file_subtitle(rel_path: Path, cluster: str) -> str:
    rel_posix = rel_path.as_posix()
    override = RUNTIME_GRAPH_FILE_ZH_OVERRIDES.get(rel_posix)
    if override:
        return override
    if rel_path.name == "__init__.py":
        return f"{_runtime_graph_cluster_meta(cluster)['label']}初始化"
    base = _runtime_graph_translate_stem(rel_path.stem) or rel_path.stem
    if cluster == "routes":
        return f"{base}路由"
    if cluster == "core":
        return f"{base}核心模块"
    if cluster == "static_js":
        return f"{base}前端脚本"
    if cluster == "static_css":
        return f"{base}页面样式"
    if cluster == "pages":
        return f"{base}页面"
    if cluster == "tests":
        return f"{base}测试"
    if cluster == "tools":
        return f"{base}辅助工具"
    if cluster == "skills":
        return f"{base}技能实现"
    if cluster == "root":
        return f"{base}根目录文件"
    return f"{base}模块"


def _runtime_graph_should_include(rel_path: Path) -> bool:
    if rel_path.suffix.lower() not in RUNTIME_GRAPH_EXTENSIONS:
        return False
    parts = rel_path.parts
    for part in parts:
        if part in RUNTIME_GRAPH_EXCLUDED_DIRS or part.startswith(".tmp_"):
            return False
        if part.startswith(".") and part not in {".", ".."}:
            return False
    return True


def _runtime_graph_collect_file_nodes(root: Path) -> tuple[list[dict], set[str], dict[str, str]]:
    nodes: list[dict] = []
    node_ids: set[str] = set()
    module_map: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel_path = path.relative_to(root)
        except Exception:
            continue
        if not _runtime_graph_should_include(rel_path):
            continue
        node_id = rel_path.as_posix()
        cluster = _runtime_graph_cluster_for(rel_path)
        cluster_meta = _runtime_graph_cluster_meta(cluster)
        node = {
            "id": node_id,
            "label": rel_path.name,
            "subtitle": _runtime_graph_file_subtitle(rel_path, cluster),
            "path": node_id,
            "cluster": cluster,
            "cluster_label": cluster_meta["label"],
            "cluster_rank": cluster_meta["rank"],
            "cluster_color": cluster_meta["color"],
            "kind": _runtime_graph_kind_for(rel_path, cluster),
        }
        nodes.append(node)
        node_ids.add(node_id)
        if rel_path.suffix.lower() == ".py":
            module_name = _runtime_graph_python_module_name(rel_path)
            if module_name:
                module_map[module_name] = node_id
    return nodes, node_ids, module_map


def _runtime_graph_python_module_name(rel_path: Path) -> str:
    parts = list(rel_path.with_suffix("").parts)
    if not parts:
        return ""
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _runtime_graph_python_package_parts(rel_path: Path) -> list[str]:
    parts = list(rel_path.with_suffix("").parts)
    if not parts:
        return []
    if parts[-1] == "__init__":
        return parts[:-1]
    return parts[:-1]


def _runtime_graph_add_edge(edges: list[dict], seen: set[tuple[str, str, str]], source: str, target: str, kind: str):
    if not source or not target or source == target:
        return
    edge_key = (source, target, kind)
    if edge_key in seen:
        return
    seen.add(edge_key)
    edges.append({"source": source, "target": target, "kind": kind})


def _runtime_graph_collect_route_patterns(root: Path, node_ids: set[str]) -> list[tuple[str, str, str]]:
    patterns: list[tuple[str, str, str]] = []
    for node_id in sorted(node_ids):
        if not node_id.startswith("routes/") or not node_id.endswith(".py"):
            continue
        try:
            text = (root / node_id).read_text(encoding="utf-8")
        except Exception:
            continue
        for match in RUNTIME_GRAPH_ROUTE_PATTERN.finditer(text):
            raw_path = str(match.group(1) or "").strip()
            if not raw_path or not raw_path.startswith("/"):
                continue
            prefix = raw_path.split("{", 1)[0]
            patterns.append((raw_path, prefix or raw_path, node_id))
    patterns.sort(key=lambda item: len(item[1]), reverse=True)
    return patterns


def _runtime_graph_match_route(api_path: str, route_patterns: list[tuple[str, str, str]]) -> str | None:
    path = str(api_path or "").strip()
    if not path.startswith("/"):
        return None
    path = path.split("?", 1)[0]
    for raw_path, prefix, node_id in route_patterns:
        if path == raw_path:
            return node_id
        if prefix and path.startswith(prefix):
            return node_id
    return None


def _runtime_graph_resolve_ref(source_id: str, raw_ref: str, node_ids: set[str]) -> str | None:
    ref = str(raw_ref or "").strip()
    if not ref or ref.startswith(("http://", "https://", "data:")):
        return None
    ref = ref.split("?", 1)[0].split("#", 1)[0].strip()
    if not ref:
        return None
    if ref.startswith("/"):
        target = Path(ref.lstrip("/"))
    else:
        target = Path(source_id).parent / ref
    if not target.name and not target.suffix:
        return None
    candidates = [target]
    if not target.suffix:
        for suffix in (".js", ".css", ".html", ".py"):
            candidates.append(target.with_suffix(suffix))
        candidates.append(target / "index.js")
    for candidate in candidates:
        node_id = candidate.as_posix().lstrip("/")
        if node_id in node_ids:
            return node_id
    return None


def _runtime_graph_resolve_python_candidates(
    rel_path: Path,
    module_name: str | None,
    alias_name: str | None,
    level: int,
) -> list[str]:
    package_parts = _runtime_graph_python_package_parts(rel_path)
    if level:
        trim = max(0, level - 1)
        base_parts = package_parts[: max(0, len(package_parts) - trim)]
    else:
        base_parts = []
    if module_name:
        module_parts = (base_parts + module_name.split(".")) if level else module_name.split(".")
    else:
        module_parts = list(base_parts)
    candidates: list[str] = []
    if alias_name and alias_name != "*":
        candidates.append(".".join(module_parts + [alias_name]).strip("."))
    candidates.append(".".join(module_parts).strip("."))
    return [item for item in candidates if item]


def _runtime_graph_collect_static_edges(
    root: Path,
    node_ids: set[str],
    module_map: dict[str, str],
) -> list[dict]:
    edges: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    route_patterns = _runtime_graph_collect_route_patterns(root, node_ids)

    for node_id in sorted(node_ids):
        path = root / node_id
        suffix = path.suffix.lower()
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        if suffix == ".py":
            try:
                tree = ast.parse(text)
            except Exception:
                tree = None
            if tree is not None:
                rel_path = Path(node_id)
                for ast_node in ast.walk(tree):
                    if isinstance(ast_node, ast.Import):
                        for alias in ast_node.names:
                            target = module_map.get(str(alias.name or "").strip())
                            if target:
                                _runtime_graph_add_edge(edges, seen, node_id, target, "import")
                    elif isinstance(ast_node, ast.ImportFrom):
                        for alias in ast_node.names:
                            for candidate in _runtime_graph_resolve_python_candidates(
                                rel_path,
                                ast_node.module,
                                alias.name,
                                ast_node.level,
                            ):
                                target = module_map.get(candidate)
                                if target:
                                    _runtime_graph_add_edge(edges, seen, node_id, target, "import")
                                    break
        elif suffix == ".js":
            for match in RUNTIME_GRAPH_JS_IMPORT_PATTERN.finditer(text):
                target = _runtime_graph_resolve_ref(node_id, match.group(1), node_ids)
                if target:
                    _runtime_graph_add_edge(edges, seen, node_id, target, "import")
            for match in RUNTIME_GRAPH_FETCH_PATTERN.finditer(text):
                target = _runtime_graph_match_route(match.group(1), route_patterns)
                if target:
                    _runtime_graph_add_edge(edges, seen, node_id, target, "api")
        elif suffix == ".html":
            for match in RUNTIME_GRAPH_HTML_REF_PATTERN.finditer(text):
                target = _runtime_graph_resolve_ref(node_id, match.group(1), node_ids)
                if target:
                    _runtime_graph_add_edge(edges, seen, node_id, target, "asset")
        elif suffix == ".css":
            for match in RUNTIME_GRAPH_CSS_IMPORT_PATTERN.finditer(text):
                target = _runtime_graph_resolve_ref(node_id, match.group(1), node_ids)
                if target:
                    _runtime_graph_add_edge(edges, seen, node_id, target, "asset")

    return edges


def _runtime_graph_fixed_nodes() -> list[dict]:
    cluster_meta = _runtime_graph_cluster_meta("runtime")
    base_nodes = [
        ("runtime:user", "用户输入", "每轮任务的起点", "runtime"),
        ("runtime:decision", "LLM判断", "模型决定先回答还是先走工具", "runtime"),
        ("runtime:memory", "记忆命中", "recall_memory / query_knowledge", "runtime"),
        ("runtime:planning", "任务规划", "task_plan 与执行拆解", "runtime"),
        ("runtime:reply", "最终回复", "最后真正发给你的可见输出", "runtime"),
    ]
    return [
        {
            "id": node_id,
            "label": label,
            "subtitle": path_text,
            "path": path_text,
            "cluster": cluster,
            "cluster_label": cluster_meta["label"],
            "cluster_rank": cluster_meta["rank"],
            "cluster_color": cluster_meta["color"],
            "kind": "runtime",
        }
        for node_id, label, path_text, cluster in base_nodes
    ]


def _runtime_graph_tool_node(tool_name: str) -> dict:
    cluster_meta = _runtime_graph_cluster_meta("runtime")
    safe_id = re.sub(r"[^a-z0-9_]+", "_", str(tool_name or "").strip().lower()).strip("_") or "tool"
    return {
        "id": f"tool:{safe_id}",
        "label": str(tool_name or "tool").strip(),
        "subtitle": "本轮实际调用的技能",
        "path": "本轮实际调用的技能",
        "cluster": "runtime",
        "cluster_label": cluster_meta["label"],
        "cluster_rank": cluster_meta["rank"],
        "cluster_color": cluster_meta["color"],
        "kind": "tool",
    }


def _runtime_graph_trim_text(text: str, limit: int = 96) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _runtime_graph_extract_tool_name(detail: str) -> str:
    detail = str(detail or "").strip()
    if " · " not in detail:
        return ""
    tool_name = detail.split(" · ", 1)[0].strip()
    if not tool_name:
        return ""
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_ ]{1,64}", tool_name):
        return tool_name
    return ""


def _runtime_graph_cleanup_path(path_text: str) -> str:
    cleaned = str(path_text or "").strip().strip("'\"`")
    for marker in [" · ", " / <think>", " / Traceback", " / ", "，", "。", "）", ")", "】", "]"]:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()
    cleaned = cleaned.rstrip("\\/ ")
    return cleaned.replace("\\", "/")


def _runtime_graph_extract_paths(detail: str) -> list[str]:
    paths: list[str] = []
    for match in RUNTIME_GRAPH_FILE_PATH_PATTERN.finditer(str(detail or "")):
        cleaned = _runtime_graph_cleanup_path(match.group(1))
        if cleaned:
            paths.append(cleaned)
    for match in RUNTIME_GRAPH_DIR_PATH_PATTERN.finditer(str(detail or "")):
        cleaned = _runtime_graph_cleanup_path(match.group(1))
        if cleaned:
            paths.append(cleaned)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in paths:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _runtime_graph_repo_node_from_path(path_text: str, root: Path, node_ids: set[str]) -> str | None:
    cleaned = _runtime_graph_cleanup_path(path_text)
    root_text = root.as_posix().rstrip("/")
    cleaned_lower = cleaned.lower()
    root_lower = root_text.lower()
    if cleaned_lower.startswith(root_lower + "/"):
        rel_path = cleaned[len(root_text) + 1 :].lstrip("/")
        if rel_path in node_ids:
            return rel_path
    return None


def _runtime_graph_external_node(path_text: str) -> dict:
    cleaned = _runtime_graph_cleanup_path(path_text)
    cluster_meta = _runtime_graph_cluster_meta("external")
    safe_id = re.sub(r"[^a-z0-9_]+", "_", cleaned.lower()).strip("_") or "target"
    return {
        "id": f"external:{safe_id}",
        "label": Path(cleaned).name or cleaned,
        "subtitle": "当前任务目标",
        "path": cleaned,
        "cluster": "external",
        "cluster_label": cluster_meta["label"],
        "cluster_rank": cluster_meta["rank"],
        "cluster_color": cluster_meta["color"],
        "kind": "external",
    }


def _runtime_graph_append_sequence(sequence: list[str], *node_ids: str):
    for node_id in node_ids:
        if not node_id:
            continue
        if sequence and sequence[-1] == node_id:
            continue
        sequence.append(node_id)


def _runtime_graph_collect_runs(
    history: list[dict],
    root: Path,
    node_ids: set[str],
    limit: int,
) -> tuple[list[dict], list[dict]]:
    runs: list[dict] = []
    tool_nodes: dict[str, dict] = {}

    for item in reversed(history):
        if len(runs) >= limit:
            break
        if str(item.get("role") or "") != "nova":
            continue
        process = item.get("process") or {}
        steps = process.get("steps") or []
        if not isinstance(steps, list) or not steps:
            continue

        raw_time = str(item.get("time") or "").strip()
        sequence = ["runtime:user"]
        active_nodes: list[str] = ["runtime:user"]
        error_nodes: list[str] = []
        external_nodes: dict[str, dict] = {}
        step_rows: list[dict] = []
        trigger = ""
        stuck = ""

        for step in steps:
            label = str(step.get("label") or "").strip()
            detail = str((step.get("full_detail") or step.get("detail") or "")).strip()
            status = str(step.get("status") or "done").strip() or "done"
            tool_name = _runtime_graph_extract_tool_name(detail)
            tool_id = ""
            step_targets: list[str] = []

            if label == "模型思考":
                step_targets.append("runtime:decision")
            if label in {"记忆加载", "记忆就绪"} or tool_name in {"recall_memory", "query_knowledge"}:
                step_targets.append("runtime:memory")
            if label == "任务规划" or tool_name == "task_plan":
                step_targets.append("runtime:planning")

            if tool_name:
                tool_node = _runtime_graph_tool_node(tool_name)
                tool_nodes[tool_node["id"]] = tool_node
                tool_id = tool_node["id"]
                step_targets.append(tool_id)

            for path_text in _runtime_graph_extract_paths(detail):
                repo_node = _runtime_graph_repo_node_from_path(path_text, root, node_ids)
                if repo_node:
                    step_targets.append(repo_node)
                else:
                    external_node = _runtime_graph_external_node(path_text)
                    external_nodes[external_node["id"]] = external_node
                    step_targets.append(external_node["id"])

            if not trigger:
                if tool_name:
                    trigger = f"{tool_name} · {_runtime_graph_trim_text(detail, 72)}"
                elif label not in {"记忆加载", "模型思考"}:
                    trigger = f"{label} · {_runtime_graph_trim_text(detail, 72)}"

            if status == "error":
                stuck = f"{label} · {_runtime_graph_trim_text(detail, 88)}"

            _runtime_graph_append_sequence(sequence, *step_targets)
            for node_id in step_targets:
                if node_id not in active_nodes:
                    active_nodes.append(node_id)
                if status == "error" and node_id not in error_nodes:
                    error_nodes.append(node_id)

            step_rows.append(
                {
                    "label": label,
                    "detail": detail,
                    "status": status,
                    "tool": tool_name,
                    "targets": step_targets,
                }
            )

        _runtime_graph_append_sequence(sequence, "runtime:reply")
        if "runtime:reply" not in active_nodes:
            active_nodes.append("runtime:reply")

        runs.append(
            {
                "id": raw_time or f"run-{len(runs) + 1}",
                "time": raw_time,
                "preview": _runtime_graph_trim_text(item.get("content") or "", 96),
                "status": "error" if error_nodes else "done",
                "trigger": trigger or "本轮先从直接回复开始",
                "stuck": stuck,
                "node_ids": active_nodes,
                "error_node_ids": error_nodes,
                "path_edges": [
                    {"source": sequence[idx], "target": sequence[idx + 1]}
                    for idx in range(len(sequence) - 1)
                    if sequence[idx] != sequence[idx + 1]
                ],
                "steps": step_rows,
                "external_nodes": list(external_nodes.values()),
            }
        )

    return runs, list(tool_nodes.values())


def _is_live_skill_name(skill_name: str) -> bool:
    skill_name = str(skill_name or "").strip()
    if not skill_name:
        return False

    checker = getattr(S, "is_registered_skill_name", None)
    if callable(checker):
        try:
            if checker(skill_name):
                return True
        except Exception:
            pass

    registry_loader = getattr(S, "get_all_skills", None)
    if callable(registry_loader):
        try:
            skills = registry_loader() or {}
            return skill_name in skills
        except Exception:
            pass

    return False


def _l8_source_label(kind: str) -> str:
    if kind == "dialogue_crystal":
        return "对话结晶"
    if kind == "feedback_relearn":
        return "纠偏补学"
    return "自主学习"


def _l2_type_label(memory_type: str) -> str:
    memory_type = str(memory_type or "").strip().lower()
    mapping = {
        "fact": "事实印象",
        "preference": "偏好印象",
        "rule": "规则印象",
        "project": "项目线索",
        "goal": "目标意图",
        "decision": "决策印象",
        "knowledge": "知识线索",
        "correction": "纠正印象",
        "skill_demand": "需求线索",
        "general": "对话印象",
    }
    return mapping.get(memory_type, "对话印象")


def _build_l2_meta(item: dict, ai_brief: str, *, hit_count: int | None = None, crystallized: bool | None = None) -> dict:
    memory_type = str(item.get("memory_type") or "general").strip().lower() or "general"
    retention_entry = dict(item)
    if hit_count is not None:
        retention_entry["hit_count"] = int(hit_count or 0)
    if crystallized is not None:
        retention_entry["crystallized"] = bool(crystallized)
    retention = classify_retention_bucket(retention_entry)
    return {
        "kind": "l2_impression",
        "memory_type": memory_type,
        "type_label": _l2_type_label(memory_type),
        "user_text": str(item.get("user_text") or "").strip(),
        "ai_brief": ai_brief,
        "hit_count": int(retention_entry.get("hit_count") or 0),
        "crystallized": bool(retention_entry.get("crystallized")),
        "retention_tier": retention["tier"],
        "retention_label": retention["label"],
        "retention_reason": retention["reason"],
        "age_days": retention["age_days"],
    }


def _build_l2_ai_brief(ai_text: str) -> str:
    ai_text = str(ai_text or "").strip()
    ai_clean = re.sub(r'^[\s\uff08\u0028][^\uff09\u0029]*[\uff09\u0029]\s*', '', ai_text)
    ai_clean = ai_clean.replace("\n", " ").strip()
    if not ai_clean:
        ai_clean = ai_text.replace("\n", " ").strip()
    ai_brief = ai_clean
    for sep in ["。", "！", "？", "～", "~"]:
        if sep in ai_brief:
            ai_brief = ai_brief[:ai_brief.index(sep) + 1]
            break
    if len(ai_brief) > 40:
        ai_brief = ai_brief[:40] + "…"
    return ai_brief


def _build_l2_event(item: dict, ai_brief: str, repeat_count: int = 1, hit_count: int | None = None, crystallized: bool | None = None) -> dict:
    user_text = str(item.get("user_text") or "").strip()
    content = f"“{user_text}”"
    if ai_brief:
        content += f" —— {ai_brief}"
    meta = _build_l2_meta(item, ai_brief, hit_count=hit_count, crystallized=crystallized)
    meta["repeat_count"] = max(1, int(repeat_count or 1))
    return {
        "time": S.normalize_event_time(item.get("created_at") or item.get("time")),
        "layer": "L2",
        "event_type": "impression",
        "title": _l2_type_label(item.get("memory_type")),
        "content": content,
        "meta": meta,
    }


def _safe_stringify(value) -> str:
    formatter = getattr(S, "stringify_event_value", None)
    if callable(formatter):
        try:
            return formatter(value)
        except Exception:
            pass
    return str(value or "").strip()


@router.get("/memory")
async def get_memory():
    S.ensure_long_term_clean()
    events = []
    counts = {"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0, "L7": 0, "L8": 0}

    l1_file = S.PRIMARY_HISTORY_FILE
    if l1_file.exists():
        try:
            l1_data = json.loads(l1_file.read_text(encoding="utf-8"))
            for item in l1_data:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                counts["L1"] += 1
        except Exception:
            pass

    l2_file = S.PRIMARY_STATE_DIR / "l2_short_term.json"
    if l2_file.exists():
        try:
            l2_data = json.loads(l2_file.read_text(encoding="utf-8"))
            if isinstance(l2_data, list):
                counts["L2"] = len(l2_data)
                general_groups = {}
                for item in l2_data:
                    imp = item.get("importance") or 0
                    if imp >= 0.7:
                        user_text = str(item.get("user_text") or "").strip()
                        if not user_text:
                            continue
                        ai_brief = _build_l2_ai_brief(item.get("ai_text"))
                        memory_type = str(item.get("memory_type") or "general").strip().lower() or "general"
                        if memory_type == "general":
                            group = general_groups.get(user_text)
                            raw_time = str(item.get("created_at") or item.get("time") or "").strip()
                            if not group:
                                general_groups[user_text] = {
                                    "item": item,
                                    "ai_brief": ai_brief,
                                    "time_raw": raw_time,
                                    "repeat_count": 1,
                                    "hit_count": int(item.get("hit_count") or 0),
                                    "crystallized": bool(item.get("crystallized")),
                                }
                            else:
                                group["repeat_count"] += 1
                                group["hit_count"] += int(item.get("hit_count") or 0)
                                group["crystallized"] = group["crystallized"] or bool(item.get("crystallized"))
                                if raw_time and (not group["time_raw"] or raw_time >= group["time_raw"]):
                                    group["item"] = item
                                    group["ai_brief"] = ai_brief
                                    group["time_raw"] = raw_time
                            continue

                        events.append(_build_l2_event(item, ai_brief))

                for group in general_groups.values():
                    events.append(
                        _build_l2_event(
                            group["item"],
                            group["ai_brief"],
                            repeat_count=group["repeat_count"],
                            hit_count=group["hit_count"],
                            crystallized=group["crystallized"],
                        )
                    )
        except Exception:
            pass

    l3_file = S.PRIMARY_STATE_DIR / "long_term.json"
    if l3_file.exists():
        try:
            l3_data = json.loads(l3_file.read_text(encoding="utf-8"))
            for item in l3_data:
                if S.is_legacy_l3_skill_log(item):
                    continue
                content = S.event_text(item)
                if not content:
                    continue
                events.append({
                    "time": S.normalize_event_time(item.get("timestamp") or item.get("time") or item.get("created_at")),
                    "layer": "L3",
                    "event_type": item.get("category", "memory"),
                    "title": "\u8bb0\u5fc6\u7ed3\u6676",
                    "content": f"\u6c89\u6dc0\u4e86\u4e00\u6bb5\u957f\u671f\u8bb0\u5fc6\uff1a{content}",
                })
                counts["L3"] += 1
        except Exception:
            pass

    l4_file = S.PRIMARY_STATE_DIR / "persona.json"
    if l4_file.exists():
        try:
            l4_data = json.loads(l4_file.read_text(encoding="utf-8"))
            l4_init_time = S.normalize_event_time(l4_data.get("created_at") or "2026-03-10 00:00")
            for item in S.build_persona_events(l4_data, l4_init_time):
                events.append(item)
                counts["L4"] += 1
        except Exception:
            pass

    l5_file = S.PRIMARY_STATE_DIR / "knowledge.json"
    if l5_file.exists():
        try:
            l5_skills = json.loads(l5_file.read_text(encoding="utf-8"))
            visible_l5_skills = [
                item for item in l5_skills
                if isinstance(item, dict) and str(item.get("source") or "").strip() != "l2_demand"
            ]
            for item in visible_l5_skills:
                skill_name = item.get("name") or item.get("\u6838\u5fc3\u6280\u80fd") or "skill"
                skill_count = len(visible_l5_skills)
                source = str(item.get("source") or "").strip()
                if source == "l6_success_path":
                    content = str(item.get("summary") or item.get("\u5e94\u7528\u793a\u4f8b") or "").strip()
                    if not content:
                        content = f"\u6c89\u6dc0\u4e86\u300c{skill_name}\u300d\u7684\u7a33\u5b9a\u6210\u529f\u7ecf\u9a8c"
                    success_count = int(item.get("success_count", item.get("\u4f7f\u7528\u6b21\u6570", 0)) or 0)
                    events.append({
                        "time": S.normalize_event_time(item.get("learned_at") or item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")),
                        "layer": "L5", "event_type": "method_experience", "title": "\u65b9\u6cd5\u7ecf\u9a8c",
                        "content": f"{skill_name} / {content} / \u5df2\u6c89\u6dc0 {success_count} \u6b21",
                        "meta": {
                            "kind": "method_experience",
                            "skill": skill_name,
                            "summary": content,
                            "success_count": success_count,
                            "source": source,
                        },
                    })
                    counts["L5"] += 1
                    continue
                events.append({
                    "time": S.normalize_event_time(item.get("learned_at") or item.get("\u6700\u8fd1\u4f7f\u7528\u65f6\u95f4")),
                    "layer": "L5", "event_type": "ability_hint", "title": "\u80fd\u529b\u7ebf\u7d22",
                    "content": f"\u8bb0\u5f55\u4e86\u300c{skill_name}\u300d\u8fd9\u6761\u80fd\u529b\u7ebf\u7d22\uff08\u5f53\u524d L5 \u53ef\u89c1 {skill_count} \u9879\uff09",
                    "meta": {
                        "kind": "ability_hint",
                        "skill": skill_name,
                        "visible_count": skill_count,
                        "source": source,
                    },
                })
                counts["L5"] += 1
        except Exception:
            pass

    l6_file = S.PRIMARY_STATE_DIR / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skill_runs = l6_data.get("skill_runs", [])
            if isinstance(skill_runs, list) and skill_runs:
                for item in reversed(skill_runs[-80:]):
                    if not isinstance(item, dict):
                        continue
                    skill_name = str(item.get("skill") or "").strip()
                    if not _is_live_skill_name(skill_name):
                        continue
                    verified = item.get("verified")
                    observed = str(item.get("observed_state") or "").strip()
                    drift_reason = str(item.get("drift_reason") or "").strip()
                    summary = str(item.get("summary") or "").strip()
                    verification_mode = str(item.get("verification_mode") or "").strip()
                    verification_detail = str(item.get("verification_detail") or "").strip()
                    parts = [skill_name]
                    if summary:
                        parts.append(summary)
                    if verified is True:
                        parts.append("verified")
                    elif drift_reason:
                        parts.append(f"drift={drift_reason}")
                    if observed:
                        parts.append(f"observed={observed}")
                    events.append({
                        "time": S.normalize_event_time(item.get("at")),
                        "layer": "L6", "event_type": "execution_trace", "title": "\u6267\u884c\u8f68\u8ff9",
                        "content": " / ".join([p for p in parts if p]),
                        "meta": {
                            "kind": "execution_trace",
                            "skill": skill_name,
                            "summary": summary,
                            "verified": verified,
                            "observed_state": observed,
                            "drift_reason": drift_reason,
                            "verification_mode": verification_mode,
                            "verification_detail": verification_detail,
                        },
                    })
                    counts["L6"] += 1
            else:
                skills_used = l6_data.get("skills_used", {})
                for skill_name, data in skills_used.items():
                    if not _is_live_skill_name(skill_name):
                        continue
                    count = data.get("count", 0)
                    tail = "\u8d8a\u6765\u8d8a\u719f\u7ec3\u4e86" if count >= 3 else "\u5df2\u7ecf\u7559\u4e0b\u7b2c\u4e00\u6b21\u6267\u884c\u75d5\u8ff9"
                    events.append({
                        "time": S.normalize_event_time(data.get("last_used")),
                        "layer": "L6", "event_type": "execution_trace", "title": "\u6267\u884c\u8f68\u8ff9",
                        "content": f"\u4f7f\u7528\u4e86\uff1a\u300c{skill_name}\u300d \uff08{tail}\uff0c\u7d2f\u8ba1 {count} \u6b21\uff09",
                        "meta": {
                            "kind": "execution_count",
                            "skill": skill_name,
                            "count": count,
                            "status_note": tail,
                        },
                    })
                    counts["L6"] += 1
        except Exception:
            pass

    l7_file = S.PRIMARY_STATE_DIR / "feedback_rules.json"
    if l7_file.exists():
        try:
            l7_data = json.loads(l7_file.read_text(encoding="utf-8"))
            for item in l7_data:
                feedback = str(item.get("user_feedback") or "").strip()
                fix = str(item.get("fix") or "").strip()
                category = str(item.get("category") or "").strip()
                scene = str(item.get("scene") or "general").strip()
                content = feedback or "\u6536\u5230\u4e00\u6761\u65b0\u7684\u53cd\u9988\u4fee\u6b63\u89c4\u5219"
                if fix:
                    content = f"\u6536\u5230\u53cd\u9988\uff1a{content}\uff08\u4fee\u6b63\u65b9\u5411\uff1a{fix}\uff09"
                title = category or "\u53cd\u9988\u5b66\u4e60"
                events.append({
                    "time": S.normalize_event_time(item.get("created_at") or item.get("time")),
                    "layer": "L7", "event_type": "feedback", "title": title,
                    "content": content, "scene": scene,
                })
                counts["L7"] += 1
        except Exception:
            pass

    l8_file = S.PRIMARY_STATE_DIR / "knowledge_base.json"
    if l8_file.exists():
        try:
            l8_data = json.loads(l8_file.read_text(encoding="utf-8"))
            for item in l8_data:
                if not should_show_l8_timeline_entry(item):
                    continue
                kind = classify_l8_entry_kind(item)
                query = str(item.get("query") or item.get("name") or "已学知识").strip()
                summary = _safe_stringify(item.get("summary") or item.get("应用示例") or "")
                primary_scene = str(item.get("一级场景") or "").strip()
                secondary_scene = str(item.get("二级场景") or "").strip()
                hit_count = int(item.get("hit_count", 0) or 0)
                source_label = _l8_source_label(kind)
                content = f"学到「{query}」"
                if summary:
                    content += f"：{summary}"
                else:
                    content += "，已沉淀为新的知识卡片"
                events.append({
                    "time": S.normalize_event_time(item.get("last_used") or item.get("最近使用时间") or item.get("time") or item.get("created_at")),
                    "layer": "L8", "event_type": kind, "title": source_label,
                    "content": content,
                    "meta": {
                        "kind": kind,
                        "query": query,
                        "summary": summary,
                        "source": str(item.get("source") or "").strip(),
                        "source_label": source_label,
                        "hit_count": hit_count,
                        "primary_scene": primary_scene,
                        "secondary_scene": secondary_scene,
                        "keywords": item.get("keywords") or item.get("trigger") or [],
                    },
                })
                counts["L8"] += 1
        except Exception:
            pass

    return {"events": sorted(events, key=lambda item: item["time"], reverse=True), "counts": counts}


@router.get("/runtime_graph")
async def get_runtime_graph(limit: int = 12):
    root = _runtime_graph_root()
    file_nodes, node_ids, module_map = _runtime_graph_collect_file_nodes(root)
    static_edges = _runtime_graph_collect_static_edges(root, node_ids, module_map)
    history_loader = getattr(S, "load_msg_history", None)
    history = history_loader() if callable(history_loader) else []
    run_limit = max(1, min(int(limit or 12), 24))
    runs, tool_nodes = _runtime_graph_collect_runs(history, root, node_ids, run_limit)
    nodes = _runtime_graph_fixed_nodes() + tool_nodes + file_nodes
    nodes.sort(key=lambda item: (item.get("cluster_rank", 999), item.get("path", ""), item.get("label", "")))
    return {
        "root": str(root),
        "summary": {
            "file_count": len(file_nodes),
            "edge_count": len(static_edges),
            "run_count": len(runs),
            "tool_count": len(tool_nodes),
        },
        "nodes": nodes,
        "edges": static_edges,
        "runs": runs,
    }


@router.get("/docs/index")
async def get_docs_index():
    sections = S.build_docs_index()
    default_path = ""
    for section in sections:
        docs = section.get("docs", [])
        if docs:
            default_path = docs[0].get("path", "")
            break
    return {"sections": sections, "default_path": default_path}


@router.get("/docs/content")
async def get_doc_content(path: str):
    doc_path = S.resolve_doc_path(path)
    if not doc_path or not doc_path.exists():
        return {"ok": False, "error": "doc_not_found"}
    try:
        text = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "path": doc_path.relative_to(S.ENGINE_DIR).as_posix(),
        "title": S.extract_doc_title(text, doc_path.stem),
        "content": text,
    }


@router.get("/history")
async def get_history(limit: int = 40, offset: int = 0):
    history = S.load_msg_history()
    total = len(history)
    # offset=0 表示最新的，从末尾往前取
    if offset <= 0:
        chunk = history[-limit:] if limit < total else history
    else:
        end = total - offset
        start = max(0, end - limit)
        chunk = history[start:end] if end > 0 else []
    formatted = []
    for item in chunk:
        row = dict(item)
        if "time" in row:
            try:
                row["time"] = datetime.fromisoformat(row["time"]).strftime("%m-%d %H:%M")
            except Exception:
                pass
        role = str(row.get("role") or "").strip().lower()
        if role and role != "user":
            row["content_html"] = render_markdown_html(row.get("content", ""))
        formatted.append(row)
    return {"history": formatted, "text_history": S.get_text_history(20), "total": total, "has_more": (total - offset - limit) > 0}


@router.get("/stats")
async def get_stats():
    stats = S.load_stats_data()
    stats["prices"] = get_model_price(stats.get("model", ""))
    stats["all_prices"] = MODEL_PRICES
    # ── 补充真实的 L3/L5 计数（快照值不可靠，直接读文件）──────────
    mem = stats.setdefault("memory", {})
    try:
        l3_raw = json.loads((S.PRIMARY_STATE_DIR / "long_term.json").read_text("utf-8"))
        real_l3 = sum(1 for i in l3_raw if isinstance(i, dict) and not S.is_legacy_l3_skill_log(i))
        mem["real_l3_count"] = real_l3
    except Exception:
        mem["real_l3_count"] = mem.get("l3_count", 0)
    try:
        from capability_registry import get_all_skills
        mem["real_l5_count"] = len(get_all_skills())
    except Exception:
        try:
            kb = json.loads((S.PRIMARY_STATE_DIR / "knowledge.json").read_text("utf-8"))
            mem["real_l5_count"] = len(kb) if isinstance(kb, list) else 0
        except Exception:
            mem["real_l5_count"] = mem.get("l5_count", 0)
    try:
        persona = json.loads((S.PRIMARY_STATE_DIR / "persona.json").read_text("utf-8"))
        if not isinstance(persona, dict):
            persona = {}
        active_mode = str(persona.get("active_mode") or "").strip()
        persona_modes = persona.get("persona_modes") or {}
        mode_cfg = persona_modes.get(active_mode) if isinstance(persona_modes, dict) else {}
        if not isinstance(mode_cfg, dict):
            mode_cfg = {}
        speech_style = persona.get("speech_style") or {}
        if not isinstance(speech_style, dict):
            speech_style = {}

        def _count_nonempty(value):
            if isinstance(value, dict):
                return sum(_count_nonempty(v) for v in value.values())
            if isinstance(value, list):
                return sum(1 for item in value if str(item or "").strip())
            return 1 if str(value or "").strip() else 0

        def _recent_update_count(changelog, limit_days=7):
            now = datetime.now()
            total = 0
            for item in changelog if isinstance(changelog, list) else []:
                if not isinstance(item, dict):
                    continue
                raw = str(item.get("time") or item.get("created_at") or "").strip()
                if not raw:
                    continue
                try:
                    ts = datetime.fromisoformat(raw.replace("/", "-"))
                except Exception:
                    try:
                        ts = datetime.strptime(raw, "%Y-%m-%d %H:%M")
                    except Exception:
                        continue
                if (now - ts).days <= limit_days:
                    total += 1
            return total

        user_profile = persona.get("user_profile") or {}
        relationship_profile = persona.get("relationship_profile") or {}
        ai_profile = persona.get("ai_profile") or {}
        rules = persona.get("interaction_rules") or []
        tone = mode_cfg.get("tone") or speech_style.get("tone") or []
        particles = mode_cfg.get("particles") or speech_style.get("particles") or []
        avoid = mode_cfg.get("avoid") or speech_style.get("avoid") or []
        style_prompt = str(mode_cfg.get("style_prompt") or persona.get("style_prompt") or "").strip()
        changelog = persona.get("_changelog") or []

        mem["real_l4_active_mode"] = active_mode or "default"
        mem["real_l4_rule_count"] = len(rules) if isinstance(rules, list) else 0
        mem["real_l4_profile_count"] = (
            _count_nonempty(user_profile) +
            _count_nonempty(relationship_profile) +
            _count_nonempty(ai_profile)
        )
        mem["real_l4_tone_count"] = len(tone) if isinstance(tone, list) else 0
        mem["real_l4_particle_count"] = len(particles) if isinstance(particles, list) else 0
        mem["real_l4_avoid_count"] = len(avoid) if isinstance(avoid, list) else 0
        mem["real_l4_style_prompt"] = 1 if style_prompt else 0
        mem["real_l4_changelog_count"] = len(changelog) if isinstance(changelog, list) else 0
        mem["real_l4_recent_updates"] = _recent_update_count(changelog, limit_days=7)
    except Exception:
        mem.setdefault("real_l4_active_mode", "default")
        mem.setdefault("real_l4_rule_count", 0)
        mem.setdefault("real_l4_profile_count", 0)
        mem.setdefault("real_l4_tone_count", 0)
        mem.setdefault("real_l4_particle_count", 0)
        mem.setdefault("real_l4_avoid_count", 0)
        mem.setdefault("real_l4_style_prompt", 0)
        mem.setdefault("real_l4_changelog_count", 0)
        mem.setdefault("real_l4_recent_updates", 0)
    return {"stats": stats}


@router.post("/stats")
async def update_stats(request: dict):
    inp = int(request.get("input_tokens", 0)) if isinstance(request, dict) else 0
    out = int(request.get("output_tokens", 0)) if isinstance(request, dict) else 0
    scene = str(request.get("scene", "chat")) if isinstance(request, dict) else "chat"
    cache_write = int(request.get("cache_write", 0)) if isinstance(request, dict) else 0
    cache_read = int(request.get("cache_read", 0)) if isinstance(request, dict) else 0
    model = str(request.get("model", "")) if isinstance(request, dict) else ""
    stats = S.record_stats(
        input_tokens=inp,
        output_tokens=out,
        scene=scene,
        cache_write=cache_write,
        cache_read=cache_read,
        model=model,
    )
    return {"ok": True, "stats": stats}


@router.get("/nova_name")
async def get_nova_name():
    persona_path = S.PRIMARY_STATE_DIR / "persona.json"
    if persona_path.exists():
        try:
            persona = json.loads(persona_path.read_text(encoding="utf-8"))
            return {"name": persona.get("nova_name", "NovaCore")}
        except Exception:
            pass
    return {"name": "NovaCore"}
