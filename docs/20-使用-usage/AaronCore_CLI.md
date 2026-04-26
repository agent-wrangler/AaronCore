# AaronCore CLI

> Target: AaronCore CLI, a memory-first local agent shell.

The CLI is intentionally thin in the first phase. It does not replace the existing
runtime, memory system, tool-call chain, or desktop wrapper. It auto-starts or
attaches to the local runtime and streams `/chat` replies back to the terminal.

```text
terminal input
  -> local AaronCore runtime
  -> stream reply text
  -> existing L1-L8 / tool_call / MCP runtime keeps doing the real work
```

## Commands

For normal Windows users, install from PowerShell:

```powershell
irm https://raw.githubusercontent.com/agent-wrangler/AaronCore/master/install.ps1 | iex
```

Open a new terminal, then:

```powershell
aaroncore
```

If you already cloned the repository, run the local installer instead:

```powershell
.\install.bat
```

Open a new terminal, then:

```powershell
aaron
```

or:

```powershell
aaroncore
```

After that, the command shape is:

```powershell
aaron
aaroncore
aaron chat
aaron run "..."
aaron doctor
aaron memory search "..."
aaron logs
```

## Install The Command

Recommended public install:

```powershell
irm https://raw.githubusercontent.com/agent-wrangler/AaronCore/master/install.ps1 | iex
```

This downloads the latest public AaronCore source, creates a local Python
environment under `%LOCALAPPDATA%\AaronCore`, installs CLI dependencies, and adds
`aaron` / `aaroncore` to the current Windows user's PATH.

From a cloned repo root:

```powershell
.\install.bat
```

Open a new terminal, then:

```powershell
aaron
```

or:

```powershell
aaroncore
```

New users do not need to understand `PATH`; they only need to run the installer
once and open a new terminal.

## Runtime Startup

`aaron` now auto-starts the local runtime when the default local backend is not
already running. The localhost HTTP layer still exists internally for phase 1, but
it is no longer a user-facing step.

## Phase 1 Boundary

This first version only adds a terminal shell.

- Do not refactor `routes/chat.py`.
- Do not add a new pre-LLM router.
- Do not duplicate memory search as a separate local keyword search system.
- Keep Electron as an optional UI while the CLI path is validated.
- Hide the local HTTP gateway as implementation detail until the runtime can be
  safely extracted into a direct callable service.

## Command Notes

`aaron`

Starts or attaches to the local runtime and opens the interactive terminal shell.

`aaron chat`

Same as `aaron`. This explicit alias exists so the interactive mode is easier to
discover.

`aaron run "..."`

Starts or attaches to the local runtime, sends one message, streams the response,
then returns to the terminal.
Use `aaron` or `aaron chat` for continuous conversation.

`aaron doctor`

Checks `/health` and a few local runtime files.

`aaron memory search "..."`

Asks the existing AaronCore `/chat` tool-call runtime to search memory. The CLI
does not read and rank memory files by itself.

`aaron logs`

Tails local log files from the repo/data directory. Use `--list` to see available
logs and `--lines N` to change the output length.
