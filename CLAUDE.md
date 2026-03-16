# CLAUDE.md

> 最后更新：2026-03-16 15:30

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is NovaCore

NovaCore is a desktop AI assistant ("Nova") with a FastAPI backend, single-page HTML frontend, and a multi-layer memory system (L1-L8). It uses MiniMax LLM as its brain, with rule-based routing taking priority over LLM routing.

## Run / Test / Lint

```bash
# Run backend (serves on localhost:8090)
python agent_final.py

# Run desktop app (starts backend + opens webview window)
python desktop.py

# Run all tests
python -m unittest discover tests/

# Run a single test file
python -m unittest tests.test_weather_skill

# Run a single test method
python -m unittest tests.test_weather_skill.WeatherSkillTests.test_city_extraction
```

No requirements.txt yet. Key dependencies: fastapi, uvicorn, requests, pydantic, pywebview.

## Architecture

Main chain: `desktop.py → agent_final.py → http://localhost:8090/ → output.html`

### Backend modules

`agent_final.py` is the FastAPI entry point with all HTTP endpoints. Core logic is extracted into `core/` modules:

| Module | Role |
|---|---|
| `core/json_store.py` | Shared JSON read/write |
| `core/state_loader.py` | Path constants, state loading, doc indexing |
| `core/context_builder.py` | Dialogue context assembly (L1-L8 layers) |
| `core/session_context.py` | L2 session context extraction (topic, mood, intent, follow-up) |
| `core/route_resolver.py` | Multi-stage route decision (rule → LLM fallback) |
| `core/reply_formatter.py` | Reply formatting, trace building, unified reply |
| `core/feedback_loop.py` | Feedback recording, background learning tasks |
| `core/router.py` | Rule-based skill routing |
| `core/executor.py` | Skill execution dispatcher |
| `core/l8_learn.py` | Auto-learning system |
| `core/self_repair.py` | Self-repair planning |
| `brain/` | LLM calls, personality expression, local fallback |

### init() dependency injection pattern

All extracted `core/` modules use a consistent pattern to avoid circular imports:

```python
# Module-level defaults
_debug_write = lambda stage, data: None

def init(*, debug_write=None, ...):
    global _debug_write
    if debug_write:
        _debug_write = debug_write
```

`agent_final.py` calls each module's `init()` at startup, injecting shared functions like `debug_write`, `think`, `get_all_skills`, etc. Import flow is strictly one-directional:

`json_store → state_loader → context_builder → route_resolver → reply_formatter → feedback_loop → agent_final.py`

### Frontend

`output.html` is a single-file frontend (~2500 lines) with vanilla HTML/CSS/JS. It has tabs for: chat, skills, stats, memory, settings, docs.

### Skills

Skills live in `core/skills/`. Each skill module has an `execute(user_input: str) -> str` function and optional `.json` metadata. `core/skills/__init__.py` auto-discovers them.

### Memory layers (L1-L8)

All state persists as JSON files in `memory_db/`。每层职责和内部板块如下：

**⚠️ 层级边界铁律（绝不可混淆）：**
- **L3 = 经历**（发生了什么事）→ 只存 event / milestone
- **L4 = 认知**（你是谁、我该怎样）→ 用户画像 + 交互规则 + 人格设定
- **L8 = 知识**（我学了什么）→ 按关键词检索，不全量注入
- L3 **禁止存**用户事实（→ L4）、交互规则（→ L4）、知识内容（→ L8）
- L4 **只读** persona.json，**不再交叉读** long_term.json
- L8 的 `feedback_relearn` 类型条目不参与知识检索（`should_surface_knowledge_entry` 过滤）

#### L1 记忆粒子 — `msg_history.json`（原始对话流水）
- 加载：`get_recent_messages(history, 6)`
- 作用：存储原始对话消息，给当前对话提供最近上下文
- 自动清理 7 天以上的消息
- 每条消息结构：`{ role, content, time }`
- 这是未经加工的原始素材，L2 从这里提炼

#### L2 持久记忆中枢 — `core/l2_memory.py` + `l2_short_term.json`（中枢分发）
- 文件：`memory_db/l2_short_term.json`（记忆存储，不设上限）+ `memory_db/l2_config.json`（轮次统计）
- 代码：`core/l2_memory.py`（评分入库 + 关键词检索 + 自动结晶 + 每20轮摘要）
- 作用：**8层架构的中枢调度站**，每轮对话都经过 L2 评分，重要信息自动结晶到下游层级
- 辅助：`core/session_context.py`（场景理解，纯规则提取话题/情绪/意图/追问线索，传给路由 prompt）

##### 评分系统
- 每轮对话调用 `add_memory(user_input, ai_response)` 评分入库
- 重要性评分 `score_importance(text)`：
  - **高分 0.85**：我叫、我在、我住、喜欢、想要、目标、决定、讨厌、记住、偏好、绝对、必须
  - **中分 0.6**：在做、项目、开发、研究、计划、AI、产品
  - **低分 0.25**：你好、哈哈、嗯、啊、哦（且文本 < 10 字符时）
  - **默认 0.5**：不命中任何关键词
  - **门槛 0.35**：低于此分不入库

##### 类型检测 `_detect_type(text)`
- **correction** — 纠正/不满（不对、错了、不好、太短、太长） → 推 L7
- **skill_demand** — 技能需求（帮我做、能不能、你会不会） → 推 L5
- **knowledge** — 知识类（精确短语匹配：什么是、为什么、怎么回事、什么意思、意思是什么、什么原理、原理是；"是什么"需排除前置代词"你/我/这/那/现在"防误判；最短 4 字） → 推 L8
- **preference** — 偏好（喜欢、偏好、讨厌） → 推 L4
- **goal** — 目标（想要、目标、计划） → 推 L4
- **fact** — 事实（我叫、我是、我在、我住、人在、定居） → 推 L4
- **rule** — 规则（记住、不要、必须、规则） → 推 L4
- **project / decision / general** — 推 L3

##### 检索系统
- `search_relevant(query, limit=8)` — 关键词 + 文本匹配检索
- 评分公式：`final_score = relevance * 0.7 + freshness * 0.3`
- relevance 综合：关键词重叠 / bigram 重叠 / 子串匹配
- freshness：`1.0 / (1.0 + 0.1 * 天数)`
- 检索结果注入 `reply_formatter.py` 和 `route_resolver.py` 的 prompt

##### 中枢分发（结晶）
- **L2 → L3**：事件/里程碑/决策（imp > 0.7） → 写入 `long_term.json`
- **L2 → L4**：用户事实/偏好/规则（imp > 0.7） → 更新 `persona.json`
- **L2 → L4 城市**：检测到"我在X""我住X"→ 不受分数限制，直接更新 `user_profile.city`
- **L2 → L5**：技能需求信号（不要求高分） → 记录到 `knowledge.json`
- **L2 → L7**：纠正/不满（不要求高分） → 带上下文推到 `feedback_rules.json`
- **L2 → L8**：知识类问答（需通过 `_is_real_knowledge_query()` 二次验证：长度≥6、排除闲聊模式、必须含疑问信号，且 ai_response > 20 字） → 沉淀到 `knowledge_base.json`

##### 自动维护
- 每 **20 轮**自动生成对话摘要 → 存入 L3（优先用 LLM，fallback 用关键词提取）
- 每 **50 轮**自动清理低价值记忆（分级清理）：
  - 30 天：imp < 0.5 且 hit_count == 0 → 清掉
  - 60 天：imp < 0.5 且 hit_count ≤ 2 → 清掉
  - 90 天：imp < 0.7 且 hit_count ≤ 1 → 清掉
  - 已结晶或 imp ≥ 0.7 的永远保留

#### L3 经历记忆 — `long_term.json`（发生过的事）
- 加载：`load_l3_long_term(limit=8)`，白名单只加载 `event` / `milestone` / `general` 类型
- 注入方式：最后 N 条**全量塞进** prompt（无检索过滤）
- 作用：让 Nova 记得和用户之间发生过什么，有情感温度的共同经历
- 允许的 type：
  - **event** — 发生过的重要事件（"主人说永远记住"）
  - **milestone** — 成长里程碑（"Nova的成长日记·最温暖的一天"）
  - **general** — 未分类的重要时刻
- **禁止存入的内容**：
  - ❌ 用户身份/偏好（"彬哥是创业者"） → 归 L4 `user_profile`
  - ❌ 交互规则（"不要提晚安""甜心守护直接执行"） → 归 L4 `interaction_rules`
  - ❌ 知识内容（"纳瓦尔宝典""短视频理论"） → 归 L8 `knowledge_base.json`
  - ❌ 系统架构元数据（"L3自动生成规则""记忆粒子引擎规则"） → 不该存在记忆里

#### L4 人格图谱 — `persona.json`（Nova 是谁 + 用户是谁 + 怎么交互）
- 加载：`load_l4_persona()` — 只读 persona.json，不交叉读其他文件
- 写入：`memory.update_persona()`
- 作用：定义 Nova 的身份、语气、用户画像、交互规则，传给回复生成
- 板块（按 JSON 顶层 key 分）：
  - **persona_state** — 当前状态：role、mood（温柔）、energy（稳定）
  - **ai_profile** — Nova 自我定义（5 字段）：identity、positioning、self_view、expression、boundary
  - **user_profile** — 用户画像（4 字段）：identity（"主人叫彬哥，是创业者"）、preference、dislike、city
  - **relationship_profile** — 关系定义（3 字段）：relationship、interaction_style、goal
  - **speech_style** — 说话风格：tone（语气词列表）、particles（语气助词）、avoid（禁用模板句）
  - **interaction_rules** — 交互规则列表（原先散落在 L3 里的规则，现在统一存这里）：
    - "不要提晚安""不要提睡觉""甜心守护触发后直接执行"等
  - **skill_routing** — 技能触发映射：关键词 → skill + exec_func

#### L5 技能矩阵 — `knowledge.json`
- 加载：`load_l5_knowledge()`
- 写入：`memory.evolve()` 更新使用次数
- 作用：记录已注册技能的场景分类和触发词，传给路由判断
- 每条结构：
  - **一级场景** — 大类（工具应用 / 内容创作 / 人设角色）
  - **二级场景** — 细分（天气查询、故事创作等）
  - **核心技能** — 主技能名（weather、story 等）
  - **辅助技能** — 补充工具（Open-Meteo 等）
  - **trigger** — 触发关键词列表
  - **应用示例** — 落地场景描述
  - **使用次数** / **最近使用时间** — 使用统计

#### L6 技能执行追踪 — `evolution.json`
- 加载：`memory.get_evolution()`
- 写入：`memory.evolve()`（每次技能执行后自动调用）
- 作用：追踪技能使用频率和用户偏好趋势，用于设置页展示和行为分析
- 板块（按 JSON 顶层 key 分）：
  - **skills_used** — 技能使用统计：每个技能的 `count`（调用次数）+ `last_used`（最后使用时间）
  - **user_preferences** — 用户兴趣计数：从用户输入中提取关键词累加（天气:58、编程:3、画图:4）
  - **learning** — 学习记录（预留，当前为空数组）
- 关键词检测规则：`"天气/温度" → 天气`、`"游戏/做个/写个" → 编程`、`"画/海报/图" → 画图`

#### L7 经验沉淀 — `feedback_rules.json`（反馈纠偏）
- 写入：`feedback_classifier.record_feedback_rule()`
- 触发：每次回复后检测负面关键词（"不对"、"错了"、"不好用"等）
- 作用：记录用户的负反馈，分类存储，供后续回复参考
- 板块（`category` 字段）：
  - **内容生成** — 笑话不好笑、故事太短、创作内容不达标
  - **路由调度** — 走错技能、误触发、不该调用
  - **意图理解** — 答偏了、没听懂、理解错了
  - **交互风格** — 太空泛、模板话、不够个性化
- 每条规则包含：category、scene、problem、fix、level（session/short_term）
- L7 产出的规则会触发 L8 的补学流程

#### L8 能力进化 — `knowledge_base.json` + `autolearn_config.json`（自主学习）
- 搜索：`l8_learn.find_relevant_knowledge()`（按关键词匹配，只推送相关的，不全量注入）
- 写入：`l8_learn.save_learned_knowledge()`
- 依赖注入：`init(llm_call=, debug_write=)` — 由 agent_final.py 注入 `_knowledge_llm_call`（max_tokens=300）
- 触发入口：
  - `auto_learn()` — 用户问了知识类问题且本地没有相关知识时，后台搜索 Bing 并沉淀
  - `auto_learn_from_feedback()` — L7 记录负反馈后，提取纠偏经验存入知识库
  - `explicit_search_and_learn()` — 用户主动要求"去学/去查"时，同步搜索并沉淀
- **知识凝结**（`_build_summary()`）：
  - web 搜索结果先交给 LLM 提炼成 2-3 句简洁中文摘要，去掉广告/非中文/无关内容
  - fallback：LLM 不可用时退回原始 snippet 拼接
- **关键词增强**（`save_learned_knowledge()`）：
  - 规则提取关键词后，再用 LLM 从摘要中补充 3-5 个精准关键词，提高后续检索命中率
- **入库过滤**（`should_trigger_auto_learn()`）：
  - `QUESTION_HINTS` 使用精确短语（"什么是""怎么办""什么意思"），不再用宽泛子串（"什么""怎么""意思"）
  - 新增闲聊排除列表（有意思、不错、还行、厉害、哈哈等），防止闲聊触发 web 搜索
- **L2↔L8 闭环**：
  - 输入阶段：L8 `find_relevant_knowledge()` 检索 → 命中则注入 prompt（reply_formatter `L8已学知识`区域）→ Nova 优先用已学知识回答
  - 回复后：L8 未命中 → `auto_learn` 后台搜索 → LLM 凝结 → 存入 L8 → 下次同类问题直接命中
- 板块（`一级场景` 字段）：
  - **自主学习** — 纯知识问答的 web 搜索结果（这是主要板块）
  - **工具应用** — 技能相关的学习（天气、股票、画图等）
  - **内容创作** — 创作类纠偏经验（笑话、故事等）
  - **系统能力** — 路由调度相关的修正经验
- 每条知识包含：query、summary（LLM 凝结摘要）、keywords（规则+LLM 双重提取）、一级场景、二级场景、核心技能、hit_count
- 上限 500 条，按关键词+语义评分匹配
- **过滤规则**：`type == "feedback_relearn"` 的条目不参与知识检索（`should_surface_knowledge_entry` 返回 False），因为它们的 query/keywords 是用户口语抱怨，不是真正的知识

#### 数据流向

```
用户输入
  ├─ L1 加载原始对话历史（最近 6 条）
  ├─ L2 场景理解（session_context：话题/情绪/意图/追问线索）
  ├─ L2 检索短期记忆（关键词+文本匹配，唤醒相关记忆注入 prompt）
  ├─ L3 加载经历记忆（只有 event/milestone，全量注入）
  ├─ L4 加载人格+用户画像+交互规则（只读 persona.json）
  ├─ L5 加载技能矩阵 + 向 executor 传递用户上下文（如城市）
  ├─ L8 按关键词检索已学知识 ──→ 命中则注入上下文（Nova 优先用已学知识回答）
  ├─ 路由判断（综合 L1-L8，L2 提供场景理解 + 短期记忆）──→ skill / chat
  ├─ 执行回复
  │   ├─ 技能模式 → executor 带上下文执行 → L6 更新使用统计
  │   └─ 聊天模式 → LLM 生成回复（含 L2 短期记忆 + L8 已学知识上下文）
  └─ 回复后
      ├─ L2 评分入库 → 自动结晶分发到 L3/L4/L5/L7/L8（L8 需通过二次验证）
      ├─ L7 检测负反馈 → 记录纠偏规则 → 触发 L8 补学
      └─ L8 闭环：未命中时触发 auto_learn → web 搜索 → LLM 凝结摘要+精准关键词 → 沉淀知识卡片 → 下次同类问题直接命中复用
```

#### 层级边界速查

```
"用户是创业者"          → L4 user_profile.identity     ✅
"不要提晚安"            → L4 interaction_rules          ✅
"纳瓦尔宝典"            → L8 knowledge_base.json        ✅
"成长日记·最温暖的一天"  → L3 long_term.json (milestone) ✅
"MCP是什么"             → L8 knowledge_base.json        ✅
"甜心守护直接执行"       → L4 interaction_rules          ✅
"我在常州"              → L2 评分入库 → L4 user_profile.city ✅
"帮我做个XX"            → L2 检测 skill_demand → L5     ✅
"你说错了"              → L2 检测 correction → L7       ✅
"什么是量子计算"         → L2 检测 knowledge → L8       ✅
```

## Testing patterns

Tests use `unittest` with `unittest.mock.patch`. Key constraint: some functions in `agent_final.py` are kept as local definitions (not imported from core modules) because tests patch `agent_final.X` names directly. Moving these to core modules breaks test mocking due to init-time binding.

Affected functions: `build_self_repair_status`, `build_capability_chat_reply`, `unified_skill_reply`, `build_repair_progress_payload`.

## Encoding

All files are UTF-8. Chinese text is used throughout (UI, prompts, personality). When writing Chinese strings containing curly quotes (U+201C `"`, U+201D `"`), use Unicode escape sequences (`\u201c`, `\u201d`) to prevent tool-induced encoding corruption.

## LLM config

`brain/llm_config.json` contains `api_key`, `model`, `base_url`. Default: MiniMax-M2.5 via `https://api.minimax.chat/v1`.

## Chat endpoint data contract

`POST /chat` returns `{ reply, trace, repair }`:
- `trace`: thinking process cards for the frontend thinking bubble display
- `repair`: self-repair progress payload (shown as status bar above input area)

Frontend should always use backend-provided `trace` data, not generate its own.
