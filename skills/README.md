AaronCore skill docs use a two-tier layout:

- `.system/<skill-id>/SKILL.md`
  Built-in skills shipped with AaronCore.
- `<skill-id>/SKILL.md`
  User-defined or locally added skills.

The UI reads card title/short description/example prompt from frontmatter
and renders the markdown body as the detail document.

Runtime execution is now split by responsibility:

- `tools/agent/<skill-id>.py`
  Agent-callable native tools such as file, shell, desktop, and target actions.
- `tools/agent/<skill-id>.json`
  Runtime metadata for those native tools.
- `skills/builtin/<skill-id>.py`
  Built-in workflow/domain skill implementation for user-visible capabilities.
- `skills/builtin/<skill-id>.json`
  Runtime metadata for those built-in workflow/domain skills.
- `core/skills/<skill-id>.py`
  Compatibility shim that forwards old imports into `tools/agent/` or `skills/builtin/`.

This keeps user-visible skill docs easy to browse at the top level while
letting tool execution code leave `core/`.
