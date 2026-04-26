# docs 文档导航

> 最后更新：2026-04-14

当前文档层级已经调整，不再把根目录 `CLAUDE.md` 视为“当前运行态的唯一权威文档”。

推荐按下面顺序理解项目：

1. **代码本身** — 最终以当前实现为准
2. 根目录 `RUNTIME.md` — 当前运行态权威文档
3. `10-架构-architecture/AaronCore_当前系统架构详解.md` — 当前系统结构总览
4. `10-架构-architecture/8层Brain架构详解.md` — L1-L8 当前分层语义说明
5. `20-使用-usage/AaronCore_CLI.md` — CLI-first 本地终端入口说明
6. 根目录 `CLAUDE.md` — 编码工具默认入口、约束摘要、快速跳转页；运行态细节不要以它为准

## 当前文档

- 根目录 `RUNTIME.md` — AaronCore 当前真实运行态主链、tool_call/CoD、电脑操作底座和上下文装载说明；当前运行态优先看它
- `20-使用-usage/AaronCore_CLI.md` — AaronCore CLI 薄壳入口、命令和 phase 1 边界
- `10-架构-architecture/AaronCore_当前系统架构详解.md` — 当前系统结构总览：入口、主链、工具运行时、状态目录、模块边界
- `10-架构-architecture/8层Brain架构详解.md` — L1-L8 各层详细说明，已按当前代码更新 L5-L8 语义
- `10-架构-architecture/AaronCore_运行质量门说明.md` — runtime replay eval、benchmark、quality gate 的日常使用入口

## 历史归档

- `99-归档-archive/` — 所有过时的方案文档、旧版架构说明
- `99-归档-archive/CoD 设计演进（归档摘要）.md` — CoD 历史设计稿的合并摘要

## 开源准备

- `30-开源-open-source/AaronCore_开源整理草案.md` - AaronCore 公开仓的定位、边界与整理原则
- `30-开源-open-source/AaronCore_state_data_public_boundary.md` - `state_data/` 的公开边界、模板策略与私有真值划分
