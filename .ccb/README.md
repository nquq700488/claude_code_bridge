# CCB 项目脚本模板

本目录包含 `ccb` 的启动/停止/重启脚本，与项目配置一起作为模板使用。

## 配置档案

分屏布局有两套写法，通过 `ccb.config` 的一行路由器切换。`ccb.config` 本身不含布局，只指定用哪一份档案：

```toml
config_profile = "compact"   # 单窗口 4-agent 紧凑布局
# config_profile = "multi"   # 双窗口分屏布局
```

切换后运行 `ccb reload` 生效，无需重启。

### 方式一：compact — 单窗口紧凑布局

所有 agent 在**同一个 tmux 窗口**内，用经典单行布局语法：

```text
(planner:codex; developer:claude), (reviewer:codex; tester:kimi)
```

```text
┌───────────────┬───────────────┐
│    planner    │  developer    │
│    (codex)    │  (claude)     │
├───────────────┼───────────────┤
│   reviewer    │   tester      │
│   (codex)     │   (kimi)      │
└───────────────┴───────────────┘
```

### 方式二：multi — 双窗口分屏布局

使用 v2 格式（`version = 2` + `[windows]`），每个窗口一套独立布局：

```toml
version = 2
entry_window = "main"

[windows]
main   = "planner:codex; developer:codex"
work   = "reviewer:claude; tester:kimi"
# test   = "tester:kimi"     # 已注释，当前未启用
```

```text
窗口 main:  窗口 work:
┌──────────┬──────────┐   ┌──────────┬──────────┐
│ planner  │developer │   │ reviewer │  tester  │
│ (codex)  │ (codex)  │   │ (claude) │  (kimi)  │
└──────────┴──────────┘   └──────────┴──────────┘
```

> **两套档案的 provider 分配不同**（同一个 agent 名在不同档案里可绑定不同 provider）：
> `developer` 在 compact 是 Claude、在 multi 是 Codex；`reviewer` 在 compact 是 Codex、在 multi 是 Claude。
> 切换档案后以对应文件为准。

两套档案都只含 4 个 agent：`planner` / `developer` / `reviewer` / `tester`。
`inspiration`（OpenCode）在 compact 中不存在，在 multi 中定义为注释状态。

## 使用

```bash
# 通过 .ccb/ 目录调用
./.ccb/start.sh       # 启动 ccb（已运行则提示）
./.ccb/stop.sh        # 停止 ccb
./.ccb/stop.sh -f     # 强制停止
./.ccb/restart.sh     # 重启 ccb
./.ccb/restart.sh -f  # 强制清理后重启
```

## 参数说明

| 脚本 | 参数 | 说明 |
|------|------|------|
| `start.sh` | `-s` / `--safe` | 安全模式启动 |
| `start.sh` | `-n` / `--new` | 重建后启动 |
| `stop.sh` | `-f` / `--force` | 强制清理后停止 |
| `restart.sh` | `-f` | 强制清理后重启 |
| `restart.sh` | `-s` | 安全模式重启 |
| `restart.sh` | `-n` | 重建后重启 |

## 前提条件

- 已全局安装 `ccb`
- 本项目已创建 `ccb.config`
