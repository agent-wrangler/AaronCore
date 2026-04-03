from storage.json_store import load_json
from storage.paths import LLM_CONFIG_FILE


def load_current_model() -> str:
    llm_conf = load_json(LLM_CONFIG_FILE, {})
    if isinstance(llm_conf, dict):
        model_name = llm_conf.get("model") or llm_conf.get("default") or "unknown"
        return str(model_name)
    return "unknown"
