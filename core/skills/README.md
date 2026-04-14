# Runtime Capability Package

`core/skills/` is now a compatibility package plus thin wrapper layer.

It is not the canonical skill-doc root. User-facing skill packages and `SKILL.md` files live in `/skills`.

This directory currently contains:

- compatibility shims for native protocol tools that moved to `/tools/agent`
- compatibility shims for built-in workflow/domain skills that moved to `/skills/builtin`
- a package wrapper in `__init__.py` that re-exports the runtime registry API from `/capability_registry`

Keep user-facing skill docs out of this package. New `SKILL.md` content belongs in `/skills/.system/<skill-id>/` or `/skills/<skill-id>/`.
Keep new runtime implementations out of this package as well. New built-in workflow/domain skill code belongs in `/skills/builtin/`.
