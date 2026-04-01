# Runtime Capability Package

`core/skills/` is the NovaCore runtime capability package.

It is not the canonical skill-doc root. User-facing skill packages and `SKILL.md` files live in `/skills`.

This directory currently contains:

- runtime capability modules (`*.py`)
- runtime capability metadata (`*.json`)
- internal worker scripts under `internal_workers/`
- transient state/config files under `runtime_state/` and `runtime_config/`

Keep user-facing skill docs out of this package. New `SKILL.md` content belongs in `/skills/.system/<skill-id>/` or `/skills/<skill-id>/`.
