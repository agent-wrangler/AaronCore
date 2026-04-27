# AaronCore CLI

> Target: AaronCore CLI, a memory-first local agent shell.

The CLI is intentionally thin in the first phase. It does not replace the existing
runtime, memory system, or tool-call chain. It loads the existing runtime in the
same Python process by default and streams chat events back to the terminal
without requiring a localhost server.

```text
terminal input
  -> in-process AaronCore runtime
  -> stream reply text
  -> existing L1-L8 / tool_call / MCP runtime keeps doing the real work
```

## Commands

For normal Windows users, install from PowerShell. There is no desktop `.exe`
package in the mainline; the public path is the CLI installer:

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
aaron setup
aaron qq status
aaron wechat status
aaron social list
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

## First Model Setup

If the opening screen or `aaron doctor` says model setup is needed, run:

```powershell
aaron setup
```

The setup wizard lets the user choose a provider/model, enter an API key with
hidden terminal input, and optionally test the connection. Secrets are saved
through the existing model-config runtime into the local-only config file, not
into tracked public defaults.

Inside the full-screen terminal UI, `/setup` temporarily returns to a normal
terminal prompt for hidden key input, then drops back into AaronCore when the
wizard finishes.

## Terminal UI

`aaron` / `aaroncore` opens an interactive terminal UI by default. The input bar
stays fixed at the bottom, while the conversation, memory/tool progress, and
assistant response stay above it.

If a terminal does not render the UI well, use the simple print-style fallback:

```powershell
aaron --plain
```

## Runtime Startup

`aaron` now loads the local runtime directly in the CLI process. The legacy
localhost HTTP transport is still available for debugging:

```powershell
aaron --transport http
aaron doctor --transport http
```

## Phase 1 Boundary

This first version only adds a terminal shell.

- Do not refactor `routes/chat.py`.
- Do not add a new pre-LLM router.
- Do not duplicate memory search as a separate local keyword search system.
- Keep the CLI direct runtime path as the default user-facing path; use the
  localhost HTTP transport only as a legacy/debug fallback.

## Command Notes

`aaron`

Starts or attaches to the local runtime and opens the interactive terminal shell.

`aaron chat`

Same as `aaron`. This explicit alias exists so the interactive mode is easier to
discover.

`aaron setup`

Runs the terminal model setup wizard. Use this when a fresh install has no API
key yet, or when switching to another provider. The same wizard is available
from inside chat with `/setup`.

`aaron qq`

Shows and manages QQ listening state. QQ monitoring itself should be started
through the normal chat path, for example by saying `帮我监听 QQ 群「群名」` inside
AaronCore. That keeps the request on the existing LLM-led tool-call chain.
Use `aaron qq status` / `/qq status` to inspect listeners, `aaron qq stop` /
`/qq stop` to stop listeners tracked by the current AaronCore process, and
`aaron qq logs` to inspect monitor logs.

`aaron wechat`

Shows and manages WeChat listening state. WeChat monitoring is also started
through the normal chat path, for example by saying `帮我监听微信「聊天名」`.
Use `aaron wechat status` / `/wechat status` or `aaron wx status` to inspect
listeners, `aaron wechat stop` / `/wechat stop` to stop them, and
`aaron wechat logs` to inspect monitor logs.

`aaron social`

Lists or opens social/communication handoff targets. Use `aaron social list` /
`/social list` to see the current platform catalog, or `aaron social open Slack`
to open one platform entry. QQ and WeChat have deeper local messaging/listening
support; the other platforms are browser/app handoff targets, so sending and
posting continue through the normal chat/tool flow.

`aaron mcp`

Opens the terminal MCP manager. It can list configured MCP servers, add a server
manually, search the MCP registry, install a server into local config, connect,
disconnect, or remove saved servers. The same wizard is available from inside
chat with `/mcp`.

`aaron run "..."`

Starts or attaches to the local runtime, sends one message, streams the response,
then returns to the terminal.
Use `aaron` or `aaron chat` for continuous conversation.

`aaron doctor`

Checks runtime health and a few local runtime files.

`aaron memory search "..."`

Asks the existing AaronCore chat/tool-call runtime to search memory. The CLI
does not read and rank memory files by itself.

`aaron logs`

Tails local log files from the repo/data directory. Use `--list` to see available
logs and `--lines N` to change the output length.
