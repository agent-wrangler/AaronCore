# Contributing To AaronCore

Thanks for taking an interest in AaronCore.

What makes this project more unusual is its author: someone who could not write a single line of code started AaronCore from zero and pushed it to its current stage within just one month.

Now AaronCore is looking for technical support, collaboration, and shared belief from people who care about the future of agents. If you are interested in memory systems, long-horizon agents, continuity, reasoning, or agent infrastructure, your support may help this direction truly keep moving forward.

This project is not just a generic tool agent. Its core direction is a memory-first agent runtime built for continuity. Because of that, some parts of the codebase are much more sensitive than others.

This document is here to make collaboration easier without losing the core architecture.

## What Helps Most

Good contributions include:

- bug fixes
- tests
- packaging improvements
- desktop polish
- documentation
- tooling and workflow quality
- observability and debugging support
- safe improvements to existing subsystems

## High-Risk Areas

Please be especially careful around:

- `routes/chat.py`
- memory layering and writeback flow
- task continuity and task runtime state
- prompt/context injection
- tool-call main-chain behavior

Changes in these areas can easily damage the core AaronCore experience even when the code looks cleaner on paper.

## Main Architectural Guardrails

These are project rules, not loose preferences.

1. Do not insert a new layer before LLM decision.
   Do not add pre-routing, pre-planning, prompt-time continuity patches, or other new logic before the model has made its own decision.

2. Do not reorder the main sequence in `routes/chat.py`.
   Small local fixes are fine. Structural sequence changes need explicit maintainer approval first.

3. Do not duplicate an existing subsystem.
   Before adding planning, continuity, protocol, or context mechanisms, check whether the repo already has one. Extend the existing layer instead of creating a second one.

4. Do not replace explicit runtime continuity with keyword heuristics.
   Task continuity should remain anchored in runtime state such as task plan, task store, current step, blocker, verification state, and execution results.

## Preferred Contribution Style

- Keep changes scoped.
- Follow existing repo patterns before introducing new abstractions.
- Add tests when touching shared behavior.
- Avoid large refactors unless they are necessary to complete the change safely.
- Explain architectural intent clearly in PR descriptions for sensitive changes.

## Public / Private Boundary

AaronCore is being prepared for a clean public-facing repo shape.

Working rule:

**sync templates, not truth data**

Please do not submit:

- personal memory data
- real task history
- local secrets or keys
- private runtime state snapshots
- backup artifacts created from live use

Templates, defaults, empty state examples, and sanitized fixtures are welcome.

## Before Proposing A Main-Chain Change

If your change touches memory, continuity, routing, or runtime state, please first explain:

1. what exact layer you are changing
2. why the existing subsystem is insufficient
3. why this does not create a parallel mechanism
4. how the change preserves the current main-chain order

This saves a lot of review time.

## Project Status

AaronCore is under active development. Some documentation is still catching up with the code, and some detailed docs are currently in Chinese.

When code and docs disagree, the current code wins.

## License

By contributing to AaronCore, you agree that your contributions will be released under the MIT License used by this repository.
