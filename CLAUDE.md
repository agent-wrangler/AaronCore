# CLAUDE.md

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

#### L2 记忆提炼 — `core/session_context.py`（场景理解）
- 加载：`extract_session_context(history, current_input)`
- 作用：从 L1 原始对话中**提炼**出结构化的短期认知，不是简单多取几条消息
- 板块（返回 dict 的 4 个 key）：
  - **topics（话题识别）** — 这轮对话在聊什么（天气/股票/故事/编程/技术/闲聊等）
  - **mood（情绪感知）** — 用户当前情绪状态（平稳/积极/低落/不满/纠正/感谢）
  - **intents（意图追踪）** — 用户最近的意图模式链（任务委托→知识提问→延续追问等）
  - **follow_up（上下文延续）** — 需要接住的线索：story_title（故事续写）、is_follow_up（追问）、is_correction（纠正）、repeated_question（重复提问）
- 轻量实现：纯规则提取，不调 LLM，不用向量
- 传给路由 prompt（作为"L2会话理解"），帮助路由判断更准确

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
- 触发入口：
  - `auto_learn()` — 用户问了知识类问题且本地没有相关知识时，后台搜索 Bing 并沉淀
  - `auto_learn_from_feedback()` — L7 记录负反馈后，提取纠偏经验存入知识库
  - `explicit_search_and_learn()` — 用户主动要求"去学/去查"时，同步搜索并沉淀
- 板块（`一级场景` 字段）：
  - **自主学习** — 纯知识问答的 web 搜索结果（这是主要板块）
  - **工具应用** — 技能相关的学习（天气、股票、画图等）
  - **内容创作** — 创作类纠偏经验（笑话、故事等）
  - **系统能力** — 路由调度相关的修正经验
- 每条知识包含：query、summary、keywords、一级场景、二级场景、核心技能、hit_count
- 上限 500 条，按关键词+语义评分匹配
- **过滤规则**：`type == "feedback_relearn"` 的条目不参与知识检索（`should_surface_knowledge_entry` 返回 False），因为它们的 query/keywords 是用户口语抱怨，不是真正的知识

#### 数据流向

```
用户输入
  ├─ L1 加载原始对话历史（最近 6 条）
  ├─ L2 从 L1 提炼会话认知（话题/情绪/意图/上下文线索）
  ├─ L3 加载经历记忆（只有 event/milestone，全量注入）
  ├─ L4 加载人格+用户画像+交互规则（只读 persona.json）
  ├─ L5 加载技能矩阵
  ├─ L8 按关键词检索相关知识 ──→ 命中则注入上下文
  ├─ 路由判断（综合 L1-L8，L2 提供场景理解）──→ skill / chat
  ├─ 执行回复
  │   ├─ 技能模式 → L6 执行技能 → 更新使用统计
  │   └─ 聊天模式 → LLM 生成回复
  └─ 后台任务
      ├─ L7 检测负反馈 → 记录纠偏规则 → 触发 L8 补学
      └─ L8 判断是否需要自主学习 → web 搜索 → 沉淀知识
```

#### 层级边界速查

```
"用户是创业者"          → L4 user_profile.identity     ✅
"不要提晚安"            → L4 interaction_rules          ✅
"纳瓦尔宝典"            → L8 knowledge_base.json        ✅
"成长日记·最温暖的一天"  → L3 long_term.json (milestone) ✅
"MCP是什么"             → L8 knowledge_base.json        ✅
"甜心守护直接执行"       → L4 interaction_rules          ✅
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
