# CLAUDE.md

> 最后更新：2026-04-10
> 用途：给默认读取根目录 `CLAUDE.md` 的编码工具一个**薄入口**。
> 重要：**这不是 AaronCore 当前运行态的权威文档。**

## 先看这里

- 当前运行态主链：`RUNTIME.md`
- L1-L8 当前分层语义：`docs/10-架构-architecture/8层Brain架构详解.md`
- 文档导航：`docs/README.md`
- 仓库级硬约束：`AGENTS.md`

文档冲突时的优先级：

1. 代码本身
2. `RUNTIME.md`
3. `docs/10-架构-architecture/8层Brain架构详解.md`
4. `CLAUDE.md`

旧版长文档已归档到：

- `docs/99-归档-archive/根目录历史文档/CLAUDE_旧版手册_2026-04-10.md`

## 项目一句话

AaronCore 是一个以 LLM / native `tool_call` 为主导的桌面 AI 系统。

- 主链入口：`routes/chat.py`
- 回复执行：`core/reply_formatter.py`
- 工具桥接：`core/tool_adapter.py`
- 运行态状态与数据加载：`storage/state_loader.py`
- L2 / L8 记忆主实现：`memory/l2_memory.py`、`memory/l8_learning.py`
- 反馈与修复：`feedback/`

## 硬约束

下面这些约束是当前仓库的默认铁律：

1. 不要在 LLM 决策前插入新层。
2. 不要重排 `routes/chat.py` 的主顺序。
3. 不要重建已有子系统；优先扩展现有实现。
4. 连续性、任务状态、修复状态优先落到现有 runtime state，而不是新 prompt 层。
5. 架构、路由、规划、上下文注入相关改动前，先核对现有代码和 `AGENTS.md`。

## 快速运行

```bash
# backend
python agent_final.py

# desktop
start_nova.bat

# all tests
python -m unittest discover tests/
```

## 最小代码地图

- `routes/chat.py`
  当前 `/chat` 主链，先读它再动架构。
- `core/reply_formatter.py`
  tool_call 主执行循环、prompt 组装、结果回填。
- `core/tool_adapter.py`
  skill -> tool 定义转换、CoD 附加工具。
- `context/chat_context.py`
  dialogue context 与辅助上下文渲染。
- `memory/l2_memory.py`
  L2 评分、结晶、回写。
- `memory/l8_learning.py`
  L8 自主学习、显式学习、知识入库。
- `feedback/classifier.py`、`feedback/loop.py`、`feedback/repair.py`
  L7 反馈、self-repair planning、修复应用。
- `tasks/store.py`
  当前任务状态锚点。

## 代码协作默认规则

- 新 API 路由放进 `routes/`，不要直接堆到 `agent_final.py`。
- 共享状态通过 `core/shared.py` 访问。
- 当前运行态怎么跑，以代码和“当前真实流程文档”为准，不以旧设计稿为准。
- 如果你发现自己在重复写一份“当前主链说明”，优先回链到 `RUNTIME.md`，不要再在这里复制一份。
