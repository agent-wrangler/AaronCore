# 8 层 Brain 架构详解

> 基于代码实际实现整理，非设计文档。最后更新：2026-03-16 16:20
> 重要提示：这份文档主要保留 8 层记忆系统的分层说明，其中包含较早时期的路由表达。理解当前真实运行链路时，请优先阅读 `NovaCore_当前真实流程文档.md`，不要再按“先路由、再技能、最后 LLM 兜底”的旧模型理解主链。

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
      ├─ L2 评分入库 → 自动结晶分发到 L3/L4/L5/L7/L8（L8 需通过二次验证）
      ├─ L7 检测负反馈 → 记录纠偏规则 → 触发 L8 补学
      └─ L8 闭环：未命中时触发 auto_learn → web 搜索 → LLM 凝结摘要+精准关键词 → 沉淀知识卡片 → 下次同类问题直接命中复用
```

## 回流机制

1. **L2 中枢分发**：每轮对话评分入库 → 自动结晶到 L3/L4/L5/L7/L8（L8 需通过 `_is_real_knowledge_query()` 二次验证）
2. **回答后回流**：用户反馈"不对" → L7 检测 → L8 搜索 → 知识沉淀
3. **技能失败回流**：技能执行失败 → L7 检测 → L8 找备用方案
4. **L8 知识闭环**：学到知识 → LLM 凝结成中文摘要 → 精准关键词双重提取 → 存入知识卡片 → 下次检索命中直接复用

---

## L1 记忆粒子

- 文件：`memory_db/msg_history.json`
- 加载：`get_recent_messages(history, 6)`
- 作用：存储原始对话消息，给当前对话提供最近上下文
- 自动清理 7 天以上的消息
- 每条消息结构：`{ role, content, time }`
- 这是未经加工的原始素材，L2 从这里提炼

---

## L2 持久记忆中枢

8 层架构的**中枢调度站**，每轮对话都经过 L2 评分，重要信息自动结晶到下游层级。

- 文件：`memory_db/l2_short_term.json`（记忆存储，不设上限）+ `memory_db/l2_config.json`（轮次统计）
- 代码：`core/l2_memory.py`（评分入库 + 关键词检索 + 自动结晶 + 每 20 轮摘要）
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
| skill_demand（技能需求） | 帮我做、能不能、你会不会 | → L5 |
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
| **L2 → L5** | 技能需求信号 | 不要求高分，记录到 `knowledge.json` |
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

- 文件：`memory_db/long_term.json`
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

- 文件：`memory_db/persona.json`
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

## L5 技能矩阵

- 文件：`memory_db/knowledge.json`
- 加载：`load_l5_knowledge()`
- 写入：`memory.evolve()` 更新使用次数
- 作用：记录已注册技能的场景分类和触发词，传给路由判断

### 当前已注册技能

| 一级场景 | 二级场景 | 核心技能 | 触发词 |
|----------|----------|----------|--------|
| 工具应用 | 天气查询 | weather | 天气、气温、温度、下雨、晴天 |
| 工具应用 | 股票查询 | stock | 股票、股价、A股、美股、大盘、行情、指数 |
| 工具应用 | 新闻聚合 | news | 新闻、头条、今日新闻、热点 |
| 工具应用 | 编程游戏 | run_code | 做个游戏、写个游戏、小游戏、贪吃蛇、俄罗斯方块 |
| 内容创作 | 故事创作 | story | 故事、讲故事、讲个 |
| 内容创作 | 写文章 | article | 写文章、写篇、文章 |
| 内容创作 | AI画图 | draw | 海报、画图、生成图片、做图、AI画图 |

每条还包含：辅助技能、应用示例、使用次数、最近使用时间。

---

## L6 技能执行追踪

- 文件：`memory_db/evolution.json`
- 加载：`memory.get_evolution()`
- 写入：`memory.evolve()`（每次技能执行后自动调用）
- 作用：追踪技能使用频率和用户偏好趋势

### 板块（按 JSON 顶层 key 分）

| 板块 | 说明 |
|------|------|
| skills_used（技能使用统计） | 每个技能的 count（调用次数）+ last_used（最后使用时间） |
| user_preferences（用户兴趣计数） | 从用户输入中提取关键词累加（天气:58、编程:3、画图:4） |
| learning（学习记录） | 预留，当前为空数组（学习职责已由 L8 承担） |

关键词检测规则："天气/温度" → 天气、"游戏/做个/写个" → 编程、"画/海报/图" → 画图

---

## L7 经验沉淀

- 文件：`memory_db/feedback_rules.json`
- 写入：`feedback_classifier.record_feedback_rule()`
- 触发：每次回复后检测负面关键词（"不对"、"错了"、"不好用"等）
- 作用：记录用户的负反馈，分类存储，供后续回复参考

### 板块（`category` 字段）

| 板块 | 覆盖场景 |
|------|----------|
| 内容生成 | 笑话不好笑、故事太短、创作内容不达标 |
| 路由调度 | 走错技能、误触发、不该调用 |
| 意图理解 | 答偏了、没听懂、理解错了 |
| 交互风格 | 太空泛、模板话、不够个性化 |

每条规则包含：category、scene、problem、fix、level（session / short_term）。

L7 产出的规则会触发 L8 的补学流程。

---

## L8 能力进化

- 文件：`memory_db/knowledge_base.json` + `memory_db/autolearn_config.json`
- 代码：`core/l8_learn.py`（依赖注入 `init(llm_call, debug_write)`，由 `agent_final.py` 启动时注入）
- 搜索：`l8_learn.find_relevant_knowledge()`（按关键词评分匹配，只推送相关的，不全量注入）
- 写入：`l8_learn.save_learned_knowledge()`
- 触发入口：
  - `auto_learn()` — 用户问了知识类问题且本地没有相关知识时，后台搜索 Bing 并沉淀
  - `auto_learn_from_feedback()` — L7 记录负反馈后，提取纠偏经验存入知识库
  - `explicit_search_and_learn()` — 用户主动要求"去学/去查"时，同步搜索并沉淀

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
| L2 → L5 | 技能需求信号（"帮我做…"）记录到 knowledge.json |
| L2 → L7 | 纠正/不满信号带上下文推到 feedback_rules.json |
| L2 → L8 | 知识类问答经二次验证后沉淀到 knowledge_base.json |
| L8 → L2/回复 | L8 知识在每次对话时被检索，命中则注入路由和回复上下文（L2 既供料又消费） |
| L5 ↔ L6 | L5 定义技能配置，L6 记录技能执行统计，evolve() 同时更新两者 |
| L5 → executor | executor 从 L4 读取用户上下文（如城市），传给技能 execute() |
| L7 → L8 | L7 记录负反馈后触发 L8 补学，纠偏经验按场景分类存入知识库 |

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
"帮我做个XX"            → L2 检测 skill_demand → L5        ✅
"你说错了"              → L2 检测 correction → L7          ✅
"什么是量子计算"         → L2 检测 knowledge → L8          ✅
```
