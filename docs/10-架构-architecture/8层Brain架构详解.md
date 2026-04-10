# 8 层 Brain 架构详解

> 基于代码实际实现整理，非设计文档。最后更新：2026-04-10 03:30
> 重要提示：这份文档保留 8 层记忆系统的分层说明，其中部分 L1-L4 历史描述仍偏设计视角；当前主链请优先阅读根目录 `RUNTIME.md`。本文已按当前代码更新 L5-L8 语义和主要回流口径。

## 架构总览

```
用户输入
  ├─ L1 加载原始对话历史（当前主链实际窗口以代码为准）
  ├─ L2 兼容层（session_context 目前主要保留接口兼容，不再承担主链规则路由）
  ├─ L2/L3/L8 等记忆在当前 tool_call + CoD 主链下以按需拉取为主
  ├─ L3 经历记忆（是否预装以当前主链代码为准）
  ├─ L4 加载人格+用户画像+交互规则（只读 persona.json）
  ├─ L5/L8 以按需注入或工具拉取为主
  ├─ LLM / tool_call 主导是否直接回复或调用工具
  ├─ 执行回复
  │   ├─ tool_call 模式 → tool_adapter / executor / 内部工具执行
  │   └─ 结果回喂 LLM → 继续多轮工具调用或输出最终回复
  └─ 回复后
      ├─ 写回 L1/L2，执行轨迹落到 L6
      ├─ 已验证成功的 L6 run 可上浮为 L5 成功方法经验
      ├─ L7 检测负反馈 → 记录纠偏规则 / 补学线索
      └─ L8 正式知识由对话结晶与自主学习沉淀
```

## 回流机制

1. **L2 中枢分发**：每轮对话评分入库 → 自动结晶到 L3/L4/L7/L8（L8 仍需 `_is_real_knowledge_query()` 二次验证）
2. **执行回流**：技能执行后的 run_event 落到 L6；满足 `success + verified + 无 drift` 时，L6 经验可上浮成 L5 成功方法经验
3. **反馈回流**：用户反馈"不对" → L7 记录纠偏规则；补学仍可触发，但不再自动变成 L8 正式知识卡片
4. **L8 知识闭环**：自主/显式学习或 L2 对话结晶 → 生成可复用知识卡片 → 下次检索命中直接复用

---

## L1 记忆粒子

- 文件：`state_data/memory_store/msg_history.json`
- 加载：`get_recent_messages(history, 6)`
- 作用：存储原始对话消息，给当前对话提供最近上下文
- 自动清理 7 天以上的消息
- 每条消息结构：`{ role, content, time }`
- 这是未经加工的原始素材，L2 从这里提炼

---

## L2 持久记忆中枢

8 层架构的**中枢调度站**，每轮对话都经过 L2 评分，重要信息自动结晶到下游层级。

- 文件：`state_data/memory_store/l2_short_term.json`（记忆存储，不设上限）+ `state_data/memory_store/l2_config.json`（轮次统计）
- 代码：`memory/l2_memory.py`（评分入库 + 关键词检索 + 自动结晶 + 每 20 轮摘要）
- 辅助：`core/session_context.py`（当前主要是兼容占位层，不再承担主链规则路由）

### 评分系统

每轮对话调用 `add_memory(user_input, ai_response)` 评分入库。

`score_importance(text)` 评分规则：

| 分值 | 关键词 | 说明 |
|------|--------|------|
| **0.85（高分）** | 我叫、我在、我住、喜欢、想要、目标、决定、讨厌、记住、偏好、绝对、必须 | 身份/偏好/意愿类 |
| **0.6（中分）** | 在做、项目、开发、研究、计划、AI、产品 | 工作/项目类 |
| **0.25（低分）** | 你好、哈哈、嗯、啊、哦（且文本 < 10 字符时） | 纯寒暄/语气词 |
| **0.5（默认）** | — | 不命中任何关键词 |

入库门槛：**0.35**，低于此分不入库。

### 类型检测 `_detect_type(text)`

| 类型 | 触发关键词 | 结晶去向 |
|------|-----------|---------|
| correction（纠正） | 不对、错了、不好、太短、太长 | → L7 |
| skill_demand（技能需求） | 帮我做、能不能、你会不会 | 保留为信号，但当前不再直接结晶到 L5 |
| knowledge（知识） | 精确短语匹配：什么是、为什么、怎么回事、是谁、什么意思、什么原理等 + `_is_real_knowledge_query()` 二次验证 | → L8 |
| preference（偏好） | 喜欢、偏好、讨厌 | → L4 |
| goal（目标） | 想要、目标、计划 | → L4 |
| fact（事实） | 我叫、我是、我在、我住、人在、定居、坐标 | → L4 |
| rule（规则） | 记住、不要、必须、规则 | → L4 |
| project / decision / general | — | → L3 |

### 检索系统

- `search_relevant(query, limit=8)` — 关键词 + 文本匹配检索
- 评分公式：`final_score = relevance * 0.7 + freshness * 0.3`
- relevance 综合：关键词重叠 / bigram 重叠 / 子串匹配
- freshness：`1.0 / (1.0 + 0.1 * 天数)`
- 检索结果的实际注入位置以当前主链代码为准，优先看 `reply_formatter.py` 与 `routes/chat.py`

### 中枢分发（结晶）

| 目标 | 条件 | 说明 |
|------|------|------|
| **L2 → L3** | 事件/里程碑/决策，imp > 0.7 | 写入 `long_term.json` |
| **L2 → L4** | 用户事实/偏好/规则，imp > 0.7 | 更新 `persona.json` |
| **L2 → L4 城市** | 检测到"我在X""我住X" | **不受分数限制**，直接更新 `user_profile.city` |
| **L2 → L5** | 当前无直接结晶链 | L5 主要改由 L6 成功执行经验上浮 |
| **L2 → L7** | 纠正/不满 | 不要求高分，带上下文推到 `feedback_rules.json` |
| **L2 → L8** | 知识类问答 + `_is_real_knowledge_query()` 二次验证通过 + ai_response > 20 字 | 不要求高分，沉淀到 `knowledge_base.json` |

### 自动维护

- 每 **20 轮**自动生成对话摘要 → 存入 L3（优先用 LLM，fallback 用关键词提取）
- 每 **50 轮**自动清理低价值记忆（分级清理）：
  - 30 天：imp < 0.5 且 hit_count == 0 → 清掉
  - 60 天：imp < 0.5 且 hit_count ≤ 2 → 清掉
  - 90 天：imp < 0.7 且 hit_count ≤ 1 → 清掉
  - 已结晶或 imp ≥ 0.7 的永远保留

### 场景理解（辅助模块）

- 文件：`core/session_context.py`
- 加载：`extract_session_context(history, current_input)`
- 作用：从 L1 原始对话中提炼结构化的短期认知，传给路由 prompt 作为"L2 会话理解"

| 板块 | 字段 | 说明 |
|------|------|------|
| 话题识别 | `topics` | 这轮对话在聊什么（天气/股票/故事/编程/技术/闲聊等） |
| 情绪感知 | `mood` | 用户当前情绪状态（平稳/积极/低落/不满/纠正/感谢） |
| 意图追踪 | `intents` | 用户最近的意图模式链（任务委托→知识提问→延续追问等） |
| 上下文延续 | `follow_up` | 需要接住的线索：故事续写、追问、纠正、重复提问 |

轻量实现：纯规则提取，不调 LLM，不用向量。

---

## L3 经历记忆

- 文件：`state_data/memory_store/long_term.json`
- 加载：`load_l3_long_term(limit=8)`，白名单只加载 `event` / `milestone` / `general` 类型
- 注入方式：最后 N 条**全量塞进** prompt（无检索过滤）
- 作用：让 Nova 记得和用户之间发生过什么，有情感温度的共同经历

### 允许的 type

| 板块 | 说明 | 示例 |
|------|------|------|
| event（事件） | 发生过的重要事件 | "主人说永远记住" |
| milestone（里程碑） | 成长里程碑 | "Nova的成长日记·最温暖的一天" |
| general（未分类） | 未分类的重要时刻 | — |

### 禁止存入的内容

| ❌ 内容 | 正确去向 |
|---------|---------|
| 用户身份/偏好（"彬哥是创业者"） | L4 `user_profile` |
| 交互规则（"不要提晚安""甜心守护直接执行"） | L4 `interaction_rules` |
| 知识内容（"纳瓦尔宝典""短视频理论"） | L8 `knowledge_base.json` |
| 系统架构元数据（"L3自动生成规则"） | 不该存在记忆里 |

---

## L4 人格图谱

- 文件：`state_data/memory_store/persona.json`
- 加载：`load_l4_persona()` — 只读 persona.json，不交叉读其他文件
- 写入：`memory.update_persona()`
- 作用：定义 Nova 的身份、语气、用户画像、交互规则，传给回复生成

### 板块（按 JSON 顶层 key 分）

| 板块 | 说明 |
|------|------|
| persona_state（当前状态） | role、mood（温柔）、energy（稳定） |
| ai_profile（AI 画像） | identity、positioning、self_view、expression、boundary |
| user_profile（用户画像） | identity（"主人叫彬哥，是创业者"）、preference、dislike、city |
| relationship_profile（关系画像） | relationship、interaction_style、goal |
| speech_style（说话风格） | tone（语气词）、particles（语气助词）、avoid（禁用模板句） |
| interaction_rules（交互规则） | "不要提晚安""不要提睡觉""甜心守护触发后直接执行"等 |
| skill_routing（技能触发映射） | 关键词 → skill + exec_func（历史遗留，L5 为主） |

---

## L5 成功方法经验

- 文件：`state_data/memory_store/knowledge.json`
- 加载：`storage/state_loader.load_l5_knowledge()`
- 结构：当前返回 `knowledge.json` 最近 10 条条目 + 已注册技能的轻量元数据（`name` + `keywords`）
- 当前最重要的条目来源：`memory.evolve() -> _maybe_promote_success_path()` 产出的 `source="l6_success_path"`
- 作用：沉淀“什么做法被验证有效”的正向方法经验，供复杂任务与按需上下文复用

### 典型成功经验字段

| 字段 | 说明 |
|------|------|
| `experience_key` | 去重键，通常由技能名 + action/target/outcome 组成 |
| `name` | 展示名，例如 `open_target / open_url / url` |
| `action_kind` / `target_kind` | 行为类型与目标类型 |
| `outcome` / `observed_state` | 结果与观察到的状态 |
| `verification_mode` / `verification_detail` | 如何验证、验证到什么 |
| `summary` / `success_count` | 成功经验摘要与累计命中次数 |

L5 现在回答的是“什么方法成功过”，而不是“当前有哪些技能”。

---

## L6 执行轨迹

- 文件：`state_data/memory_store/evolution.json`
- 加载：`memory.get_evolution()`
- 写入：`memory.evolve(user_input, skill_used, run_event)`
- 作用：记录真实执行事实，是 L5 上浮和后续纠偏分析的素材层

### 板块（按 JSON 顶层 key 分）

| 板块 | 说明 |
|------|------|
| `skills_used` | 聚合统计：`count` / `verified_count` / `failure_count` / `drift_count` / `last_outcome` |
| `skill_runs` | 逐次执行事实：`success` / `verified` / `expected_state` / `observed_state` / `drift_reason` / `repair_hint` / `repair_succeeded` / `verification_mode` / `verification_detail` |

L6 不是 prompt 主体，而是“这次到底怎么跑的”的事实账本。

---

## L7 反馈纠偏

- 文件：`state_data/memory_store/feedback_rules.json`
- 记录入口：`feedback/classifier.py::record_feedback_rule()`
- 主链写回：`routes/chat.py` 回复后调用 `S.l7_record_feedback_v2(...)`
- 作用：记录用户负反馈、失败提醒和纠偏约束，供后续回复少量 relevant 注入

### 当前更准确的理解

| 角色 | 说明 |
|------|------|
| 负向约束 | 告诉系统“别再怎么做” |
| 失败规格 | 记录答偏、走错技能、风格不对等失败信号 |
| 反馈链输入 | 可继续触发补学或修复流程，但自己不是修复状态机 |

每条规则通常包含：`category`、`scene`、`problem`、`fix`、`last_question`、`user_feedback`、`feedback_count`。

`_extract_routing_constraint()` 当前已经退役，所以不要再把 L7 理解成结构化路由表。

---

## L8 已学知识

- 文件：`state_data/memory_store/knowledge_base.json` + `state_data/memory_store/autolearn_config.json`
- 主实现：`memory/l8_learning.py`（`core/l8_learn.py` 只是兼容 shim）
- 搜索：`query_knowledge` / `find_relevant_knowledge()` 按需检索
- 写入：`save_learned_knowledge()`
- 作用：保存真正可复用的事实 / 概念 / 原理 / 方法性知识卡片
- 当前正式入库来源：
  - `auto_learn()` / `explicit_search_and_learn()` 的自主或显式学习
  - `memory/l2_memory.py::_to_l8()` 的对话结晶（`source="l2_crystallize"`）
- `feedback_relearn` 只保留在反馈链路里，不再参与正式检索或时间线展示

### 三层防污染机制

防止闲聊/感叹/评价污染知识库：

| 层级 | 位置 | 作用 |
|------|------|------|
| 第一层 | L2 `_detect_type()` 精确短语匹配 | 只有"什么是""为什么""怎么回事"等明确知识问句才标记为 knowledge |
| 第二层 | L2 `_is_real_knowledge_query()` 二次验证 | 排除闲聊模式（"有意思""不错""哈哈"等）+ 要求包含疑问信号 + 长度 ≥ 6 |
| 第三层 | L8 `should_trigger_auto_learn()` 闲聊排除 | 再次过滤"有意思""好玩""嗯嗯"等口语，防止漏网 |

### 知识凝结流程（LLM 增强）

```
web 搜索结果（原始 snippets）
  → LLM 知识凝结器（提炼 2-3 句中文核心摘要，去广告/无关内容）
  → LLM 关键词提取（从摘要中提取 3-5 个精准中文关键词）
  → 存入知识卡片（query + summary + keywords + 场景分类）
  → 下次同类问题检索命中直接复用
```

- 凝结 prompt：`"你是知识凝结器。用户问了：「{query}」…请用简洁的中文总结核心答案"`
- 关键词 prompt：`"从以下知识摘要中提取 3-5 个最重要的中文关键词"`
- LLM 调用使用独立的 `_knowledge_llm_call()`（max_tokens=300, timeout=15s），比普通 LLM 调用额度更高
- fallback：LLM 不可用时退回原始 snippet 拼接 + 规则关键词提取

### 板块（`一级场景` 字段）

| 板块 | 说明 |
|------|------|
| 自主学习 | 纯知识问答的 web 搜索结果（主要板块） |
| 工具应用 | 技能相关的学习（天气、股票、画图等） |
| 内容创作 | 创作类纠偏经验（笑话、故事等） |
| 系统能力 | 路由调度相关的修正经验 |
| 人物角色 | 人设相关的调整 |
| 系统功能 | 能力和设置相关 |

每条知识包含：query、summary、keywords、一级场景、二级场景、核心技能、hit_count、trigger。上限 500 条。

### 过滤规则

- `type == "feedback_relearn"` 的条目不参与知识检索（`should_surface_knowledge_entry` 返回 False），因为它们的 query/keywords 是用户口语抱怨，不是真正的知识
- `QUESTION_HINTS` 已收紧为精确短语列表（"什么是""是什么""为啥""怎么办"等），不再包含宽泛词

### L2 ↔ L8 闭环

```
用户提问 → L8 检索已学知识
  ├─ 命中 → 注入上下文 → Nova 优先用已学知识回答（不重复搜索）
  └─ 未命中 → auto_learn() 触发
      → Bing 搜索 → LLM 凝结摘要 → LLM 提取关键词
      → 存入知识卡片 → 下次同类问题直接命中复用
```

L2 既是 L8 的原料供应商（结晶知识类对话到 L8），也是 L8 的消费者（检索 L8 知识注入回复上下文）。

---

## 层间关系

| 关系 | 说明 |
|------|------|
| L1 → L2 | L2 从 L1 原始对话中提炼场景理解（session_context） |
| L2 → L3 | 事件/里程碑/决策（imp > 0.7）结晶写入 long_term.json |
| L2 → L4 | 用户事实/偏好/规则结晶写入 persona.json；城市提取不受分数限制 |
| L2 → L5 | 当前无直接结晶链；L5 主要由 L6 成功执行经验上浮 |
| L2 → L7 | 纠正/不满信号带上下文推到 feedback_rules.json |
| L2 → L8 | 知识类问答经二次验证后沉淀到 knowledge_base.json |
| L8 → L2/回复 | L8 知识在每次对话时被检索，命中则注入路由和回复上下文（L2 既供料又消费） |
| L5 ↔ L6 | L6 记录执行事实，满足 `success + verified + 无 drift` 时可把成功路径上浮成 L5 |
| L5 → executor | executor 从 L4 读取用户上下文（如城市），传给技能 execute() |
| L7 → L8 | L7 可触发补学或反馈预览，但 `feedback_relearn` 不再进入 L8 正式知识检索 |

---

## 层级边界速查

```
"用户是创业者"          → L4 user_profile.identity        ✅
"不要提晚安"            → L4 interaction_rules             ✅
"纳瓦尔宝典"            → L8 knowledge_base.json           ✅
"成长日记·最温暖的一天"  → L3 long_term.json (milestone)    ✅
"MCP是什么"             → L8 knowledge_base.json           ✅
"甜心守护直接执行"       → L4 interaction_rules             ✅
"我在常州"              → L2 评分入库 → L4 user_profile.city ✅
"帮我做个XX"            → LLM 直接看 tool list 决定是否调工具；skill_demand 只保留为 L2 signal ✅
"你说错了"              → L2 检测 correction → L7          ✅
"什么是量子计算"         → L2 检测 knowledge → L8          ✅
```
