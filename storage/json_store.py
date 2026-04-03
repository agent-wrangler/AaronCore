# json_store - 公共 JSON 读写
# 消除 agent_final / l8_learn / self_repair 三处重复

import json
from pathlib import Path


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_store(primary: Path, legacy: Path, default):
    if primary.exists():
        return load_json(primary, default)
    if legacy.exists():
        data = load_json(legacy, default)
        try:
            write_json(primary, data)
        except Exception:
            pass
        return data
    return default
