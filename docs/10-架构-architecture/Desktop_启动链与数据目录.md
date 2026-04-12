# Desktop 启动链与数据目录

最后更新：2026-04-01

这份文档专门解释桌面 `.exe` 到底从哪里启动、连哪份后端、读哪份数据。

## 结论先说

在你这台机器上，桌面版 `.exe` 当前优先连的是开发仓库：

- 代码根：`C:\Users\36459\AaronCore`
- 后端入口：`C:\Users\36459\AaronCore\agent_final.py`
- 状态目录：`C:\Users\36459\AaronCore\memory_db`

不是默认退回打包目录里的 `resources/novacore/memory_db`。

## 实际启动链

桌面启动链是：

1. `AaronCore.exe`（兼容回退到 `NovaCore.exe`）
2. `desktop_runtime_35/main.js`
3. `shell/main.js`
4. `agent_final.py`
5. `http://localhost:8090/`

对应文件：

- [desktop_runtime_35/main.js](C:/Users/36459/AaronCore/desktop_runtime_35/main.js)
- [shell/main.js](C:/Users/36459/AaronCore/shell/main.js)
- [agent_final.py](C:/Users/36459/AaronCore/agent_final.py)

## `.exe` 怎么决定代码根目录

关键逻辑在 [desktop_runtime_35/main.js](C:/Users/36459/AaronCore/desktop_runtime_35/main.js)。

打包态下，`NOVACORE_ROOT` 的优先级是：

1. `NOVACORE_DEV_ROOT`
2. `.exe` 同级的开发仓库目录
3. `process.resourcesPath/novacore`

也就是说，只有前两项都找不到时，才会退回打包资源目录。

## 为什么这台机器命中开发仓库

当前目录关系是：

- 桌面目录：`C:\Users\36459\AaronCoreDesktop`
- 开发仓库：`C:\Users\36459\AaronCore`

`desktop_runtime_35/main.js` 会把 `NovaCoreDesktop` 去掉 `Desktop` 后缀，尝试找同级的 `NovaCore`。这一台机器刚好存在，所以 `.exe` 会优先命中开发仓库。

## 后端怎么读数据目录

状态目录不是 shell 决定的，而是 [core/runtime_state/state_loader.py](C:/Users/36459/AaronCore/core/runtime_state/state_loader.py) 决定的。

里面当前的主路径是：

- `PRIMARY_STATE_DIR = ENGINE_DIR / "memory_db"`

而 `ENGINE_DIR` 最终来自当前运行的 `NOVACORE_ROOT`。

所以当 `.exe` 连的是开发仓库时，主状态目录自然就是：

- `C:\Users\36459\AaronCore\memory_db`

## 为什么容易误判成“用了打包目录”

最常见的误判有两个：

- 只看到了打包 fallback 分支，没看到“开发仓库优先”的分支
- 直接用带代理环境的请求去访问 `localhost:8090`，被代理层误导成后端坏了

正确验证方式应该是：

- 读启动链代码
- 看 `8090` 监听进程的命令行
- 用不走代理的本地请求访问 `127.0.0.1:8090`

## 出问题时怎么快速判断

先看这三件事：

1. `desktop_runtime_35/main.js` 里的 `resolveAaronCoreRoot()`
2. `shell/main.js` 里实际启动的 `BACKEND_ENTRY`
3. `core/runtime_state/state_loader.py` 里的 `PRIMARY_STATE_DIR`

如果还不确定，再看：

- 当前 `8090` 是哪个 `python.exe` 在监听
- 它的命令行是不是 `C:\Users\36459\AaronCore\agent_final.py`

## 一句话记忆

在这台机器上：

**`.exe` 不是优先吃打包资源，而是优先吃同级开发仓库；只要开发仓库存在，数据就是开发仓库那份 `memory_db`。`**
