NovaCore skill docs use a two-tier layout:

- `.system/<skill-id>/SKILL.md`
  Built-in skills shipped with NovaCore.
- `<skill-id>/SKILL.md`
  User-defined or locally added skills.

The UI reads card title/short description/example prompt from frontmatter
and renders the markdown body as the detail document.

Runtime execution code still lives in `core/skills/`:

- `core/skills/<skill-id>.py`
  Execution logic
- `core/skills/<skill-id>.json`
  Runtime metadata and catalog fields

This keeps skill documents easy to browse at the top level without moving
the existing runtime execution chain.
