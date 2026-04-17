import os
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
_DATA_ROOT_ENV_KEYS = ("AARONCORE_DATA_DIR", "NOVACORE_DATA_DIR")


def _resolve_data_root() -> Path:
    for key in _DATA_ROOT_ENV_KEYS:
        raw = str(os.environ.get(key) or "").strip()
        if raw:
            try:
                return Path(raw).expanduser().resolve()
            except Exception:
                return Path(raw).expanduser()
    return ENGINE_DIR


DATA_ROOT_DIR = _resolve_data_root()
USES_EXTERNAL_DATA_ROOT = DATA_ROOT_DIR != ENGINE_DIR
CORE_DIR = ENGINE_DIR / "core"
STATE_DATA_DIR = DATA_ROOT_DIR / "state_data"
MEMORY_STORE_DIR = STATE_DATA_DIR / "memory_store"
TASK_STORE_DIR = STATE_DATA_DIR / "task_store"
CONTENT_STORE_DIR = STATE_DATA_DIR / "content_store"
RUNTIME_STORE_DIR = STATE_DATA_DIR / "runtime_store"
CHAT_UPLOADS_DIR = RUNTIME_STORE_DIR / "chat_uploads"
PRIMARY_STATE_DIR = MEMORY_STORE_DIR
LEGACY_STATE_DIR = DATA_ROOT_DIR / "memory" if USES_EXTERNAL_DATA_ROOT else ENGINE_DIR / "memory"
LOGS_DIR = DATA_ROOT_DIR / "logs"
HTML_FILE = ENGINE_DIR / "output.html"
RESTORED_OUTPUT_JS_FILE = DATA_ROOT_DIR / ".tmp_settings_check.js" if USES_EXTERNAL_DATA_ROOT else ENGINE_DIR / ".tmp_settings_check.js"
LLM_CONFIG_TEMPLATE_FILE = ENGINE_DIR / "brain" / "llm_config.json"
LLM_CONFIG_FILE = DATA_ROOT_DIR / "brain" / "llm_config.json" if USES_EXTERNAL_DATA_ROOT else LLM_CONFIG_TEMPLATE_FILE
LLM_LOCAL_CONFIG_FILE = DATA_ROOT_DIR / "brain" / "llm_config.local.json" if USES_EXTERNAL_DATA_ROOT else ENGINE_DIR / "brain" / "llm_config.local.json"

PRIMARY_HISTORY_FILE = MEMORY_STORE_DIR / "msg_history.json"
LEGACY_HISTORY_FILE = LEGACY_STATE_DIR / "msg_history.json"
PRIMARY_STATS_FILE = RUNTIME_STORE_DIR / "stats.json"
LEGACY_STATS_FILE = LEGACY_STATE_DIR / "stats.json"
PERSONA_FILE = MEMORY_STORE_DIR / "persona.json"
KNOWLEDGE_FILE = MEMORY_STORE_DIR / "knowledge.json"
KNOWLEDGE_BASE_FILE = MEMORY_STORE_DIR / "knowledge_base.json"
L2_CONFIG_FILE = MEMORY_STORE_DIR / "l2_config.json"
L2_SHORT_TERM_FILE = MEMORY_STORE_DIR / "l2_short_term.json"
LONG_TERM_FILE = MEMORY_STORE_DIR / "long_term.json"
CONVERSATION_HISTORY_TEXT_FILE = MEMORY_STORE_DIR / "conversation_history.txt"
GROWTH_FILE = MEMORY_STORE_DIR / "growth.json"
EVOLUTION_FILE = MEMORY_STORE_DIR / "evolution.json"
FEEDBACK_RULES_FILE = MEMORY_STORE_DIR / "feedback_rules.json"
LEGACY_L3_SKILL_ARCHIVE_FILE = MEMORY_STORE_DIR / "long_term_legacy_skill_logs.json"
CONTENT_PROJECTS_FILE = CONTENT_STORE_DIR / "content_projects.json"
CONTENT_TOPIC_REGISTRY_FILE = CONTENT_STORE_DIR / "content_topic_registry.json"
STORY_STATE_FILE = CONTENT_STORE_DIR / "story_state.json"
TASK_PROJECTS_FILE = TASK_STORE_DIR / "task_projects.json"
TASKS_FILE = TASK_STORE_DIR / "tasks.json"
TASK_RELATIONS_FILE = TASK_STORE_DIR / "task_relations.json"
AUTOLEARN_CONFIG_FILE = RUNTIME_STORE_DIR / "autolearn_config.json"
AUTOLEARN_LOCAL_CONFIG_FILE = RUNTIME_STORE_DIR / "autolearn_config.local.json"
CHAT_CONFIG_FILE = RUNTIME_STORE_DIR / "chat_config.json"
FILE_EXPORT_STATE_FILE = RUNTIME_STORE_DIR / "file_export_state.json"
MCP_SERVERS_FILE = RUNTIME_STORE_DIR / "mcp_servers.json"
MCP_REGISTRY_CACHE_FILE = RUNTIME_STORE_DIR / "mcp_registry_cache.json"
QQ_MONITOR_STATE_FILE = RUNTIME_STORE_DIR / "qq_monitor_state.json"
QQ_MONITOR_DEBUG_LOG_FILE = RUNTIME_STORE_DIR / "qq_monitor_debug.log"
CU_DEBUG_LOG_FILE = RUNTIME_STORE_DIR / "cu_debug.log"
COMPUTER_USE_DEBUG_LOG_FILE = RUNTIME_STORE_DIR / "computer_use_debug.log"
QUERY_CACHE_FILE = RUNTIME_STORE_DIR / "query_cache.json"
SELF_REPAIR_REPORTS_FILE = RUNTIME_STORE_DIR / "self_repair_reports.json"
SKILL_STORE_FILE = RUNTIME_STORE_DIR / "skill_store.json"
TOOL_CALL_CONFIG_FILE = RUNTIME_STORE_DIR / "tool_call_config.json"
LAB_DIR = RUNTIME_STORE_DIR / "lab"
LEGACY_CORE_STATE_DIR = RUNTIME_STORE_DIR / "legacy_core_state"
TTS_CACHE_DIR = RUNTIME_STORE_DIR / "tts_cache"
DOCS_DIR = ENGINE_DIR / "docs"

DEFAULT_L1_RECENT_TOKEN_BUDGET = 4000
