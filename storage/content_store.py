from storage.json_store import load_json, write_json
from storage.paths import CONTENT_PROJECTS_FILE, CONTENT_TOPIC_REGISTRY_FILE


def load_content_projects():
    data = load_json(CONTENT_PROJECTS_FILE, [])
    return data if isinstance(data, list) else []


def save_content_projects(projects):
    write_json(CONTENT_PROJECTS_FILE, projects if isinstance(projects, list) else [])


def load_content_topic_registry():
    data = load_json(CONTENT_TOPIC_REGISTRY_FILE, {"used_topics": []})
    if not isinstance(data, dict):
        return {"used_topics": []}
    topics = data.get("used_topics")
    if not isinstance(topics, list):
        data["used_topics"] = []
    return data


def save_content_topic_registry(registry):
    payload = registry if isinstance(registry, dict) else {"used_topics": []}
    if not isinstance(payload.get("used_topics"), list):
        payload["used_topics"] = []
    write_json(CONTENT_TOPIC_REGISTRY_FILE, payload)
