# CLAUDE.md

> 最后更新：2026-03-23

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is NovaCore

NovaCore is a desktop AI assistant ("Nova") with a FastAPI backend, **Electron shell**, modular frontend, and a multi-layer memory system (L1-L8). It uses a user-configurable LLM as its brain (via `/models/config` 管理), with **LLM native tool_call** as the primary routing mechanism — no rule-based routing layer, all decisions delegated to the LLM.

## Hard Project Constraints

These are repository-level architectural constraints and must be treated as binding:

1. Do not insert any new layer before LLM decision.
   No pre-routing, pre-planning, pre-decision continuity injection, or other new flow may be added ahead of the LLM's own decision point.

2. Do not reorder the main sequence in `routes/chat.py`.
   Localized fixes are acceptable only if they preserve the current order. Structural reordering requires explicit approval.

3. Do not rebuild or duplicate an existing subsystem.
   Before adding new planning, continuity, routing, or protocol logic, first verify whether the repository already has that subsystem and extend the existing design instead of creating a parallel one.

## Run / Test / Lint

```bash
# Run backend (serves on localhost:8090)
python agent_final.py

# Run desktop app (Electron shell, auto-starts backend)
# 方式1：双击桌面 NovaCore 快捷方式
# 方式2：命令行
start_nova.bat

# Run all tests
python -m unittest discover tests/

# Run a single test file
python -m unittest tests.test_weather_skill
```

No requirements.txt yet. Key dependencies: fastapi, uvicorn, requests, pydantic. Desktop shell: Electron (via companion/node_modules).

## Architecture

Main chain: `start_nova.bat → shell/main.js (Electron) → http://localhost:8090/ → output.html`

### 当前对话链路（tool_call + CoD）

**核心原则：权力归于 LLM，效率归于工程。拒绝中间层规则分流。**

```
用户输入 → POST /chat（SSE streaming）
  ├─ L1 加载对话历史（最近 15 轮，原生 user/assistant messages 数组）
  ├─ L4 精简加载（_condense_l4 提取核心身份 ~200 字自然语言）
  ├─ 构建 system prompt（~900 tokens，不全量注入 L2/L3/L5/L8）
  ├─ 一次 LLM 调用（带 tools 定义）
  │   ├─ LLM 直接回复文本 → 流式输出 → 完成
  │   └─ LLM 输出 tool_call → 框架执行 → 结果喂回 → LLM 继续回复
  └─ 回复后
      ├─ L2 评分入库 → 自动结晶分发到 L3/L4/L5/L7/L8
      ├─ L7 检测负反馈 → 记录纠偏规则 → 触发 L8 补学
      └─ L8 闭环：未命中时 auto_learn → web 搜索 → 知识沉淀
```

### tool_call 模式

- `_get_tool_call_enabled()` 硬编码 True，全量走 tool_call
- 技能通过 `core/tool_adapter.py` 转成 OpenAI function calling 格式
- `build_tools_list()` 从 `get_all_skills()` 自动构建 tools 定义
- LLM 自己决定调不调工具、调哪个 — **不需要规则路由预判**
- 技能 description（`tools/agent/*.json` 和 `skills/builtin/*.json`）是 LLM 判断的唯一依据，必须写清楚能力边界

### CoD（Context-on-Demand）按需上下文

- L2/L3/L5/L8 不再注入 system prompt，改为两个记忆工具：
  - `recall_memory(query)` — 检索 L2(短期记忆) + L3(经历)
  - `query_knowledge(topic)` — 检索 L8(知识库)
- system prompt 从 ~3000 tokens 降到 ~900 tokens
- 开关：`state_data/tool_call_config.json` 的 `cod_enabled` 字段
- L1 是固定窗口（Fixed Context），L2-L8 是扩展插槽（Expansion Slots）

### Backend modules

`agent_final.py` is the FastAPI entry point — app creation, initialization, and route mounting. HTTP endpoints are split into `routes/` modules:

| Module | Role |
|---|---|
| `routes/health.py` | `/health`, `/awareness/pending`, `/qq/monitor` |
| `routes/models.py` | `/models`, `/model/{name}`, `/models/config` |
| `routes/companion.py` | `/companion`, `/companion/state`, `/companion/models`, `/companion/model/{name}` |
| `routes/data.py` | `/memory`, `/docs/*`, `/skills`, `/history`, `/stats`, `/nova_name` |
| `routes/settings.py` | `/autolearn/*`, `/self_repair/*`, `/l7/stats` |
| `routes/chat.py` | `/chat` (SSE streaming) |
| `core/shared.py` | Shared state container — `agent_final.py` populates at startup, routes import from here |
| `core/json_store.py` | Shared JSON read/write |
| `core/state_loader.py` | Path constants, state loading, doc indexing |
| `core/context_builder.py` | Dialogue context assembly (L1-L8 layers) |
| `core/session_context.py` | Compatibility stub for old L2 session extraction; current tool_call main chain no longer relies on it for real routing |
| `core/route_resolver.py` | Legacy route decision module, retained for compatibility and non-main-path code only |
| `core/reply_formatter.py` | Reply formatting, trace building, unified reply with tools stream |
| `core/tool_adapter.py` | Skill → OpenAI tool 转换、tool_call 执行桥接、CoD 记忆工具 |
| `core/feedback_loop.py` | Feedback recording, background learning tasks |
| `core/router.py` | Legacy rule-based routing module, not part of the current tool_call main chain |
| `core/executor.py` | Skill execution dispatcher |
| `core/l8_learn.py` | Auto-learning system |
| `core/self_repair.py` | Self-repair planning |
| `brain/` | LLM calls, personality expression, local fallback |

### 路由规范

- 所有新 API 路由必须放在 `routes/` 对应模块中，禁止直接加到 `agent_final.py`
- `agent_final.py` 只负责：app 创建、初始化、HTML 服务（`/` 和 `/__restored_output.js`）、路由挂载、测试兼容函数
- 新增路由域（全新功能领域）时新建 `routes/xxx.py`
- 每个路由文件不超过 300 行，超过时拆分
- 路由模块通过 `from core import shared as S` 访问共享状态，不直接 import `agent_final`（避免循环依赖）
- 需要测试 patch 的函数保留在 `agent_final.py`，路由模块通过 lazy import `agent_final` 调用

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

`agent_final.py` calls each module's `init()` at startup, injecting shared functions like `debug_write`, `think`, `get_all_skills`, etc. Import flow is strictly one-directional. Note: this is an import/dependency chain, not the runtime dialogue main chain:

`json_store → state_loader → context_builder → route_resolver → reply_formatter → feedback_loop → agent_final.py`

### Frontend

`output.html` is a minimal HTML skeleton (~150 lines). CSS and JS are split into `static/` modules:

- `static/css/main.css` — 全部样式
- `static/js/utils.js` — 公共工具函数
- `static/js/awareness.js` — 感知球
- `static/js/chat.js` — 聊天/发送/流式输出/步骤追踪器
- `static/js/memory.js` — 记忆页
- `static/js/settings.js` — 设置页
- `static/js/docs.js` — 文档页
- `static/js/stats.js` — 驾驶舱/运行看板
- `static/js/app.js` — 标签路由/初始化/侧边栏/历史加载

Chat streaming uses SSE events: `trace`(步骤状态), `stream`(文字 token), `reply`(完整回复), `repair`(修复进度).

### Skills

Runtime skills are now split by responsibility:

- `tools/agent/` — native protocol tools such as file, shell, desktop, and target actions
- `skills/builtin/` — built-in workflow/domain skills
- `core/skills/` — compatibility package for old imports only
- `capability_registry/__init__.py` — runtime registry that auto-discovers `tools/agent/` and `skills/builtin/`

### Memory layers (L1-L8)

All state persists as JSON files in `state_data/`。每层职责和内部板块如下：

**⚠️ 层级边界铁律（绝不可混淆）：**
- **L3 = 经历**（发生了什么事）→ 只存 event / milestone
- **L4 = 认知**（你是谁、我该怎样）→ 用户画像 + 交互规则 + 人格设定
- **L8 = 知识**（我学了什么）→ 按关键词检索，不全量注入
- L3 **禁止存**用户事实（→ L4）、交互规则（→ L4）、知识内容（→ L8）
- L4 **只读** persona.json，**不再交叉读** long_term.json
- L8 的 `feedback_relearn` 类型条目不参与知识检索（`should_surface_knowledge_entry` 过滤）

#### L1 记忆粒子 — `msg_history.json`（原始对话流水）
- 加载：`_build_l1_messages(bundle, limit=15)` — 取最近 15 轮完整对话，构建原生 user/assistant messages 数组
- 超长回复截断到 800 字，连续同 role 自动合并
- 作用：存储原始对话消息，给 LLM 提供多轮上下文理解能力
- 自动清理 7 天以上的消息
- 每条消息结构：`{ role, content, time }`
- 这是未经加工的原始素材，L2 从这里提炼

#### L2 持久记忆中枢 — `core/l2_memory.py` + `l2_short_term.json`（中枢分发）
- 文件：`state_data/l2_short_term.json`（记忆存储，不设上限）+ `state_data/l2_config.json`（轮次统计）
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
  ├─ L1 加载对话历史（最近 15 轮，原生 messages 数组）
  ├─ L4 精简加载（_condense_l4 提取核心身份 ~200 字）
  ├─ 构建 system prompt（~900 tokens）+ tools 定义
  ├─ 一次 LLM 调用（tool_call 模式）
  │   ├─ LLM 判断需要记忆 → 调用 recall_memory / query_knowledge
  │   │   ├─ recall_memory → 检索 L2 短期记忆 + L3 经历
  │   │   └─ query_knowledge → 检索 L8 知识库
  │   ├─ LLM 判断需要技能 → 调用 weather / news / computer_use 等
  │   │   └─ executor 执行 → 结果喂回 → LLM 继续回复
  │   └─ LLM 判断直接回复 → 流式输出文本
  └─ 回复后
      ├─ L2 评分入库 → 自动结晶分发到 L3/L4/L5/L7/L8（L8 需通过二次验证）
      ├─ L7 检测负反馈 → 记录纠偏规则 → 触发 L8 补学
      └─ L8 闭环：未命中时触发 auto_learn → web 搜索 → LLM 凝结 → 沉淀 → 下次命中
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

Tests use `unittest` with `unittest.mock.patch`. Key constraint: some functions in `agent_final.py` are kept as local definitions (not moved to routes) because tests patch `agent_final.X` names directly. Moving these to route modules breaks test mocking due to init-time binding.

Affected functions: `build_self_repair_status`, `build_capability_chat_reply`, `build_repair_progress_payload`.

Route modules that need these functions use lazy `import agent_final` inside request handlers to avoid circular imports while preserving test patchability.

## Encoding

All files are UTF-8. Chinese text is used throughout (UI, prompts, personality). When writing Chinese strings containing curly quotes (U+201C `"`, U+201D `"`), use Unicode escape sequences (`\u201c`, `\u201d`) to prevent tool-induced encoding corruption.

## LLM config

`brain/llm_config.json` contains `api_key`, `model`, `base_url`. Users can add/switch models via the settings page or `/models/config` API.

## Chat endpoint data contract

`POST /chat` returns `{ reply, trace, repair }`:
- `trace`: thinking process cards for the frontend thinking bubble display
- `repair`: self-repair progress payload (shown as status bar above input area)

Frontend should always use backend-provided `trace` data, not generate its own.

---

## 实验室（Lab）— AutoResearch 引擎

> 参考：Karpathy autoresearch（一个文件、一个指标、一个循环）
> 状态：架构已简化，核心循环可用

### 设计原则

- **一个文件**：每次实验只修改一个目标文件（等价于 Karpathy 的 `train.py`）
- **一个指标**：`verify.py` 输出 0-100 分数（等价于 `val_bpb`）
- **一个循环**：读文件 → LLM 改 → 写回 → 跑验证 → 比分 → 留好的 → 重复
- **不依赖 Git**：baseline 存内存，失败直接写回，不需要 commit/revert
- **不污染主系统**：不注入 L4/L7 记忆，不往 L7 写失败经验，实验室独立运行

### 文件结构

| 文件 | 角色 | 等价 Karpathy |
|---|---|---|
| `core/lab.py` | 实验引擎（循环 + 控制） | 主循环 |
| `routes/lab.py` | API 路由 | — |
| `state_data/lab/verify.py` | 验证脚本（固定，人工维护） | `prepare.py` |
| `state_data/lab/experiments.json` | 实验记录 | — |
| `state_data/lab/results.tsv` | 逐轮日志 | — |
| `static/js/lab.js` | 前端 UI | — |

### 核心循环

```
baseline = 读取目标文件
best = baseline
for round in 1..N:
    current = 读文件
    new_code = LLM(current, goal)       # max_tokens=16384
    写入 new_code → 目标文件
    score = verify.py(目标文件, goal)    # 子进程，输出 0-100
    if score > best_score:
        best = new_code                  # 留
    else:
        写回 best → 目标文件             # 回退
实验结束：无改善 → 恢复 baseline
```


### 今日进展（2026-03-23 凌晨）

#### 多轮 tool_call（核心架构升级）
- **之前**：只支持单轮 tool_call（LLM 调一次工具后第二次不带 tools，无法连续调用）
- **现在**：多轮循环，每轮都带 tools，LLM 自主决定何时停止
- 安全上限 20 轮（正常 3-5 轮），跑满上限后补一次 LLM 调用生成最终回复
- 文件：`core/reply_formatter.py` `unified_reply_with_tools_stream()` 重写 tool_call 循环
- 前端 trace 更新：`read_file` → "检查文件"、`list_files` → "浏览目录"、`self_fix` → "自我修复"

#### 新增诊断工具（read_file + list_files）
- Nova 之前只能盲猜文件路径，现在能先看再修
- `read_file(file_path)` — 读取白名单内的文件内容（大文件截断前 200 行）
- `list_files(directory)` — 列出目录结构（不传参则列所有可访问目录）
- 工具定义写入 `configs/tools.json`（v1.1）
- 完整诊断流程：`list_files → read_file → self_fix`（LLM 自主编排，不强制顺序）

#### self_fix 大文件补丁模式
- **小文件（≤300行）**：全量重写（原逻辑）
- **大文件（>300行）**：补丁模式 — LLM 只输出 `===APPEND===` 或 `===FIND/REPLACE===` 指令
- 解决 3000 行 CSS 文件全量重写超时/超 token 的问题
- 参数名兼容：同时接受 `problem` 和 `fix_description`
- 路径自动纠错：`frontend/css/` → `static/css/`、反斜杠→正斜杠、模糊匹配文件名

#### 白名单扩展
- 早期：`["static/", "configs/", "core/skills/"]`
- 当前：`["static/", "configs/", "tools/agent/", "skills/builtin/", "app_data/", "workers/", "state_data/"]`
- `state_data/` 允许 Nova 读写自己的主状态与记忆数据
- `core/` 核心引擎代码仍不直接开放给 self_fix

#### "禁止加粗" 规则清理
- 发现 Markdown 渲染不是 CSS/JS 问题，而是 system prompt 禁止 LLM 输出 Markdown 语法
- **6 处**"禁止加粗"规则分布在 3 层：
  - `core/reply_formatter.py`：4 处硬编码（4 个不同的 prompt 构建函数）
  - `configs/prompts.json`：1 处
  - `state_data/persona.json` L4：1 处
- 全部改为"回复时可以自由使用 Markdown 语法"
- 教训：system prompt 是最高优先级指令，一条规则能覆盖所有用户请求
- 教训：配置分散在代码+配置文件+记忆文件三层时，改一处不够

#### L1 历史清理
- 清空 `msg_history.json`（9000+ 行），因为全是不用 Markdown 的旧回复
- L2-L8 的结晶数据不受影响（重要记忆、人格、规则都保留）
- L1 只是原始对话流水，清掉后 Nova 仍认识用户

---

### 竞品调研：OpenClaw（NovaCore 的样板）

> GitHub: https://github.com/openclaw/openclaw
> 330k stars, 64.1k forks（2026年最火的开源 AI 项目）
> 进化链：Claude Code → OpenClaw → NovaCore

#### OpenClaw 是什么
- 自托管的多平台 AI 助手，核心是 **Gateway WebSocket 控制面**
- 接入 20+ 消息平台：WhatsApp、Telegram、Slack、Discord、Signal、iMessage 等
- 设备集成：macOS/iOS/Android 节点，暴露摄像头、录屏、定位、通知等本地能力
- 语音：唤醒词检测 + ElevenLabs TTS
- 浏览器自动化：CDP 控制 Chrome
- Canvas 工作区：A2UI 可视化交互

#### OpenClaw 的架构特点
- Gateway WebSocket (`ws://127.0.0.1:18789`) 统一控制面
- 多 Agent 路由：不同渠道/账号可路由到隔离的 agent
- 安全模型：配对模式（未知发送者需验证码），DM 视为不可信输入
- `/restart` 聊天中重启网关，`/elevated on` 提权 bash 执行
- `openclaw doctor` 自检修复
- 守护进程：launchd (macOS) / systemd (Linux)，崩溃自动重启

#### NovaCore vs OpenClaw 对比

| 维度 | OpenClaw | NovaCore |
|---|---|---|
| 多平台接入 | 20+ 渠道 ✅✅✅ | 仅桌面端 ❌ |
| 设备控制 | 摄像头/录屏/定位 ✅ | 无 ❌ |
| 浏览器自动化 | CDP Chrome ✅ | computer_use 基础版 |
| 记忆系统 | 会话压缩，基本存储 | L1-L8 八层记忆 ✅✅✅ |
| 人格系统 | 无 | L4 完整人格图谱 ✅✅ |
| 自我修复 | 用户命令式 (`/restart`) | AI 自主式 (self_fix) ✅ |
| 自我认知 | 无 | 闪回+read_file+list_files ✅ |
| 用户画像 | 无 | L4 画像+L7 纠偏 ✅ |
| 主动行为 | 无 | 心跳（待做）✅ |

#### NovaCore 的定位
- **OpenClaw 的痛点**：每次新对话都是陌生人，没有持久记忆
- **NovaCore 的价值**：有灵魂的 OpenClaw — 记住你、认识你、主动成长
- **后续方向**：在 NovaCore 的记忆大脑上，逐步补齐 OpenClaw 的基础设施能力（多平台、设备控制、语音等）

#### 可借鉴的 OpenClaw 特性
- [ ] `/restart` 聊天中重启后端
- [ ] 守护进程 + 崩溃自动重启
- [ ] 多渠道接入（优先微信/QQ）
- [ ] 设备节点（摄像头、录屏、定位）
- [ ] 语音唤醒 + TTS
- [ ] Canvas/A2UI 可视化工作区

### 今日进展（2026-03-22 下午-晚）

#### 实验室简化（参考 Karpathy autoresearch）
- 去掉 Git commit/revert、L4/L7 记忆注入、L7 失败写入、`_generate_verify_cmd`
- max_tokens 4096→8192，改用流式调用防截断
- 实验历史喂给 LLM（带记忆的 agent，不再无状态）
- 前端去掉"影子克隆"文案、修 redColor bug、avg_score→score
- 结论：autoresearch 本质是调参器，只适合单文件+客观指标场景，不适合 Nova 技能优化

#### self_fix 工具（对话中即时自我修复）
- 新增 CoD 工具 `self_fix(file_path, problem)` — Nova 聊天中直接修文件
- 白名单限制：只能改 `static/`、`configs/`、`tools/agent/`、`skills/builtin/`、`app_data/`、`workers/`、`state_data/`
- 自动备份 `.bak`、截断保护、流式 LLM 调用
- 工具定义写入 `configs/tools.json`（否则被覆盖 LLM 看不到）
- 修复 `core/self_repair.py` 的 `_load_llm_config()` 不认新格式 config 的 bug
- 设置页去掉旧的"修复提案"区块（已被 self_fix 替代）

#### 闪回引擎（联想回复）
- 新建 `core/flashback.py` — 扫描用户输入的情绪/话题线索，搜 L3+L2 关联记忆
- 触发词：情绪词（烦、累、终于）、回忆词（想起、上次）、模式词（又、总是、每次）
- 命中则注入 system prompt hint，LLM 自己决定要不要自然提到
- 注入点：`routes/chat.py` bundle 构建后 + `reply_formatter.py` 三种 prompt 模式
- 设计：CoD = 主动回忆（意识），闪回 = 不自觉联想（潜意识），互补不重叠

#### 待做：心跳（主动探索）
- 后台定时线程，默默搜索用户关心的领域
- 搜到值得说的 → LLM 判断"值不值得打扰" → 值得才推到 awareness
- 不定时推送（有惊喜感），不是定时闹钟
- 实现：读 L4 画像 + L6 兴趣 → 生成搜索词 → 搜索 → LLM 判断 → 推或闭嘴
- 文件规划：`core/heartbeat.py`（引擎）+ awareness 推送（已有基础设施）

#### 架构思考：L9 自主意识层
- L1-L8 全是被动的（用户说话才转），L9 不依赖用户输入就能运转
- 三个表现：闪回（对话中联想）、心跳（后台主动搜索）、self_fix（自我修复）
- 底层同一个判断："这跟主人有什么关系？值不值得说/做？"

---

### 今日进展（2026-03-23 UI大改造 + 架构迁移）

#### pywebview → Electron 迁移（壳替换）

> ⚠️ **核心经验：遇到死活解决不了的问题，不要在同一层死磕，往上退一步看看是不是层选错了。**

**背景**：无边框窗口在 pywebview 下尝试了 30+ 次全部失败。

**失败方案汇总**（全部在 pywebview 层）：
| # | 方案 | 失败原因 |
|---|------|---------|
| 1 | DWM 边框色匹配 | 边框还在，颜色不是真正的无边框 |
| 2 | `frameless=True` | 去了边框，但丢了拖拽和缩放 |
| 3 | `WM_NCHITTEST` 子类化 | WebView2 子窗口吃掉所有客户区鼠标事件 |
| 4 | CSS `-webkit-app-region: drag` | pywebview 不支持该属性 |
| 5 | `WS_THICKFRAME` 加回 | pywebview 内部覆盖窗口样式 |
| 6 | `SendMessageW` SC_DRAGMOVE | pywebview expose 函数在后台线程，ReleaseCapture 无效 |
| 7 | `PostMessageW` SC_DRAGMOVE | 投递到 UI 线程仍无效 |
| 8 | 完整 64 位签名子类化 | WebView2 控件覆盖了非客户区 |

**根因分析**：
```
pywebview 的嵌套结构：
  Windows 原生窗口 → pywebview 封装层 → WebView2 子窗口 → 网页
  │                  │                  │
  │                  │                  └─ 吃掉鼠标事件
  │                  └─ 覆盖窗口样式
  └─ DWM 管的，CSS 够不到

中间层太多，每层都可能覆盖/拦截你的修改。
```

**解决方案**：换 Electron（壳替换，前端后端一行不改）
```
shell/main.js (Electron)
  └→ http://localhost:8090/ (同一个 FastAPI 后端)
       └→ output.html (同一个前端)

frame: false     → 无边框 ✅（一行配置）
resizable: true  → 可缩放 ✅（原生支持）
CSS -webkit-app-region: drag → 可拖拽 ✅（Electron 原生支持）
```

**文件结构**：
```
NovaCore/
├── shell/                    ← Electron 主壳（新建）
│   ├── main.js               ← 主进程（~100行）
│   ├── preload.js             ← 安全桥接
│   └── package.json
├── start_nova.bat             ← 一键启动（复用 companion 的 electron.exe）
├── desktop.py                 ← 旧壳（保留，不再使用）
```

#### 拉伸黑底修复（transparent: true）

> ⚠️ **同样的教训：setBackgroundColor 改的是 Chromium 层，拉伸黑底是 Windows DWM 层画的。层不对。**

**失败方案**：
| 方案 | 失败原因 |
|------|---------|
| `backgroundColor: '#fafbfc'` | 只影响 Chromium，DWM 不听 |
| `win.setBackgroundColor()` | 同上 |
| `will-resize` + `resize` 事件实时刷 | 同上，API 就够不到 DWM |
| `nativeTheme.themeSource` | 不影响窗口背景 |

**解决方案**：`transparent: true`
```javascript
// shell/main.js
win = new BrowserWindow({
  frame: false,
  transparent: true,   // ← 告诉 DWM "这窗口是透明的，不用涂底色"
  resizable: true,
});
```

**原理**：
- 之前：窗口拉大 → DWM 涂黑色占位 → Chromium 再画内容 → 黑→内容的闪烁
- 现在：窗口拉大 → transparent 说"不用涂" → DWM 跳过 → Chromium 直接画 → 无闪烁

#### 圆角问题（待解决）
- `clip-path: inset(0 round 10px)` 能裁圆但渲染不稳定（晃动后左右不对称）
- `border-radius + overflow:hidden` 被 body 全屏布局覆盖
- 可能的方案：DWM API `DWMWA_WINDOW_CORNER_PREFERENCE`（直接让系统画圆角）
- 当前保持方角（VS Code、Discord 等同级产品也是方角 frameless）

#### UI 改造清单
- **聊天居中**：`.msg` 的 `align-self: stretch` → `center`
- **弹性宽度**：`max-width: 780px` → `width:90%; max-width:1600px`
- **行高变量**：`--bubble-line-height`，≤1200px 用 1.6，>1200px 用 1.8
- **输入框重构**：图片/话筒/发送按钮移入 `.inp-wrap` 内的 `.inp-actions` 工具栏
- **输入框悬浮**：去掉 `.input` 底槽背景，`margin-top:-40px` 浮在聊天区上方
- **渐隐遮罩**：`.input::before` 从输入框向上投射 60px 渐变
- **自动增高**：textarea `max-height:40vh`，去掉 `flex:1`（这是增高失效的根因）
- **发送按钮智能显隐**：默认隐藏，有内容时 `.visible` 类显示
- **光标呼吸**：`caret-color` 在紫色间 2s 循环
- **动态 Placeholder**：8 秒轮换文案
- **快捷键提示**：`Enter 发送 · Shift+Enter 换行`，≥1000px 显示
- **滚动条**：textarea 内滚动条 3px、透明轨道、半透明滑块
- **设置/实验室全宽**：`.chat:has(.settings-page)` 加 `align-items:stretch`
- **窗口控制按钮**：最小化/最大化/关闭（IPC 通信）
- **前端壳兼容层**：自动检测 Electron (`novaShell`) / pywebview / 浏览器

#### 经验总结（价值最高的三条）

1. **"在错误的层上使劲"是最大的时间浪费**
   - 边框问题：pywebview 中间层太多 → 换 Electron 直接解决
   - 黑底问题：setBackgroundColor 改 Chromium 层 → transparent:true 改 DWM 层
   - 规则覆盖问题（上次）：改 CSS 没用 → 发现是 system prompt "禁止加粗"

2. **看竞品的底层，不只看表面**
   - 右键看豆包属性 → 发现是 .exe（Electron）→ 找到了正确方向
   - 不是看 UI 好不好看，是看它用什么技术栈

3. **先验证再打磨（MVP 思维）**
   - 早期用 pywebview 3 行跑起来 → 验证核心功能
   - 等到在意边框了 → 说明产品成熟了 → 再升级基础设施
   - 顺序不能反：先用最快的方式做出来，值得了再换壳
- Nova 的进化路径不是"改代码"，是"积累认知 + 主动行动"

### 今日其他修复（2026-03-22 上午）
- L1 去重：`_history_for_context` 防止用户消息在 LLM 中出现两遍
- L1 卫生检查：`l1_hygiene_clean()` 防止坏回复自我强化（毒教材循环）
- L8 知识库清洗：44→23 条，移除垃圾条目
- L8 入库质检：`_check_entry_quality()` 6 道检查拦截垃圾
- L8 检索门槛：min_score 6→12，topic_overlap 不再放行一切
- L8 搜索引擎：Bing RSS → Tavily API（+ Brave 备选）
- `<think>` 过滤修复：缓冲 60 字符再判断，防止跨 chunk 泄漏
- web_search 工具：加入 CoD 工具列表，Nova 能当场搜索回答
- 思考步骤布局：flex-start 替代 flex-end，不再跑到头像上方
- 流式滚动修复：_initStreamBubble 强制滚底 + 前5次flush无条件滚动
