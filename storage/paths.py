from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = ENGINE_DIR / "core"
PRIMARY_STATE_DIR = ENGINE_DIR / "state_data"
LEGACY_STATE_DIR = ENGINE_DIR / "memory"
LOGS_DIR = ENGINE_DIR / "logs"
HTML_FILE = ENGINE_DIR / "output.html"
RESTORED_OUTPUT_JS_FILE = ENGINE_DIR / ".tmp_settings_check.js"
LLM_CONFIG_FILE = ENGINE_DIR / "brain" / "llm_config.json"

PRIMARY_HISTORY_FILE = PRIMARY_STATE_DIR / "msg_history.json"
LEGACY_HISTORY_FILE = LEGACY_STATE_DIR / "msg_history.json"
PRIMARY_STATS_FILE = PRIMARY_STATE_DIR / "stats.json"
LEGACY_STATS_FILE = LEGACY_STATE_DIR / "stats.json"
LEGACY_L3_SKILL_ARCHIVE_FILE = PRIMARY_STATE_DIR / "long_term_legacy_skill_logs.json"
CONTENT_PROJECTS_FILE = PRIMARY_STATE_DIR / "content_projects.json"
CONTENT_TOPIC_REGISTRY_FILE = PRIMARY_STATE_DIR / "content_topic_registry.json"
TASK_PROJECTS_FILE = PRIMARY_STATE_DIR / "task_projects.json"
TASKS_FILE = PRIMARY_STATE_DIR / "tasks.json"
TASK_RELATIONS_FILE = PRIMARY_STATE_DIR / "task_relations.json"
DOCS_DIR = ENGINE_DIR / "docs"

DEFAULT_L1_RECENT_TOKEN_BUDGET = 8000
