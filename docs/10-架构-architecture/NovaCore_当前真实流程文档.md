# NovaCore 当前真实流程文档

> 最后更新：2026-03-30
> 定位：**当前运行态补充文档**。用于快速理解 NovaCore 现在真正怎么跑。
> 适用场景：以后新对话开始时，如果要碰 NovaCore，建议先读这份，再去看具体代码。
> 说明：遇到和代码不一致时，**以当前代码为准**；遇到和根目录 `CLAUDE.md` 冲突时，优先按代码核对后再判断。

---

## 1. 一句话总览

**NovaCore 当前是真实运行中的 `LLM 主导系统`。**

它的主链不是“规则先分流、LLM 再兜底”，而是：

- 上层：**LLM / tool_call 主导**
- 中层：**L1-L8 记忆系统 + CoD 按需上下文 + 电脑操作底层能力**
- 下层：**技能执行 / 文件 / 应用 / 窗口 / UI / 系统调用**

也就是说：

```text
用户输入
  ↓
LLM 主导（tool_call）
  ↓
首轮看到：真实技能工具 + 记忆工具 / 知识工具 / 搜索工具 / ask_user 等
  ↓
技能层（open_target / app_target / ui_interaction ...）
  ↓
6 层协议底座（感知 / 文件 / 应用 / 窗口 / UI / 编排）
  ↓
操作系统
  ↓
结果回喂 LLM
  ↓
最终回复 + 记忆回写
```

---

## 2. 当前最重要的真实结论

### 2.1 当前主链是 tool_call

`routes/chat.py` 里：

- `routes/chat.py:14` `_get_tool_call_enabled()` 直接返回 `True`
- `routes/chat.py:645` 起，主链进入 `tool_call` 模式
- `routes/chat.py:912` 之后的“非 tool_call 路径”是**已废弃保留代码**，默认不走

所以现在要理解 NovaCore，默认认知应该是：

> **先按 LLM/tool_call 主链理解，别先按旧规则路由理解。**

---

### 2.2 CoD 在 tool_call 模式下自动启用

`routes/chat.py:523`：

- `_use_cod = _use_tool_call`

也就是说只要当前在 tool_call 主链，就默认进入 CoD 思路：

- **只预装最必要的上下文**
- 其余记忆/知识让 LLM 按需调用工具拉取

---

### 2.3 默认自动预加载的核心不是全量记忆，而是 `L1 + L4 + 轻量 L2(session) + 少量 L7`

当前每轮对话默认先装：

- `L1 最近 30 轮原始历史`（加载到 bundle）
- `L4 人格图谱`
- `L2 会话理解`（轻量结构化的 `session_context`，不是 L2 持久记忆全文）
- `L7 经验教训`（少量 relevant rules）
- `dialogue_context`（现在已收口为非重复增量提示）
- `flashback_hint`（命中才有）

这里最容易误解的是 **L2**。

当前默认带进来的不是“L2 持久记忆内容”，而是：

> **L2 的轻量会话理解层（session_context）**

它的作用不是回忆过去，而是给 LLM 一个很便宜的“当前会话态”锚点，主要告诉模型：

- 当前大概在聊什么（topics）
- 用户当前是什么状态（mood）
- 这轮是不是明显承接上一轮（follow_up/intents）

所以这里可以记成一句：

> **当前默认带的 2，不是 L2 记忆，而是 L2 会话态。**

而这些不会默认全量预装：

- L2 持久记忆内容（`l2_memories`）
- L3 经历记忆
- L5 成功执行经验 / 工作方法记忆
- L8 已学知识

这些在 CoD 下主要走按需工具调用。

现在 `dialogue_context` 只保留 3 类增量提示：

- `follow_up_hint`：追问提示
- `reference_hint`：指代/省略提示
- `vision_hint`：视觉提示

它**不再**重复生成：

- 上一轮用户摘要
- 上一轮 Nova 摘要
- 最近几轮对话摘要列表
- 压缩兜底摘要

因此当前边界是：

- **L1 管原始最近对话**
- **dialogue_context 管增量提示**

这是现在非常重要的结构边界。

---

## 3. 当前真实主链：从用户输入到最终回复

## 3.1 入口：`/chat`

文件：`routes/chat.py`

用户消息进入后，大致过程：

1. 读取当前消息、图片、历史
2. 保存当前用户消息到 `msg_history`
3. 加载上下文 bundle
4. 进入 `tool_call` 主链
5. LLM 决定直接回答还是调用工具
6. 工具执行结果回喂 LLM
7. 生成最终回复
8. 回复后写回 L1/L2/L7/L8 等

---

## 3.2 上下文装载阶段

关键代码：`routes/chat.py:526-590`

### 当前会进 bundle 的主要内容

- `l1 = get_recent_messages(..., 30)`
- `l2 = extract_session_context(...)`
- `l4 = load_l4_persona()`
- `l7 = search_relevant_rules(...)`
- `dialogue_context = build_dialogue_context(...)`
- `flashback_hint = detect_flashback(...)`（命中才有）

### CoD 下默认跳过的内容

如果 `_use_cod = True`：

- `l2_memories = []`
- `l3 = []`
- `l5 = {}`
- `l8 = []`

也就是说这些不是预装，而是让模型后面按需调工具取。

---

## 3.3 L1 到底是多少

这里要区分两个层次：

### A. bundle 里先加载 10轮

代码：`routes/chat.py:526`

```python
l1 = S.get_recent_messages(_history_for_context, 10)
```

### B. 真正送给 tool_call LLM 的原始消息窗口是最近 10轮

代码：

- `core/reply_formatter.py:46` `_build_l1_messages(bundle, limit=15)`
- `core/reply_formatter.py:878`

所以当前真实情况是：

> **先加载 L1 最近 10轮到 bundle，再裁成最近 10 轮原始 messages 喂给 tool_call LLM。**

---

## 3.4 L4 怎么进主链

L4 是当前默认强预装层。

代码：

- `routes/chat.py:541` `l4 = S.load_l4_persona()`
- `core/reply_formatter.py:600` CoD prompt 用精简 L4
- `core/reply_formatter.py:665` tool_call prompt 用完整 L4/L4 风格

L4 负责的不是事实检索，而是：

- Nova 是谁
- 用户是谁
- 说话风格是什么
- 交互规则是什么

所以它是当前每轮对话最稳定的一层。

---

## 3.5 dialogue_context 现在怎么进模型

文件：`core/context_builder.py`、`core/reply_formatter.py`

### 现在结构化生成

`core/context_builder.py:213`

返回：

```python
{
  "follow_up_hint": ...,
  "reference_hint": ...,
  "vision_hint": ...,
}
```

### 现在统一渲染

`core/context_builder.py:263` `render_dialogue_context(context)`

### 当前真正注入到主链的位置

- `core/reply_formatter.py:751` tool_call 非流式
- `core/reply_formatter.py:871` tool_call 流式主路径
- `core/reply_formatter.py:380` 普通 chat
- `core/reply_formatter.py:492` 普通 chat 流式

现在它只作为：

> **对话增量提示**

而不再是历史摘要本身。

---

## 3.6 flashback 是什么，和 dialogue_context 的关系是什么

文件：`core/flashback.py`

flashback 的定位不是最近上下文，而是：

> **旧记忆联想提示层**

它会：

1. 看当前用户输入有没有情绪/回忆/模式线索
2. 去搜 L3，必要时搜 L2
3. 如果命中，生成一段可忽略的联想 hint
4. 注入 prompt，让 LLM 自己决定要不要自然地提到

### 和 dialogue_context 的区别

- `dialogue_context`：最近连续性提示（追问 / 指代 / 视觉）
- `flashback`：中远程记忆联想（L2/L3）

### 当前注入点

- `routes/chat.py:595-597` 生成 `flashback_hint`
- `core/reply_formatter.py:657-660` CoD prompt 注入
- `core/reply_formatter.py:719-722` tool_call prompt 注入
- `core/reply_formatter.py:554-557` 普通 chat prompt 注入

所以它和 `dialogue_context` 有关系，但不是同一个东西。

---

## 4. tool_call 主链怎么跑

关键文件：

- `routes/chat.py`
- `core/tool_adapter.py`
- `core/reply_formatter.py`
- `brain/__init__.py`

---

## 4.1 工具列表怎么构建

### 普通技能工具

`core/tool_adapter.py:57` `build_tools_list()`

它会把注册的 skills 转成 OpenAI function calling 风格工具定义。

### CoD 下的附加工具

`core/tool_adapter.py:196` `build_tools_list_cod()`

这里有一个非常重要的当前事实：

> **CoD 首轮就已经直接暴露真实技能工具。`discover_tools` 只是兜底，不是主入口。**

也就是说现在不是：

> `LLM -> discover_tools -> 再发现技能`

而是更接近：

> `LLM -> 直接看到真实技能工具和内部工具 -> 自己决定调用哪个`

在技能工具之外，还会挂：

- `recall_memory`
- `query_knowledge`
- `web_search`
- `self_fix`
- `read_file`
- `list_files`
- `ask_user`

也就是说现在主链不是单纯技能表，而是：

> **技能工具 + 记忆工具 + 搜索工具 + 自修复工具 + 交互暂停工具**

---

## 4.2 tool_call 的执行方式

### 当前主函数

- `core/reply_formatter.py:849` `unified_reply_with_tools_stream()`

### 基本流程

```text
system prompt
+ 对话增量提示（dialogue_context）
+ L1 原始最近对话 messages
+ user prompt
   ↓
第一次 LLM 调用（带 tools）
   ↓
如果不调工具：直接输出回复
如果调工具：执行工具
   ↓
把 tool result 追加到 messages
   ↓
继续多轮 tool_call（最多 20 轮）
   ↓
LLM 停止调工具后输出最终文本
```

### 多轮 tool_call

代码：`core/reply_formatter.py:979`

这点很关键：

> NovaCore 现在不是“单轮 tool_call”，而是**多轮 tool_call 主链**。

---

## 4.3 tool_call 下真正发给 LLM 的是什么

### 非流式 tool_call

`core/reply_formatter.py:740`

顺序大致是：

1. system prompt
2. `dialogue_context` 渲染后的增量提示
3. user prompt

### 流式 tool_call 主路径

`core/reply_formatter.py:869`

顺序大致是：

1. system prompt
2. `dialogue_context` 渲染后的增量提示
3. L1 最近 15 轮原始 messages
4. user prompt

所以当前主链不是“只喂 prompt 文本”，而是：

> **system prompt + 增量提示 + 原始最近对话 + user prompt**

---

## 4.4 结果怎么回写

tool_call 跑完后，当前主链会继续做这些事：

- 写入 L1 历史
- `S.l2_add_memory(msg, response)` 回写 L2
- 检测 L7 反馈
- 必要时触发 L8 自主学习 / 显式学习
- L7 的 `feedback_relearn` 仍会运行，但不再沉淀为 L8 正式知识卡片

关键位置：`routes/chat.py:842-909`

所以 NovaCore 现在是一个真正的闭环：

```text
输入 → 理解 → 工具 → 回复 → 记忆回写 → 下次复用
```

---

## 5. 电脑操作能力现在到底怎么挂在主链下面

这部分最容易误解。

## 5.1 正确理解

电脑操作不是压在 LLM 上面的“总路由器”，而是：

> **LLM 之下的一套通用能力底座**

也就是说：

- 还是 LLM 决定要不要调用电脑操作相关工具
- 电脑操作相关 skill 再往下落到底层协议与系统调用

---

## 5.2 当前真实可达路径

### 当前真正可达的常态主链

```text
LLM 选择 tool_call
  ↓
首轮直接看到真实技能工具（discover_tools 只做兜底）
  ↓
open_target / app_target / ui_interaction / screen_capture / folder_explore / save_export ...
  ↓
executor 统一执行
  ↓
目标解析 / 文件校验 / 应用生命周期 / 窗口管理 / UI 交互 / 修复编排
  ↓
操作系统
```

### 需要特别注意的一点

`routes/chat.py:924` 那段：

- `context_pull 检测 protocol action → 直达派发`

这段代码现在还在，但它位于：

- `routes/chat.py:912` 之后的 **非 tool_call 路径**

而当前：

- `_get_tool_call_enabled()` 返回 `True`

所以现实是：

> **`context_pull` 的那段“协议前置直达派发”代码当前默认不走。**

这意味着：

- 电脑操作底座仍然存在，而且仍然是当前真实能力底座
- 相关协议与 skill 仍然存在
- 但当前常态调用方式是 **LLM 先选工具**，不是 `routes/chat.py` 先规则化协议直达
- 旧的是“协议前置直达派发挂法”，不是“6 层协议底座本身”

这是现在必须牢牢记住的“真实环境”结论。

---

## 5.3 电脑操作 6 层底座（当前建议口径）

现在仍然可以用下面这 6 层理解电脑操作能力，但要记住：

> **它们是 LLM 之下的底座，不是 LLM 之上的总控层。**

### 1. 环境感知层
- 当前窗口/目标/保存状态/系统现状感知
- 相关文件：`core/target_protocol.py`、`core/fs_protocol.py`

### 2. 文件系统协议层
- 文件/目录/制品相关原语
- 相关文件：`core/fs_protocol.py`、`open_target.py`、`save_export.py`、`folder_explore.py`

### 3. 应用生命周期协议层
- 应用启动/关闭/聚焦/校验
- 相关文件：`core/skills/app_target.py`

### 4. 窗口管理协议层
- 最大化/最小化/还原/移动/缩放/焦点
- 相关文件：`core/skills/ui_interaction.py`

### 5. UI 交互协议层
- 点击/输入/快捷键/拖拽/悬停
- 相关文件：`core/skills/ui_interaction.py`

### 6. 执行编排层
- 执行、校验、drift、repair
- 相关文件：`core/executor.py`、`core/fs_protocol.py`

---

## 6. L1-L8 记忆系统在当前主链中的位置

这部分不再重复讲设计历史，只说当前运行态怎么融合。

## 6.1 L1
- 原始历史消息
- bundle 加载最近 30 轮
- tool_call 主链实际喂最近 15 轮原始 messages

## 6.2 L2

当前要把 L2 分成两部分理解：

### A. `session_context`（默认会进主链）

这是当前每轮默认会预装进去的 **轻量会话理解层**。

来源：

- `routes/chat.py:527` `l2 = extract_session_context(...)`
- `core/reply_formatter.py:603-619` CoD prompt 会读取它的 `topics` / `mood`

它不是“回忆过去的内容”，而是给模型一个便宜的当前态标签：

- 现在大概在聊什么
- 用户当前情绪如何
- 这轮是不是承接上一轮

所以这部分最好记成：

> **当前默认带的 2，不是 L2 记忆，而是 L2 会话态。**

### B. `l2_memories`（CoD 下默认不预装）

这部分才是“L2 持久记忆内容”。

代码：

- `routes/chat.py:528` `l2_memories = [] if _use_cod else S.l2_search_relevant(msg)`

也就是说当前 CoD/tool_call 主链里，它默认不进 bundle 主体，而是让 LLM 之后按需调用 `recall_memory` 去拉。

所以当前真实情况可以一句话概括为：

- **L2 会话态：默认带**
- **L2 持久记忆内容：默认按需拉**

## 6.3 L3
- 经历记忆
- CoD 下默认不预装，按需回忆为主

## 6.4 L4
- 人格图谱
- 当前强预装，是最稳定的一层

## 6.5 L5
- 成功执行经验 / 工作方法记忆
- 不再承担“技能列表”职责；当前技能表由 tool list 直接暴露给 LLM
- 旧版 `L2 -> L5` 技能需求链已经退役；当前 L5 主要来自 L6 成功执行经验的沉淀
- 现在更适合沉淀经过验证的成功执行路径，供复杂任务按需召回
- CoD 下默认不预装全量，只在复杂任务/规划层按需读取

## 6.6 L6
- 原始执行轨迹 / 素材层
- 记录真实 tool run 的 success / verified / drift / observed_state 等执行事实
- 它不是 prompt 主体，更像 L5 成功经验和后续 L7 纠偏的源数据层
- 主要在回复后更新，负责留下“这次到底怎么跑的”

## 6.7 L7
- 反馈纠偏规则
- 当前主链会预装少量 relevant rules

## 6.8 L8
- 已学知识
- 定义：真正可复用的知识卡片层，不再混入口语抱怨、对话分析或系统自指内容
- CoD 下默认按需查询，不预装全量
- 当前只有两条正式入库路径：
  - 自主学习：`core/l8_learn.py` 的 `explicit_search_and_learn()` 与 `run_l8_autolearn_task -> save_learned_knowledge()`
  - 对话结晶：`core/l2_memory.py` 的 `_to_l8() -> save_learned_knowledge(source="l2_crystallize")`
- 记忆页中会显示为两类事件：`自主学习` 和 `对话结晶`
- `feedback_relearn` 属于 L7 的补学动作，当前只保留在反馈链路里，不再作为 L8 已学知识入库、检索或展示
- 核心文件与数据：
  - `core/l8_learn.py`
  - `core/l2_memory.py`
  - `memory_db/knowledge_base.json`

---

## 7. 现在最该记住的几个边界

## 7.1 L1 vs dialogue_context

- `L1` = 最近原始对话
- `dialogue_context` = 追问 / 指代 / 视觉增量提示

不要再把 `dialogue_context` 当成“最近对话摘要层”理解。

---

## 7.2 dialogue_context vs flashback

- `dialogue_context` = 最近连续性
- `flashback` = 旧记忆联想

前者短程，后者中远程。

---

## 7.3 LLM 主导 vs 电脑操作底座

- `LLM` = 总控大脑
- `电脑操作 6 层` = 下层通用能力底座

不要反过来理解。

---

## 7.4 设计理想态 vs 当前真实代码态

当前真实代码里：

- LLM/tool_call 主链：**真实可达**
- CoD 自动启用：**真实可达**
- `context_pull` 直达派发：**代码还在，但默认不可达**

这三点必须区分清楚。

---

## 8. 新对话开始时，建议怎么快速读这套系统

如果以后是新会话，建议先按这个顺序读：

### 第一层：总说明
1. 根目录 `CLAUDE.md`
2. 本文：`docs/10-架构-architecture/NovaCore_当前真实流程文档.md`

### 第二层：主链关键文件
3. `routes/chat.py`
4. `core/reply_formatter.py`
5. `core/tool_adapter.py`
6. `brain/__init__.py`

### 第三层：上下文与记忆
7. `core/context_builder.py`
8. `core/flashback.py`
9. `core/l2_memory.py`
10. `core/l8_learn.py`

### 第四层：电脑操作底座
11. `core/fs_protocol.py`
12. `core/target_protocol.py`
13. `core/executor.py`
14. `core/skills/open_target.py`
15. `core/skills/app_target.py`
16. `core/skills/ui_interaction.py`

---

## 9. 以后继续改 NovaCore 时，默认应该带着哪些判断

### 先判断：这是哪一层的问题？
- LLM 主链问题？
- 上下文装载问题？
- 记忆命中问题？
- flashback 联想问题？
- tool_call 工具选择问题？
- 技能本身问题？
- 电脑操作底层问题？

### 再判断：这是当前主链还是历史残留？
尤其要小心：

- `routes/chat.py` 里保留着一些旧分支
- 不是所有看到的代码都在当前主路径上真实运行

### 最后判断：这个改动会不会让 L1、dialogue_context、flashback 重新打架？
这是最近很容易踩的点。

---

## 10. 最终定稿（给未来的 Claude / 未来的新会话）

如果以后只允许记住一句话，那就记这句：

> **NovaCore 当前的真实运行态是：LLM/tool_call 主导，CoD 自动启用，默认预装 L1 + L4 + 少量结构化上下文，其余记忆按需拉取；电脑操作能力是 LLM 之下的通用底座，不是压在 LLM 上面的总控层。**

如果允许记住第二句，再加这句：

> **当前 `dialogue_context` 已经收口成非重复增量提示层，只负责追问、指代、视觉，不再复述最近对话；而 `flashback` 是单独的旧记忆联想层。**
---

## 11. 2026-03-28 新增的底层修正

这一轮更新最重要的不是“又修好了几个场景”，而是把几处真正的底层断点补上了。

### 11.1 6 层底座内部新增：动作结果协议

当前更准确的理解应该是：

- 不是新增第 7 层
- 而是在现有 6 层协议底座内部，补强了统一的“动作结果协议 / 执行闭环协议”

核心落点：

- `core/fs_protocol.py`
- `core/executor.py`
- `core/skills/open_target.py`
- `core/skills/app_target.py`

现在协议层开始统一返回这类结构：

- `action_kind`
- `target_kind`
- `target`
- `outcome`
- `display_hint`
- `verification_mode`
- `verification_detail`

这意味着：

- 技能层不再只是吐一段自由文本
- 执行后“到底是新打开、聚焦现有窗口、恢复最小化、重试成功、还是只触发未确认”这些语义开始统一沉到底层
- 上层步骤展示以后应该优先读这层动作结果，而不是继续猜文案

### 11.2 执行后验证开始真正往协议层收口

昨天已经有 `verify_post_condition(...)`，但之前它更像“存在的能力”，不是“默认生效的闭环”。

当前更接近真实状态的是：

- `executor` 首次执行结果也会统一接协议层后置验证
- 如果有 `drift`，它不再只是某个 skill 私有的小判断
- 动作结果、验证结果、repair 语义开始往同一套 meta 收

### 11.3 MiniMax 空回复的根因不是模型，而是工具回填链断了

这轮最关键的修正之一是：

- 不是“MiniMax 查完工具后懒得回答”
- 而是我们之前在 `brain/__init__.py` 的 `_normalize_openai_messages()` 里，把 `assistant + tool_calls` 那条关键消息吞掉了

结果就是：

1. 工具已经成功执行
2. 第二轮把 `tool_result` 回喂模型
3. MiniMax 找不到对应 `tool id`
4. 接口直接报 `tool result's tool id not found (2013)`
5. 上层才表现成“返回空内容”

所以这次经验很重要：

> **工具已成功但最终回复空掉，优先查 tool-call 回填链，不要先怀疑 LLM 本身。**

### 11.4 客户端壳层现在有单实例锁

之前 Electron 壳没有单实例保护，所以重复启动客户端时，会直接再开一只窗口。

当前已经在：

- `shell/main.js`

补上了单实例锁，逻辑是：

- 第一次启动：正常创建窗口
- 第二次启动：不再新开实例
- 直接恢复并聚焦现有窗口

### 11.5 当前最值得记住的新边界

这一轮之后，更推荐的判断顺序是：

1. 先查当前能力有没有真实暴露给模型
2. 再查 tool_call / tool_result 的协议链有没有断
3. 再查动作是否真的执行成功
4. 最后才考虑兜底体验

也就是说：

> **先修链路，再做兜底。**
