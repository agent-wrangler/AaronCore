# AaronCore 仓库结构与目录职责

最后更新：2026-04-26

这份文档只回答一件事：仓库里每个主要目录负责什么。

## 根目录原则

- 根目录只保留稳定入口、核心源码目录和少量构建脚本。
- 临时文件、日志、截图、scratch 脚本不要长期平铺在根目录。
- `skills/` 是 skill 一级类目：既是 skill 文档根，也承载内建用户可见技能实现。

## 主要目录

### 运行时源码

- `/core`
  运行时引擎代码。这里放协议、状态、执行桥、记忆实现、能力运行时等。
- `/routes`
  FastAPI 路由层。
- `/brain`
  模型配置、人格和高层思考相关逻辑。

### 技能与能力

- `/skills`
  skill 一级类目。这里放系统/用户 skill 文档，以及内建用户可见技能实现。
- `/skills/builtin`
  内建 workflow/domain 技能的真实运行时代码与元数据。
- `/capability_registry`
  运行时技能注册与装载边界；负责发现 `tools/agent` 和 `skills/builtin`。
- `/core/skills`
  兼容包；保留旧导入路径，不再承载新的真实技能实现。

### 状态与数据

- `/state_data`
  主状态与记忆数据目录。
- `/memory`
  旧记忆接口层和 legacy 兼容入口。
- `/logs`
  运行日志、调试截图和其他输出产物。

### 归档与文档

- `/archive`
  历史遗留、旧入口、旧 skills 包和 scratch 备份。
- `/docs`
  架构说明、设计记录和参考文档。
- `/tests`
  测试代码。

## 当前关键入口

- `aaron.py` / `aaron.bat` / `aaroncore.bat`
  终端 CLI 入口，默认走 direct in-process runtime。
- `agent_final.py`
  Python 后端/API 调试入口。
- `requirements-cli.txt`
  终端运行依赖清单。

## 已做的根目录清理

- 根目录日志移动到 `/logs/root-legacy/`
- 调试截图移动到 `/logs/screenshots/`
- scratch html/js/txt/测试脚本/备份移动到 `/archive/backups/root-scratch/`

## 当前最容易混的几个点

- `skills/` 和 `core/skills/` 不是一回事。
  前者是一级类目；真实 builtin 技能实现在 `skills/builtin/`，`core/skills/` 只是兼容层。
- `state_data/` 和 `memory/` 不是一回事。
  前者是当前主状态目录，后者是旧接口层。
## 后续整理方向

- 继续把 `/core` 按运行时职责拆成更清楚的子包。
- 让新增 skill 统一落到 `/skills/<skill-id>/SKILL.md` 这套结构。
