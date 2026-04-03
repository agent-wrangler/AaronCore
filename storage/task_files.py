from storage.json_store import load_json, write_json
from storage.paths import TASK_PROJECTS_FILE, TASK_RELATIONS_FILE, TASKS_FILE


def load_task_projects():
    data = load_json(TASK_PROJECTS_FILE, [])
    return data if isinstance(data, list) else []


def save_task_projects(projects):
    write_json(TASK_PROJECTS_FILE, projects if isinstance(projects, list) else [])


def load_tasks():
    data = load_json(TASKS_FILE, [])
    return data if isinstance(data, list) else []


def save_tasks(tasks):
    write_json(TASKS_FILE, tasks if isinstance(tasks, list) else [])


def load_task_relations():
    data = load_json(TASK_RELATIONS_FILE, [])
    return data if isinstance(data, list) else []


def save_task_relations(relations):
    write_json(TASK_RELATIONS_FILE, relations if isinstance(relations, list) else [])
