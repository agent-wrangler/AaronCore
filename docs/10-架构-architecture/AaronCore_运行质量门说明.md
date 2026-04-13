# AaronCore 运行质量门说明

> 最后更新：2026-04-14

这份文档只讲一件事：现在仓库里怎么快速检查 runtime continuity、replay regressions 和 benchmark 健康度。

## 1. 默认入口

日常先跑这个：

```bat
scripts\run_runtime_quality.bat
```

它当前等价于：

```bat
python tools\runtime_quality_gate.py
```

默认会同时做两件事：

1. 跑 `full_runtime_regressions` 的 replay eval dry-run
2. 汇总 benchmark 历史状态

默认输出只保留 summary，适合日常看板式检查。

## 2. 接到 git 提交前

安装本地 pre-commit hook：

```bat
scripts\install_runtime_quality_hook.bat
```

卸载本地 pre-commit hook：

```bat
scripts\uninstall_runtime_quality_hook.bat
```

安装后，仓库会把本地 `core.hooksPath` 指到版本化的 `.githooks/`，提交前自动执行：

```bat
python tools\runtime_quality_gate.py --strict
```

这里只拦真正的 fail，不拦 summary 级别的 warning。

## 3. 结果怎么理解

`runtime_quality_gate.py` 的顶层 `summary.status` 现在有三种值：

- `pass`
  replay 全过，benchmark 侧也没有 warning
- `warn`
  replay 没挂，但 benchmark 历史还有脏数据、长期 skip、orphaned 记录之类的问题
- `fail`
  replay 失败，或者显式运行 benchmark 时出现 `skip/crash`

## 4. 常用命令

看详细输出：

```bat
scripts\run_runtime_quality.bat --details
```

预演全部 benchmark，但不真的写结果：

```bat
scripts\run_runtime_quality.bat --benchmark-all --benchmark-dry-run
```

真的把全部 tracked benchmark 各跑一轮：

```bat
python tools\benchmark_runner.py --all --rounds 1
```

归档 `results.tsv` 里已经不再被 `experiments.json` 跟踪的历史记录：

```bat
python tools\benchmark_runner.py --archive-orphaned
```

只跑 replay eval：

```bat
python tools\live_llm_replay.py --suite full_runtime_regressions --dry-run
```

## 5. 当前边界

- `runtime_quality_gate.py` 负责总览，不替代单独 runner
- `live_llm_replay.py` 负责 runtime regressions / eval suite
- `benchmark_runner.py` 负责 benchmark 历史、批跑、归档
- `.githooks/pre-commit` 负责提交前自动触发 quality gate
- `results.tsv` 现在只保留 tracked experiments
- `results.orphaned.tsv` 保留旧历史，不再参与主 quality gate

## 6. 建议用法

改 continuity、session、runtime state、tool-call prompt 这类逻辑时，先跑：

```bat
scripts\run_runtime_quality.bat
```

如果输出是 `warn`，先看 benchmark warning 是历史卫生问题，还是新回归。

如果改了 `verify.py`、`story.py` 或实验数据，再补一轮：

```bat
python tools\benchmark_runner.py --all --rounds 1
scripts\run_runtime_quality.bat
```
