# NovaCore 架构说明文档

## 一、系统概述

NovaCore 是一个独立运行的本地AI智能体，不依赖OpenClaw。

- **端口**: 8090
- **位置**: `C:\Users\36459\NovaCore`
- **模型**: MiniMax-M2.5（与OpenClaw共用API）
- **架构**: 8层AI Brain

## 二、8层Brain架构

```
用户输入
    │
    ▼
L1 工作记忆 → 意图提取
    │
    ▼
L2 短期记忆 → 场景理解
    │
    ▼
L3 记忆结晶 → 经验提炼
    │
    ▼
L4 人格图谱 → 偏好匹配
    │
    ▼
L5 技能矩阵 → 触发路由（核心！）
    │
    ▼
L6 技能执行 → Skill Wrapper
    │
    ▼
L7 经验沉淀 → 负面反馈
    │
    ▼
L8 能力进化 → 自动优化
```

## 三、执行流程（完整）

```
用户: "今天天气怎么样"
    │
    ▼
L1-L2: 意图理解 (brain/__init__.py)
    │
    ▼ 匹配到 intent=weather
L5: 技能路由 (core/router.py)
    │
    ▼ 找到 exec_func="weather_query"
L6: 技能执行 (core/executor.py)
    │
    ▼ 调用 weather_query_func
    │  → wttr.in API 获取天气
    │  → 返回: "常州天气：8°C，Clear，湿度66%"
    ▼
L4: 推理 (brain/__init__.py)
    │
    ▼ LLM返回[思考步骤]+[最终回复]
    │  → 思考步骤：用户问天气，需要调用天气技能...
    │  → 最终回复：主人～常州今天8°C，晴天呢！...
    ▼
前端显示：可折叠的思考过程 + Nova风格回复
```

### 关键点
- **先执行技能 → 再让LLM回复**
- exec_func从knowledge.json的"触发器函数"字段获取
- LLM返回格式：[思考步骤] + [最终回复]
- 前端可折叠显示思考过程

## 四、目录结构

```
NovaCore/
├── agent.py          # 主入口，Web服务+前端页面
├── desktop.py        # 桌面客户端
├── brain/            # L1-L4 意图理解、推理
│   ├── __init__.py   # think()、understand_intent()、auto_learn()
│   └── llm_config.json  # LLM配置（MiniMax API）
├── core/            # 8层架构核心
│   ├── router.py    # L5 技能路由
│   ├── executor.py  # L6 技能执行
│   ├── memory_consolidator.py  # L7 经验沉淀
│   └── logger.py
├── memory/          # 记忆系统
│   └── __init__.py
├── memory_db/       # 记忆数据
│   ├── knowledge.json   # 技能知识库
│   ├── persona.json    # 人格配置（用户称呼）
│   └── long_term.json  # 长期记忆
├── skills/          # 技能定义
│   └── __init__.py
└── tools/          # 工具实现
    └── __init__.py
```

## 五、核心模块

### L1-L4: brain/__init__.py
- `understand_intent()` - 意图理解
- `think()` - LLM推理，返回 {thinking, reply}
- `auto_learn()` - L7/L8自动学习（检测"叫我xxx"、"记住xxx"）

### L5: core/router.py
- `route()` - 技能路由决策
- `parse_intent()` - 意图解析
- 自动加载knowledge.json

### L6: core/executor.py
- `execute()` - 技能执行
- `register_skill()` - 动态注册技能
- 内置技能：weather_query, run_code, tell_story等

### 记忆数据: memory_db/
- `knowledge.json` - 场景→技能映射 + 触发器函数
- `persona.json` - 用户称呼（主人/彬哥等）
- `long_term.json` - 长期记忆

## 六、工作流程

```
用户说"今天天气怎么样"
    │
    ▼
neuro_route() → L5路由判断
    │
    ▼
skill={exec_func: "weather_query", ...}
    │
    ▼
neuro_execute() → 调用 weather_query_func
    │
    ▼
返回天气结果
    │
    ▼
think() → LLM组织语言
    │
    ▼
返回 {thinking, reply}
    │
    ▼
前端显示：可折叠思考过程 + 回复
```

## 七、启动方式

### 命令行
```bash
python C:\Users\36459\NovaCore\agent.py
# 访问 http://localhost:8090
```

### 桌面客户端
```bash
python C:\Users\36459\NovaCore\desktop.py
```

## 八、与OpenClaw关系

- **完全独立**: NovaCore运行在8090端口，不依赖OpenClaw
- **API共享**: 共用MiniMax-M2.5 API
- **可联动**: 可以通过API互相调用
- **记忆独立**: 有自己的记忆系统

## 九、技能列表

| 技能 | 触发词 | 状态 |
|------|--------|------|
| 天气查询 | 天气、温度、明天、后天 | ✅ wttr.in |
| 讲故事 | 讲故事、讲个 | ✅ |
| 编程 | 做个、写个、游戏 | ✅ MiniMax生成代码 |
| 股票查询 | 股票 | ✅ |
| 自动学习 | 叫我xxx、记住xxx | ✅ 更新persona.json |

## 十、铁律

**所有回答、所有技能，必须经过L5场景路由同意，才能开口。**

流程：
1. 用户说话
2. 送给neuro_route()
3. L1意图 + L2场景 → L5查表
4. 技能才允许执行/回答

**没有路由点头 → 技能闭嘴**

## 十一、特色功能

### 思考过程显示
- LLM返回格式：[思考步骤] + [最终回复]
- 前端可折叠显示
- 点击展开/收起

### 自动学习
- 检测"叫我xxx" → 更新persona.json
- 检测"记住xxx" → 更新long_term.json

### 代码生成
- "做个猜数字游戏" → 调用MiniMax生成tkinter游戏
- 直接运行，不是只保存文件
