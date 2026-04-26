# AaronCore CLI

> Target: AaronCore CLI, a memory-first local agent shell.

The CLI is intentionally thin in the first phase. It does not replace the existing
runtime, memory system, tool-call chain, or desktop wrapper. It talks to the
already-running local backend at `localhost:8090` and streams `/chat` replies back
to the terminal.

```text
terminal input
  -> POST localhost:8090/chat
  -> stream reply text
  -> existing L1-L8 / tool_call / MCP runtime keeps doing the real work
```

## Commands

```powershell
.\aaron.bat
.\aaron.bat run "summarize what we were doing"
.\aaron.bat doctor
.\aaron.bat memory search "CLI direction"
.\aaron.bat logs
```

When the repo root is on `PATH`, the intended command shape is:

```powershell
aaron
aaron run "..."
aaron doctor
aaron memory search "..."
aaron logs
```

## Start Backend

The CLI expects the AaronCore backend to be running first:

```powershell
python agent_final.py
```

Then, in another terminal:

```powershell
.\aaron.bat doctor
.\aaron.bat run "hello"
```

## Phase 1 Boundary

This first version only adds a terminal shell.

- Do not refactor `routes/chat.py`.
- Do not add a new pre-LLM router.
- Do not duplicate memory search as a separate local keyword search system.
- Keep Electron as an optional UI while the CLI path is validated.

## Command Notes

`aaron`

Starts a simple interactive terminal shell.

`aaron run "..."`

Sends one message to `/chat` and streams the response.

`aaron doctor`

Checks `/health` and a few local runtime files.

`aaron memory search "..."`

Asks the existing AaronCore `/chat` tool-call runtime to search memory. The CLI
does not read and rank memory files by itself.

`aaron logs`

Tails local log files from the repo/data directory. Use `--list` to see available
logs and `--lines N` to change the output length.
