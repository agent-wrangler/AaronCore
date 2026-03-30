# NovaCore Agent Constraints

These constraints are hard project rules for any new coding conversation in this repository.

## Main Chain Constraints

1. Do not insert any new layer before LLM decision.
   This includes pre-routing, pre-planning, pre-injected task continuity, pre-decision context adapters, or any other new flow placed before the LLM has made its own tool or routing decision.

2. Do not reorder the main sequence in `routes/chat.py`.
   Small localized fixes are allowed only if they preserve the existing order. Any structural change to the main chain requires explicit user approval first.

3. Do not rebuild or duplicate an existing subsystem.
   Before adding any new planning, continuity, routing, protocol, or context mechanism, first check whether the repository already has that subsystem. Extend the existing design only when explicitly requested and only after confirming the exact boundary.

## Specific NovaCore Interpretations

- `task_plan`, task continuity, and similar capabilities must not be reimplemented as parallel systems.
- If a feature already exists in `task_plan.py`, `task_store.py`, `reply_formatter.py`, or related architecture files, do not create a second overlapping layer.
- Fix protocol and execution-chain gaps at the correct existing layer instead of adding prompt-time or keyword-based patches.
- Do not fall back to keyword routing for architecture or system-capability problems unless the user explicitly asks for that approach.

## Working Rule

When the user gives architectural boundaries, treat them as binding constraints, not suggestions. If a requested change appears to conflict with an existing implementation, identify the exact files first and ask before introducing a new layer.

## Default Skill

For work in this repository touching architecture, routing, planning, continuity, protocol/context injection, or tool-call main-chain behavior, always apply the installed skill `$bie-tm-fan-sha-bi` as a default guardrail.

When the user adds a new architectural boundary or repeats a correction, append one concise entry to the skill's `references/violations.md` record before making further architecture changes.

The repository mirror for this skill lives at [agent_skills/bie-tm-fan-sha-bi/SKILL.md](/c:/Users/36459/NovaCore/agent_skills/bie-tm-fan-sha-bi/SKILL.md).
