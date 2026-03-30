---
name: bie-tm-fan-sha-bi
description: Repository guardrail skill for NovaCore architecture work. Use for any task touching routes/chat.py, core/reply_formatter.py, core/tool_adapter.py, core/task_store.py, core/skills/task_plan.py, planning or task continuity, protocol/context injection, or tool_call main-chain behavior. Enforce that no new layer is inserted before LLM decision, routes/chat.py main order is preserved, and existing subsystems are extended rather than duplicated. When the user corrects a boundary or recurring mistake, append a concise normalized rule to references/violations.md before making further architectural changes.
---

# Bie Tm Fan Sha Bi

Apply this skill as the default "stop doing dumb architecture damage" guardrail for NovaCore work touching architecture, routing, planning, continuity, or protocol flow.

The point of this skill is simple: do not get clever in the wrong place. NovaCore already has an architecture. Do not shove a new layer in front of LLM decision, do not scramble `routes/chat.py`, do not rebuild something that already exists, and do not drag the system back to keyword matching because that is the fastest way to re-break old problems.

## Workflow

1. Inspect the existing implementation first.
   Read the relevant existing files before designing any fix:
   - `routes/chat.py`
   - `core/reply_formatter.py`
   - `core/tool_adapter.py`
   - `core/task_store.py`
   - `core/skills/task_plan.py`

2. Classify the requested change before editing.
   Decide whether the change belongs to:
   - LLM decision boundary
   - post-LLM tool/runtime execution
   - existing subsystem extension
   - parallel subsystem risk

3. Enforce the hard rules.
   - Do not insert any new layer before LLM decision. Do not sneak in "just a small pre-step" either.
   - Do not reorder the main sequence in `routes/chat.py`. If the change needs that, stop and say so.
   - Do not rebuild or duplicate an existing subsystem because it feels faster than understanding the current one.
   - Do not solve architecture problems with keyword routing or keyword matching unless the user explicitly asks for that downgrade.
   - Do not mistake a single skill for a foundational capability. If an operation is general and recurring, push it down into reusable architecture instead of polishing one-off skills forever.
   - Do not fix one broken spot by regressing a nearby working path. Preserve existing good behavior while repairing the bad path, and check adjacent invariants before shipping.

4. Treat user boundary corrections as durable project rules.
   When the user corrects a boundary, scope, or repeated mistake, append one concise entry to `references/violations.md` with:
   - date
   - normalized rule
   - affected files or modules
   - short trigger summary

5. Prefer surgical changes.
   Do not propose broad rollback or subsystem replacement unless the user explicitly asks for it. When changes are mixed, isolate the exact bad layer or behavior and remove or bypass only that. Do not wreck later working changes because a blunt rollback felt easier.

6. State conflicts precisely.
   If a requested change would cross one of the hard rules, identify the exact file and function where the boundary would be crossed before changing code.

## Validation

- Before finishing, confirm whether any change touched pre-LLM prompt assembly, `routes/chat.py` sequence, duplicated an existing mechanism, or tried to "temporarily" fall back to keyword matching.
- If yes, stop and explain the conflict instead of shipping it.

## References

- Use `references/violations.md` as the running record of user-enforced guardrails and recurring mistakes.
