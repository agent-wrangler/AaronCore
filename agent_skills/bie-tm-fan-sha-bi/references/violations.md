# Violations And Guardrails

Keep this file concise. Append new entries; do not rewrite history.

## 2026-03-30

- Rule: Do not insert any new layer before LLM decision.
  Raw: 别TM在 LLM 还没做决策前乱塞新层，别自作聪明。
  Affected: `routes/chat.py`, `core/reply_formatter.py`, planning/continuity injection.
  Trigger: User repeatedly clarified that all new logic must stay after LLM decision.

- Rule: Do not reorder the main sequence in `routes/chat.py`.
  Raw: 别TM把 `routes/chat.py` 主顺序搞乱。
  Affected: `routes/chat.py`.
  Trigger: User reported prior regressions caused by moving planning into the top-level chain.

- Rule: Do not rebuild or duplicate an existing subsystem.
  Raw: 别TM已有体系不用，自己又造一遍。
  Affected: `task_plan.py`, `task_store.py`, `core/reply_formatter.py`, related continuity and planning logic.
  Trigger: User objected to adding new planning/context layers on top of an existing design.

- Rule: Distinguish pre-existing architecture from new additions before explaining ownership or proposing changes.
  Raw: 别TM把原来就有的东西说成你新做的，先分清谁是谁。
  Affected: architecture explanations, planning/context changes.
  Trigger: User objected to incorrect claims about what was newly added versus already present.

- Rule: Prefer surgical removal or bypass over broad rollback when changes are mixed.
  Raw: 别TM一出问题就想整段回滚，把别的正常东西一起搞死。
  Affected: any intertwined architecture or protocol fix.
  Trigger: User rejected rollback because it risks breaking later working changes.

- Rule: Do not fall back to keyword matching for architecture, routing, protocol, or system-capability problems.
  Raw: 别TM总退回 keyword matching，这套系统早就该摆脱关键词路由了。
  Affected: routing, skill triggering, protocol repair, architectural fixes.
  Trigger: User clarified that NovaCore has already moved beyond keyword-hit path routing, and keyword patches pull the system backward.

- Rule: Do not treat individual skills as foundational capabilities; unify common operations into reusable architecture.
  Raw: 别TM把单个技能当底层能力，别把零散技能当成底层核心，我们不可能逐个去设计打磨，必须将所有通用操作统一封装成底层架构能力。
  Affected: skill design, architecture layering, protocol capabilities, reusable operation handling.
  Trigger: User clarified that recurring generic operations must be pushed into底层架构能力 rather than solved one skill at a time.

- Rule: Do not repair one path by breaking another path that was already working; preserve adjacent good behavior when changing protocol or persistence logic.
  Raw: 一天天的，改一个地方，把另外个好的地方丢了。
  Affected: protocol fixes, persistence logic, adjacent behavior invariants, regression control.
  Trigger: User pointed out that a later persistence refactor regressed an already-working `模型思考` history behavior.

## 2026-03-31

- Rule: After a repeated `write_file` missing-`content` failure, do not keep surfacing the same bad call path; force a different next file action or stop cleanly.
  Raw: `write_file` 缺少 `content` 这个错昨天到今天反复出现，不能一直改提示词和补锅，最后还是把同一个失败原样抛回来。
  Affected: `core/reply_formatter.py`, `core/fs_protocol.py`, tool-call runtime retry handling.
  Trigger: User reported the same `write_file` missing-`content` failure recurring across many attempts without a durable runtime fix.
