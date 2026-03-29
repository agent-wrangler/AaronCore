# 单步 tool_call 改造方案

> 创建：2026-03-20
> 状态：Phase 1 已实施（feature flag 默认关闭）
> 背景：参考 Claude Code / OpenClaw 的 agent 架构，将 NovaCore 从"规则路由 + 分离执行"改为"LLM 原生 tool_call"模式

## 一、为什么要改

### 现状（三次串行调用，~6.5s）
```
用户输入
  → 规则路由 + LLM lite 判断走哪个技能（2.5s）
  → executor 执行技能（1s）
  → LLM 润色回复（3s）
  = 6.5s，三次串行
```

### 目标（一次 LLM 调用 + 可选工具执行，~3s）
```
用户输入
  → 一次 LLM 调用（system prompt 带 tools 定义）
  → LLM 自己决定：
      ├─ 直接回复文本 → 完成（~3s）
      └─ 输出 tool_call → 框架执行 → 结果喂回 → LLM 继续回复（~4s）
```

### 收益
- 单步延迟从 6.5s 降到 3-4s
- 省掉独立的路由 LLM 调用（llm_route_lite）
- 回复天然带人格（同一个 LLM 上下文，不需要单独润色）
- 为多步 agent loop 打基础（每步快了，多步才跑得通）

## 二、架构对比

### 改前
```
route_resolver.py（规则 + LLM lite）
  → router.py（关键词匹配）
  → executor.py（技能分发）
  → reply_formatter.py（LLM 润色）
```
四个模块串行，路由和执行完全分离。

### 改后
```
reply_formatter.py（主 LLM 调用，带 tools）
  → 如果 LLM 返回 tool_call → executor.py 执行 → 结果喂回 LLM
  → LLM 输出最终回复
```
路由和回复合并成一次 LLM 调用，executor 变成 tool 执行器。

## 三、tools 定义

把现有 skill 转成 LLM tools 格式（以 DeepSeek function calling 为例）：

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "weather",
        "description": "查询城市天气（当前/明天/后天）",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {"type": "string", "description": "城市名，如常州、北京"},
            "day": {"type": "string", "enum": ["today", "tomorrow", "day_after"], "description": "查询哪天"}
          },
          "required": ["city"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "news",
        "description": "抓取最新热门新闻",
        "parameters": {"type": "object", "properties": {}}
      }
    },
    {
      "type": "function",
      "function": {
        "name": "story",
        "description": "讲一个有趣的故事",
        "parameters": {
          "type": "object",
          "properties": {
            "topic": {"type": "string", "description": "故事主题（可选）"}
          }
        }
      }
    }
  ]
}
```

其他技能（draw、stock、run_code、article、computer_use、model_config）同理转换。

## 四、实施步骤

### Phase 1：tool_call 基础能力（核心改动）

1. **brain/ 层支持 tool_call**
   - `brain/__init__.py` 的 `think()` / `think_stream()` 支持传入 tools 定义
   - 解析 LLM 返回的 tool_call 结构（DeepSeek 兼容 OpenAI 格式）
   - 新增 `think_with_tools(prompt, tools, dialogue_context)` 函数

2. **skill → tool 适配层**
   - 新增 `core/tool_adapter.py`：把 skill JSON 元数据转成 tools 定义
   - 每个 skill 的 `execute()` 函数不变，tool_adapter 负责调用和结果格式化

3. **reply_formatter.py 改造**
   - `unified_chat_reply` / `unified_chat_reply_stream` 改为带 tools 调用
   - 如果 LLM 返回 tool_call → 调用 tool_adapter → 结果喂回 LLM → 继续生成
   - 如果 LLM 直接回复文本 → 和现在一样

4. **routes/chat.py 简化**
   - skill 模式和 chat 模式合并：都走 `unified_chat_reply_with_tools`
   - 不再需要 `unified_skill_reply` 的独立路径
   - trace 事件：如果 LLM 决定调工具 → yield trace "调用技能"

### Phase 2：路由层降级为快速拦截

1. **保留规则路由作为快速拦截**（不删除）
   - 高置信度关键词（>= 0.95）仍然直通，不走 LLM（省钱省时间）
   - 纠偏/假设/闲聊等明确非技能场景仍然直接走 chat
   - 但不再有 `llm_route_lite` 调用

2. **route_resolver.py 简化**
   - 删除 `llm_route_lite` 和 `llm_route`（LLM 路由判断）
   - 保留 `resolve_route` 但只做规则快筛
   - 规则没命中 → 直接交给主 LLM（带 tools）自己决定

### Phase 3：流式适配

1. **tool_call 的流式输出**
   - LLM 流式输出时，先检测是否有 tool_call
   - 有 → 暂停流式，执行工具，结果喂回，继续流式
   - 无 → 正常流式输出文本

2. **前端适配**
   - 新增 SSE 事件类型 `tool_call`（前端显示"正在查询天气…"）
   - 工具执行完后继续流式输出最终回复

## 五、风险和兜底

### DeepSeek function calling 准确性
- DeepSeek 的 tool_call 不如 Claude 稳定，可能出现：不该调的调了、该调的没调
- 兜底：保留规则路由作为快速拦截层，高置信度场景不依赖 LLM 判断
- 监控：记录 tool_call 决策日志，和旧路由结果对比，评估准确率

### 向后兼容
- skill 模块（core/skills/*.py）不改，execute() 接口不变
- skill JSON 元数据不改，tool_adapter 负责转换
- 测试用例不改，patch 点不变

### 回退方案
- 保留旧的 `unified_skill_reply` 路径，用配置开关切换
- 如果 tool_call 模式效果不好，可以一键回退

## 六、后续：多步 agent loop

单步 tool_call 跑通后，多步就是在外面套一个循环：

```python
while not done and iterations < max_iterations:
    result = think_with_tools(prompt, tools, context)
    if result.has_tool_call:
        tool_result = execute_tool(result.tool_call)
        context.append(tool_result)
        iterations += 1
    else:
        done = True
        final_reply = result.text
```

吸取 OpenClaw 教训：
- 最大轮次限制（默认 5 轮）
- 单步超时保护（10s）
- 总时间上限（30s）
- 循环检测（同一个 tool 连续调 2 次 → 强制终止）
- 断点续传（中间结果存 session，断了可以继续）

## 七、涉及文件

| 文件 | 改动 |
|------|------|
| `brain/__init__.py` | 新增 think_with_tools |
| `core/tool_adapter.py` | 新建，skill → tool 转换 |
| `core/reply_formatter.py` | 改造 unified_chat_reply 支持 tool_call |
| `core/route_resolver.py` | 简化，删除 LLM 路由 |
| `routes/chat.py` | 合并 skill/chat 路径 |
| `core/skills/*.py` | 不改 |
| `core/router.py` | 保留，降级为快速拦截 |
| `core/executor.py` | 保留，被 tool_adapter 调用 |
