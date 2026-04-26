# AaronCore 当前系统架构详解

> 最后更新：2026-04-14
> 定位：**当前系统结构总览文档**。用于把当前代码边界、主链分工、状态目录、技能/工具运行时放到一张图里理解。
> 关系说明：
> - 运行时事实优先看根目录 `RUNTIME.md`
> - L1-L8 分层语义细节优先看 `8层Brain架构详解.md`
> - 仓库目录边界优先看 `AaronCore_仓库结构与目录职责.md`
> - 本文不替代代码；遇到和代码冲突时，以当前代码为准

这份文档的目标，是替代继续翻多份旧的 `NovaCore_*架构说明* / *系统说明*` 历史文档来理解当前 AaronCore。

---

## 1. 一句话结论

**AaronCore 当前是一个以 `LLM / native tool_call` 为主导的本地 Agent runtime。**

它的真实主链不是旧时代的“规则先分流、LLM 再兜底”，而是：

```text
aaron / aaroncore CLI
  -> 直接加载 AaronCore runtime
  -> /chat 进入 routes/chat.py
  -> 构建最小必要上下文 bundle
  -> 主 LLM 在同一上下文里决定直接回复或调用工具
  -> tool_adapter / decision.tool_runtime / executor 执行工具
  -> 结果回喂 LLM
  -> 生成最终回复
  -> 写回 state_data 下的 memory_store / task_store / runtime_store
```

如果只记一件事，就记这一条：

> **现在的 AaronCore，应该先按 `routes/chat.py + tool_call` 主链理解，而不是先按旧 `router.py` 时代理解。**

---

## 2. 当前最重要的架构事实

### 2.1 主决策权在 LLM，不在前置规则层

仓库级边界已经很明确：

- 不要在 LLM 决策前插入新层
- 不要重排 `routes/chat.py` 的主顺序
- 连续性、规划、上下文锚点优先落到现有 runtime state，而不是再造平行 prompt 层

这意味着当前架构的基本姿势是：

- **LLM 负责下一步决策**
- **runtime 负责状态锚定、工具执行和结果回写**

### 2.2 `/chat` 是真实主入口

当前聊天主入口在：

- `routes/chat.py`

它负责：

- 接收用户消息
- 读取/更新历史
- 判断 tool_call / CoD 开关
- 组装 bundle
- 驱动主 LLM/tool loop
- 生成 trace / SSE / 最终 reply
- 写回 L1/L2/L7/L8、task runtime、stats 等

### 2.3 当前 repo 的 runtime 真正写到 `state_data/`

很多旧文档还在讲 `memory_db/`，但**当前代码里的主状态目录真源已经是 `state_data/`**。

代码真源在：

- `storage/paths.py`

当前主路径是：

- `state_data/memory_store/`
- `state_data/task_store/`
- `state_data/runtime_store/`
- `state_data/content_store/`

所以现在理解 AaronCore 的状态层时，优先按 `state_data/*` 看，不要再按旧 `memory_db/*` 看。

### 2.4 现在有不少兼容 facade，读代码时要分清“真实现”和“兼容入口”

当前仓库已经做过一轮架构搬迁，所以不少 `core/*` 名字还在，但真实实现已经转移。

最容易混的几个例子：

- `core/reply_formatter.py`
  - 只是兼容 shim，真实实现是 `decision/reply_formatter.py`
- `core/runtime_state/state_loader.py`
  - 只是兼容 shim，真实实现是 `storage/state_loader.py`
- `core/skills/__init__.py`
  - 主要是 capability registry facade，真实 builtin 技能实现在 `skills/builtin/`

这不是坏事，但阅读代码时必须带着这张迁移地图。

---

## 3. 运行时堆栈：从 CLI 到后端

## 3.1 CLI 直接运行链

当前推荐的 Windows 终端入口是：

- `aaron`
- `aaroncore`

这条链路以 CLI 为主入口，默认不经过 localhost 网关：

```text
terminal input
  -> aaron.py
  -> in-process AaronCore runtime
  -> routes/chat.py 的现有 tool_call 主链
  -> 流式终端回复
```

它主要解决：

- 用户只输入 `aaron` / `aaroncore` 就能对话
- 默认只依赖 Python CLI 运行环境，不走本地 HTTP 网关
- 后端 `agent_final.py` 继续作为 API 调试入口保留

## 3.2 Python 后端入口

当前 Python 后端入口是：

- `agent_final.py`

它现在的职责已经比较清晰：

- 初始化 shared/runtime 依赖
- 初始化 memory / feedback / route / reply formatter 等模块
- 创建 FastAPI app
- 挂载静态资源
- `include_router(...)` 挂上 `routes/*`

也就是说，`agent_final.py` **现在更像 app composition root**，而不是继续承担大块业务逻辑。

## 3.3 HTTP / 页面托管

当前页面和资源托管边界是：

- `output.html`：前端页面外壳
- `/static`：静态资源挂载
- `routes/*.py`：API 路由

当前已知关键 route 族包括：

- `routes/chat.py`
- `routes/data.py`
- `routes/settings.py`
- `routes/skills.py`
- `routes/models.py`
- `routes/health.py`
- `routes/lab.py`

---

## 4. 当前主链：`/chat` 到最终回复

这部分只讲现在真正跑的主链，不复述旧 `NovaCore_系统说明.md` 时代的规则分流叙事。

## 4.1 请求进入

用户消息进入 `POST /chat` 之后，`routes/chat.py` 会先做这些事情：

1. 接收文本、图片、UI 语言
2. 先把用户消息记入 history transaction
3. 检查 pending awareness / thinking trace / SSE state
4. 判断当前 tool_call 主链是否可用
5. 判断当前是否启用 CoD

当前 repo 配置里，`state_data/runtime_store/tool_call_config.json` 已经开启：

- `enabled: true`
- `cod_enabled: true`

所以在当前仓库状态下，常态理解就是：

> **tool_call 主链开启，CoD 也开启。**

## 4.2 bundle 装载

当前 bundle 的默认重点不是“全量记忆”，而是“最小必要上下文”。

当前主链优先预装的大致是：

- L1 最近原始对话
- L2 轻量 `session_context`
- L4 人格图谱
- 少量相关 L7 经验规则
- `dialogue_context`
- `flashback_hint`（命中时）

而这些深层内容默认不全量预装：

- L2 持久记忆全文
- L3 经历记忆
- L5 成功方法经验
- L8 知识卡片

它们在当前架构里更多通过工具按需拉取。

## 4.3 tool definitions 装载

当前工具层不是直接在 `routes/chat.py` 里手写，而是通过下面几层拼起来：

- `core/tool_adapter.py`
- `decision/tool_runtime/tool_defs.py`
- `capability_registry/`
- `skills/builtin/`
- `tools/agent/`

这里的分工是：

- capability registry 负责“仓库里有哪些能力”
- tool adapter 负责“这些能力怎样暴露成 LLM 可调用工具”
- decision.tool_runtime 负责“这次 tool_call turn 怎样执行、修复、重试、收尾”

## 4.4 主 LLM / tool loop

当前 tool_call 主循环的核心实现，应按下面这组边界理解：

- `decision/reply_formatter.py`
- `decision/tool_runtime/`
- `core/tool_adapter.py`

它们一起负责：

- 构建 system/user/tool messages
- 调用 LLM
- 解析 tool_call
- 修正参数/路径/协议上下文
- 执行工具
- 把执行结果回喂给 LLM
- 决定结束、重试、补充说明或要求用户确认

这里最重要的变化是：

> **“选择工具”和“生成回复”已经在同一个主 LLM 循环里了。**

这就是为什么旧 `NovaCore_任务1_统一技能主链路实施清单.md` 那种“router -> executor -> think”结构，今天只能当历史材料看。

## 4.5 工具执行与协议层

当前工具执行层不是一个扁平 executor，而是多层配合：

- `core/executor.py`
- `tools/agent/*`
- `protocols/*`
- `decision/tool_runtime/protocol_context.py`
- `decision/tool_runtime/file_targets.py`
- `decision/tool_runtime/dispatcher.py`

这层的职责是：

- 真正调用本地协议工具
- 处理文件/目录/应用/窗口/UI/网络等目标
- 把用户输入补成结构化工具参数
- 维护本轮 protocol context
- 记录成功/失败/漂移/验证信息

## 4.6 closeout 与 post-reply

主 LLM 输出最终回复之后，还要经过一层显式收尾：

- `routes/chat_reply_closeout.py`
- `routes/chat_post_reply.py`
- `routes/chat_run_helpers.py`

这一层负责：

- 用户可见回复的最终整理
- run_event 构建
- task_plan / runtime state 写回
- history / stats / companion reply 状态持久化
- deferred post-reply tasks

---

## 5. 代码目录分工：当前应该怎么读仓库

## 5.1 `routes/`：编排层

`routes/` 负责 FastAPI route 及主链编排，不是底层协议实现。

对架构阅读最关键的几个文件：

- `routes/chat.py`：主聊天链
- `routes/chat_*`：把主链拆成 trace、closeout、stream、task-plan、tool gate 等局部职责

如果你要判断“这轮请求到底怎么流转”，先看这里。

## 5.2 `decision/`：主决策与 tool runtime

`decision/` 是当前很关键的一层。

它主要承接了旧时代散落在 `core/router.py`、`reply_formatter.py`、路由 prompt、tool 重试逻辑里的主决策能力。

尤其是：

- `decision/reply_formatter.py`
- `decision/reply_prompts.py`
- `decision/reply_hygiene.py`
- `decision/tool_runtime/*`

如果你要判断“LLM 这轮为什么这样选工具、怎么修参数、怎么处理失败”，核心答案在这里。

## 5.3 `core/`：协议、桥接、兼容入口、运行时 glue

现在的 `core/` 已经不是“所有真实实现都在这里”的意思了。

它更像：

- 协议层
- 兼容 facade
- 运行时 glue
- 一些仍未迁出的核心模块

当前读 `core/` 时要特别注意：

- 有些是真实现
- 有些只是 shim / facade
- 不要看到文件名在 `core/` 就默认它仍是唯一真源

## 5.4 `storage/`：当前状态与文档索引真源

`storage/` 是当前状态目录、文档索引、history/stats/task file 读写的重要真源之一。

其中最关键的是：

- `storage/paths.py`
- `storage/state_loader.py`

如果你要判断“状态目录到底在哪、docs 索引怎么扫、history/stats 真正落哪里”，先看这层。

## 5.5 `memory/`：L2/L8 主实现和记忆 facade

`memory/` 现在不是单纯 legacy 残留，它里面有当前仍然重要的真实现：

- `memory/l2_memory.py`
- `memory/l8_learning.py`
- `memory/history_recall.py`
- `memory/flashback.py`
- `memory/l2/*`
- `memory/l8/*`

也就是说：

- 记忆的顶层 facade 还保留旧接口风格
- 但 L2 / L8 的主实现已经在 `memory/` 里拆得更细

## 5.6 `tasks/`：任务计划、连续性、工作状态锚点

当前任务系统的关键点，不是“prompt 里讲了个计划”，而是：

**任务状态有独立 runtime substrate。**

核心目录是：

- `tasks/`
- `state_data/task_store/`

关键模块包括：

- `tasks/plan_runtime.py`
- `tasks/continuity.py`
- `tasks/store.py`
- `tasks/task_plans.py`
- `tasks/fs_targets.py`

这层负责：

- task_plan 规范化
- continuity / follow-up / referential query 识别
- 显式 blocker / verification / next_action / fs_target 锚定

这也是为什么仓库级约束一直强调：

> **continuity 必须 state-driven，不要再造平行 keyword continuation 层。**

## 5.7 `skills/`、`tools/agent/`、`capability_registry/`

这是当前最容易混的另一组边界。

### `capability_registry/`

负责能力发现、注册、分类、暴露范围和目录装载。

当前会加载的原生能力主要来自：

- `tools/agent/`
- `skills/builtin/`

### `skills/builtin/`

这里是 builtin workflow / domain skill 的**规范运行时位置**。

### `core/skills/`

当前主要是兼容入口，不应该再当作新的真实实现落点。

### `tools/agent/`

这里更偏 agent-callable native tools / protocol tools。

如果你要判断“这个能力是 workflow skill、domain skill，还是 protocol tool”，就应该顺着 capability registry 的分类去看，而不是只看文件在哪个目录。

---

## 6. 当前状态目录：怎么理解 `state_data/`

当前代码里的主状态目录分成 4 类：

### 6.1 `state_data/memory_store/`

主要放：

- `msg_history.json`
- `persona.json`
- `knowledge.json`
- `knowledge_base.json`
- `long_term.json`
- `l2_short_term.json`
- `evolution.json`
- `feedback_rules.json`

它负责：

- 对话历史
- 人格/用户画像
- L2/L3/L4/L5/L6/L7/L8 相关主状态

### 6.2 `state_data/task_store/`

主要放：

- `tasks.json`
- `task_projects.json`
- `task_relations.json`

它负责：

- 当前任务状态
- 项目/任务关系
- continuity / task_plan 的显式锚点

### 6.3 `state_data/runtime_store/`

主要放：

- `tool_call_config.json`
- `autolearn_config.json`
- `chat_config.json`
- `self_repair_reports.json`
- `skill_store.json`
- `mcp_servers.json`

它负责：

- 运行期开关
- 自动学习配置
- skill / MCP / self-repair / lab 等运行时控制状态

### 6.4 `state_data/content_store/`

主要放内容工作流相关状态，比如 story/content topic/project。

---

## 7. L1-L8 在当前架构里的正确位置

当前 L1-L8 仍然是理解系统结构的重要视角，但不能再把它误读成“每层都强制串行过一遍的流水线”。

更准确的理解应该是：

- L1-L4：当前主链里更常驻
- L2/L3/L5/L8：在 CoD + tool_call 下更多是按需拉取或条件注入
- L6：执行事实账本
- L7：负反馈与纠偏规则层

所以今天读 L1-L8，更像是在读：

- **语义分层**
- **状态分层**
- **回流分层**

而不是在读一条强同步执行管线。

专题细节请单独看：

- `8层Brain架构详解.md`

---

## 8. 当前架构的关键边界

## 8.1 不要再按旧 `NovaCore` 文档的名字理解当前系统

归档里那些 `NovaCore_架构说明.md`、`NovaCore_系统架构说明_新版.md`、`NovaCore_系统说明.md` 仍然有历史参考价值，但它们对应的是：

- 旧目录布局
- 旧 skill routing 语义
- 旧 `memory_db/` 叙事
- 旧 “router -> executor -> think” 主链时代

今天继续看它们，只适合追历史，不适合理解当前实现。

## 8.2 不要在 `routes/chat.py` 前再补一个平行总控层

这既是仓库硬约束，也是当前代码结构的现实需要。

如果以后继续改架构，优先挂点应该是：

- `routes/chat.py` 现有编排节点
- `decision/tool_runtime/*`
- `tasks/*`
- `storage/*`

而不是再发明一个前置 mega-router。

## 8.3 continuity / task_plan / fs_target 必须继续留在显式 runtime state 里

当前任务连续性已经不是一句“继续上次那个”那么简单，而是依赖这些显式状态：

- task_plan
- verification
- blocker
- next_action
- fs_target
- last executed action

所以这条线应该继续 state-driven，不要退回 prompt-time keyword heuristics。

---

## 9. 建议的阅读顺序

如果你是第一次重新理解 AaronCore，建议按这个顺序：

1. `RUNTIME.md`
2. `docs/10-架构-architecture/AaronCore_当前系统架构详解.md`（本文）
3. `docs/10-架构-architecture/8层Brain架构详解.md`
4. `docs/10-架构-architecture/AaronCore_仓库结构与目录职责.md`
如果你是在追历史，再回头看：

- `docs/99-归档-archive/*`

更长的根目录历史长文已经移出当前仓库公开面，不再随仓库分发。

---

## 10. 一句话收口

**AaronCore 当前的真实结构，可以概括为：`routes/chat.py` 编排、`decision/` 决策、`tool_adapter + capability_registry` 暴露能力、`memory/ + tasks/ + storage/` 提供状态锚点、`state_data/` 作为主数据根。**

这比旧 `NovaCore` 时代更接近一个：

**LLM 主导、runtime 锚定、工具按需调用、状态显式落盘的本地 agent runtime。**
