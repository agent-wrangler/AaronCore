# state_data

This directory exists for runtime state, not for shipping a developer's real memory and task history.

For AaronCore public-repo preparation, the rule here is:

**keep structure and templates, keep real truth data local**

## What Stays Public

- directory structure
- `.gitkeep` files
- template files
- safe default configs such as public runtime defaults

## What Stays Local

- real memory contents
- real task state
- real content workflow state
- caches, logs, exports, and debug artifacts
- local secrets and local overrides

## Current Bootstrap Files

Minimal template files are provided for some stores so a clean public repo still has an obvious shape:

- `task_store/tasks.template.json`
- `task_store/task_projects.template.json`
- `task_store/task_relations.template.json`
- `content_store/content_projects.template.json`
- `content_store/content_topic_registry.template.json`

The actual runtime is still free to create its own real state files locally during use.

## Local-Only Examples

Some local-only config examples live outside or alongside this directory:

- `../brain/llm_config.local.example.json`
- `runtime_store/autolearn_config.local.example.json`
- `runtime_store/mcp_servers.example.json`

These are examples only. The real local files should remain untracked.
