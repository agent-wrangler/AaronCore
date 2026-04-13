# AaronCore state_data 公开边界清单

最后更新：2026-04-14

这份清单把 `state_data/` 里当前真实存在的内容分成三类：

1. 必须留在私有开发仓的真值
2. 可以在公开仓保留模板或默认值的内容
3. 历史兼容或运行产物，应该逐步退出公开面

## 当前规范路径

以当前代码为准，`storage/paths.py` 里定义的主状态目录是：

- `state_data/memory_store/`
- `state_data/task_store/`
- `state_data/content_store/`
- `state_data/runtime_store/`

其中：

- `PRIMARY_STATE_DIR = state_data/memory_store`
- `TASK_STORE_DIR = state_data/task_store`
- `CONTENT_STORE_DIR = state_data/content_store`
- `RUNTIME_STORE_DIR = state_data/runtime_store`

因此，公开仓边界应优先围绕这四个目录设计，而不是围绕早期遗留的顶层 `state_data/*.json` 文件设计。

## 一条总原则

**结构可以公开，真值不要公开。**

更具体一点：

- 字段结构、空模板、默认配置，可以公开
- 真实记忆、真实任务、真实历史、真实个人化配置，不应该公开

## 1. memory_store

目录：`state_data/memory_store/`

这是 AaronCore 最敏感的一层，默认应视为**私有真值区**。

### 默认不进入公开仓真值集

- `msg_history.json`
- `l2_short_term.json`
- `l2_config.json`
- `long_term.json`
- `persona.json`
- `knowledge.json`
- `knowledge_base.json`
- `feedback_rules.json`
- `evolution.json`
- `growth.json`
- `topic_summary.json`
- `conversation_history.txt`
- `long_term_legacy_skill_logs.json`
- 所有 `backup` / `bak` 文件

### 公开仓建议保留的形式

- 空模板
- 示例结构
- 脱敏样例

不建议直接保留开发者本人真实运行沉淀出来的内容。

## 2. task_store

目录：`state_data/task_store/`

这里记录的是显式任务连续性，天然就是**运行时真值**。

### 默认不进入公开仓真值集

- `tasks.json`
- `task_projects.json`
- `task_relations.json`

### 公开仓建议保留的形式

- 空数组 / 空对象模板
- 最小演示样例
- 结构说明文档

## 3. content_store

目录：`state_data/content_store/`

这层是内容工作区状态，属于**半结构化真值区**。

### 默认不进入公开仓真值集

- `content_projects.json`
- `content_topic_registry.json`
- `story_state.json`

### 公开仓建议保留的形式

- 演示项目模板
- 示例内容状态模板
- 明确标注为 sample / demo 的样例数据

## 4. runtime_store

目录：`state_data/runtime_store/`

这一层不是统一处理，应该拆成两种：

### A. 可以保留公开默认值的内容

这些文件更适合“公开默认配置 + 本地覆盖”：

- `autolearn_config.json`
- `tool_call_config.json`

未来如果需要，也可以把部分公共配置改成：

- `*.example.json`
- `*.template.json`

### B. 应视为私有运行真值或缓存的内容

默认不进入公开仓真值集：

- `autolearn_config.local.json`
- `chat_config.json`
- `file_export_state.json`
- `mcp_servers.json`
- `mcp_registry_cache.json`
- `qq_monitor_state.json`
- `query_cache.json`
- `self_repair_reports.json`
- `skill_store.json`
- `stats.json`
- 所有 debug log
- `tts_cache/`
- `lab/` 下运行结果文件

这些内容不是公开能力的一部分，而是某次本地运行留下的真实痕迹。

## 5. 顶层 state_data 遗留文件

当前仓库里还有一些顶层 `state_data/*.json` 文件，它们更像历史兼容层或旧路径遗留：

- `state_data/autolearn_config.json`
- `state_data/conversation_history.txt`
- `state_data/l2_config.json`
- `state_data/l2_short_term.json`
- `state_data/msg_history.json`
- `state_data/stats.json`

公开仓不应该继续把这些文件当成主结构的一部分。

更合理的方向是：

1. 以四个规范子目录为准
2. 顶层遗留文件逐步只留兼容，或者完全退出公开面

## 公开仓目标形态

更适合公开仓的 `state_data/` 形态应接近这样：

```text
state_data/
  .gitkeep
  memory_store/
    .gitkeep
  task_store/
    .gitkeep
  content_store/
    .gitkeep
  runtime_store/
    autolearn_config.json
    tool_call_config.json
    .gitkeep
```

如需演示数据，建议用单独命名的样例文件，而不是直接提交真实运行文件。

例如：

- `persona.template.json`
- `tasks.template.json`
- `content_projects.sample.json`
- `mcp_servers.example.json`

## 当前仓库需要继续做的事

这份清单只是边界说明，不代表当前 git 已经完全干净。

后续还需要继续做：

1. 把仍被跟踪的真值文件逐步改为模板或从索引中移除
2. 用 `.gitignore` 挡住明确的运行产物和缓存
3. 为真正要公开的配置补模板文件
4. 保证私有开发仓继续保留真实状态，不影响日常使用

## 当前结论

对 AaronCore 来说，真正应该公开的是：

- 代码
- 结构
- 默认值
- 模板
- 文档

不应该公开的是：

- 开发者本人的记忆
- 开发者本人的任务链
- 开发者本人的真实运行状态

这不是“删除记忆系统”，而是把**模板**和**真值**拆开。
