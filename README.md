# AaronCore

AaronCore is a memory-first agent project.

It explores how understanding, continuity, and action can grow from memory. The goal is to help agents move beyond isolated, one-off responses and develop a more persistent, coherent sense of progress through memory.

Technical support and thoughtful collaboration are warmly welcome.

## What AaronCore Is Trying To Do

Most agent systems are good at one or more of these:

- tool execution
- workflow orchestration
- retrieval
- note-style memory

AaronCore is aimed at a slightly different target:

- single-window continuity
- layered memory that participates in the current turn
- persistent persona and user relationship state
- task state that is being connected into the same runtime substrate

The goal is not only "an agent that can do things", but "an agent that does not reset into a stranger every turn".

## Core Direction

AaronCore currently follows these design ideas:

1. LLM-led main chain
2. memory as runtime substrate, not an optional add-on
3. explicit task state instead of purely prompt-time continuation tricks
4. on-demand knowledge retrieval instead of blindly preloading everything
5. a desktop runtime around a Python backend

## Architecture Snapshot

AaronCore uses a layered memory model internally.

- `L1` recent raw dialogue
- `L2` persistent memory and session understanding
- `L3` shared experience / long-term event memory
- `L4` persona, user profile, interaction rules
- `L5` reusable successful methods
- `L6` execution traces
- `L7` feedback and correction rules
- `L8` learned knowledge

In the current main chain, the runtime loads a lightweight working context first, then lets the model decide whether it should answer directly or pull additional memory / knowledge / tools on demand.

This makes AaronCore different from systems that mainly depend on re-reading memory documents into a fresh conversation window.

## Current State Of The Repo

This repository is the active AaronCore development workspace.

Right now it is still closer to a real working repo than a polished public open-source release:

- the architecture is real
- the runtime is real
- the documentation is being cleaned up
- the public/private boundary is still being prepared

That means the codebase already reflects the actual direction, but the packaging and open-source surface are still being organized.

## Entrypoints

Current local entrypoints in this repo:

- `start_aaroncore.bat` - current local desktop launch script in this workspace
- `agent_final.py` - Python backend entrypoint
- `desktop_runtime_35/` - Electron desktop wrapper and packaging runtime
- `website/official/` - static official site source

The desktop/runtime surface is still being organized, and packaging details may continue to evolve as the public release matures.

## Official Site

The static official site lives in `website/official/`.

- local preview: `cd website/official` then `python -m http.server 8080`
- current tracked workflows: `.github/workflows/ci.yml`, `.github/workflows/release-desktop.yml`

There is currently no site deployment workflow checked into `.github/workflows/`. Add a separate deploy workflow later if the public site needs automated publishing.

## Local Config Overrides

Public-safe defaults live in tracked files. Local secrets and machine-specific settings should live in local-only override files.

Examples included in this repo:

- `brain/llm_config.local.example.json`
- `state_data/runtime_store/autolearn_config.local.example.json`
- `state_data/runtime_store/mcp_servers.example.json`

These example files are here to show the expected shape. The real local files should stay untracked.

## Bootstrapping A Clean Checkout

If this repo is used as a future clean public checkout, the local setup flow should look like this:

1. Keep tracked defaults as they are.
2. Copy local-only examples into real local files on your own machine:
   - `brain/llm_config.local.example.json` -> `brain/llm_config.local.json`
   - `state_data/runtime_store/autolearn_config.local.example.json` -> `state_data/runtime_store/autolearn_config.local.json`
   - `state_data/runtime_store/mcp_servers.example.json` -> `state_data/runtime_store/mcp_servers.json`
3. Fill in your own local API keys and machine-specific settings.
4. Let AaronCore create real runtime state files locally during use.

For public-repo hygiene, templates and defaults should be committed, while personal truth data should remain local.

## Quick Start

For a clean local checkout today, assume:

- Python 3.11+
- Node.js 20+
- Windows for the desktop wrapper path

Then:

1. Copy the local example configs into real local-only files:
   - `brain/llm_config.local.example.json` -> `brain/llm_config.local.json`
   - `state_data/runtime_store/autolearn_config.local.example.json` -> `state_data/runtime_store/autolearn_config.local.json`
   - `state_data/runtime_store/mcp_servers.example.json` -> `state_data/runtime_store/mcp_servers.json`
2. Fill in your own local API keys and machine-specific settings.
3. Install the desktop wrapper dependencies:
   - `cd desktop_runtime_35`
   - `npm install`
4. Return to the repo root and start AaronCore:
   - `start_aaroncore.bat`

If you only want the public site locally:

- `cd website/official`
- `python -m http.server 8080`

## Read This First

If you want the most accurate picture of how AaronCore currently runs, start here:

- [RUNTIME.md](RUNTIME.md)
- [Docs Index](docs/README.md)
- [8-Layer Brain Architecture](docs/10-架构-architecture/8层Brain架构详解.md)
- [Open-Source Prep Draft](docs/30-开源-open-source/AaronCore_开源整理草案.md)
- [state_data Public Boundary](docs/30-开源-open-source/AaronCore_state_data_public_boundary.md)

Code remains the final source of truth.

## Open-Source Direction

AaronCore is being prepared for a clean public version.

The working rule is:

**sync templates, not personal truth data**

That means a public AaronCore repo should eventually contain:

- clean runnable code
- templates and defaults
- public docs
- contribution boundaries

And it should not contain:

- real personal memory data
- real task history
- local secrets
- private runtime truth state

## Why This Repo Exists

AaronCore grew out of dissatisfaction with agents that feel capable but discontinuous.

The project is trying to push on a narrower question:

What happens when memory is treated as the starting point of understanding, continuity, and action?

## Notes

- Detailed internal docs are currently more complete in Chinese.
- The codebase is evolving quickly.
- Main-chain boundaries matter here; changes around memory, continuity, routing, and runtime state should be handled carefully.

## License

This project is released under the MIT License.

See [LICENSE](LICENSE).
