This folder stores the old top-level `skills/` Python package that predated
the current NovaCore skill catalog.

It is kept only for historical reference. The active layout is now:

- `skills/.system/<skill-id>/SKILL.md`
  Built-in skill documents
- `skills/<skill-id>/SKILL.md`
  User skill documents
- `core/skills/<skill-id>.py`
  Runtime execution logic
- `core/skills/<skill-id>.json`
  Runtime metadata
