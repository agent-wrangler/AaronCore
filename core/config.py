from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PATH = {
    "root": str(ROOT),
    "state_data": str(ROOT / "state_data"),
    "memory_store": str(ROOT / "state_data" / "memory_store"),
    "task_store": str(ROOT / "state_data" / "task_store"),
    "content_store": str(ROOT / "state_data" / "content_store"),
    "runtime_store": str(ROOT / "state_data" / "runtime_store"),
    "logs": str(ROOT / "logs"),
    "skills": str(ROOT / "core" / "skills"),
}


MODEL = {
    "default": "minimax-m2.7",
    "temperature": 0.7,
    "max_tokens": 2000,
}


MEMORY = {
    "l3_max": 20,
    "l4_trigger": 1,
    "cache_ttl": 86400,
}


SKILLS = {
    "auto_load": True,
    "learn_threshold": 3,
    "timeout": 30,
}


EVOLUTION = {
    "auto_trigger": 0.1,
    "periodic_runs": 50,
}


LOG = {
    "level": "info",
    "brain_log": True,
    "event_log": True,
    "error_log": True,
}


API = {
    "host": "0.0.0.0",
    "port": 8090,
    "title": "NovaCore",
    "version": "4.0",
}


def get(key):
    for section in [PATH, MODEL, MEMORY, SKILLS, EVOLUTION, LOG, API]:
        if key in section:
            return section[key]
    return None
