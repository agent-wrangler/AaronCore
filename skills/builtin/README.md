Built-in workflow/domain skill implementations live here.

- `*.py`
  Runtime implementation for built-in user-facing skills.
- `*.json`
  Runtime metadata used by the capability registry and UI catalog.

This directory is the canonical runtime home for built-in workflow/domain skills.
Do not add new implementations under `core/skills/`; keep that package as compatibility only.
