# NovaCore 仓库结构与目录职责

最后更新：2026-04-01

这份文档只回答一件事：仓库里每个主要目录负责什么。

相关专题：
- [Desktop_启动链与数据目录.md](C:/Users/36459/NovaCore/docs/10-架构-architecture/Desktop_启动链与数据目录.md)

## 根目录原则

- 根目录只保留稳定入口、核心源码目录和少量构建脚本。
- 临时文件、日志、截图、scratch 脚本不要长期平铺在根目录。
- `skills/` 是唯一的 skill 文档根目录。

## 主要目录

### 运行时源码

- `/core`
  运行时引擎代码。这里放协议、状态、执行桥、记忆实现、能力运行时等。
- `/routes`
  FastAPI 路由层。
- `/brain`
  模型配置、人格和高层思考相关逻辑。
- `/static`
  前端静态资源。
- `/shell`
  真正的 Electron shell 源码。

### 技能与能力

- `/skills`
  skill 文档目录。这里放系统 skill 和用户 skill 的 `SKILL.md` 包。
- `/core/skills`
  运行时 capability 包，不是 skill 文档目录。

### 状态与数据

- `/memory_db`
  主状态与记忆数据目录。
- `/memory`
  旧记忆接口层和 legacy 兼容入口。
- `/logs`
  运行日志、调试截图和其他输出产物。

### 桌面运行时

- `/desktop_runtime_35`
  当前有效的 Electron 35 启动与打包 wrapper。
- `/shell`
  被 `desktop_runtime_35` 调用的实际 Electron shell。
- `/desktop_runtime`
  遗留 Electron 依赖目录，目前不在主启动链上。

### 归档与文档

- `/archive`
  历史遗留、旧入口、旧 skills 包和 scratch 备份。
- `/docs`
  架构说明、设计记录和参考文档。
- `/tests`
  测试代码。

## 当前关键入口

- `start_nova.bat`
  桌面启动入口。
- `agent_final.py`
  Python 后端入口。
- `output.html`
  服务端拼装的首页外壳。

## 已做的根目录清理

- 根目录日志移动到 `/logs/root-legacy/`
- 调试截图移动到 `/logs/screenshots/desktop-debug/`
- scratch html/js/txt/测试脚本/备份移动到 `/archive/backups/root-scratch/`

## 当前最容易混的几个点

- `skills/` 和 `core/skills/` 不是一回事。
  前者是 skill 文档，后者是运行时能力实现。
- `memory_db/` 和 `memory/` 不是一回事。
  前者是主状态目录，后者是旧接口层。
- `.exe` 不一定直接吃打包资源。
  这一点单独见 [Desktop_启动链与数据目录.md](C:/Users/36459/NovaCore/docs/10-架构-architecture/Desktop_启动链与数据目录.md)。

## 后续整理方向

- 继续把 `/core` 按运行时职责拆成更清楚的子包。
- 在确认没有启动链依赖后，再处理 `/desktop_runtime` 是否归档。
- 让新增 skill 统一落到 `/skills/<skill-id>/SKILL.md` 这套结构。
