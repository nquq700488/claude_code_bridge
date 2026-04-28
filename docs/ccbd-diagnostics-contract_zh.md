# CCBD 诊断契约

## 1. 目的

本文档定义 `ccb_source` 中项目范围的启动/关闭报告、后端日志和支持包导出的不漂移诊断契约。

它是以下内容的权威设计锚点：

- `.ccb/ccbd/startup-report.json`
- `.ccb/ccbd/shutdown-report.json`
- `.ccb/ccbd/state.json`
- `.ccb/ccbd/start-policy.json`
- `.ccb/ccbd/lifecycle.jsonl`
- `.ccb/ccbd/heartbeats/<subject-kind>/*.json`
- `.ccb/ccbd/` 下的项目范围后端日志保留
- `ccb doctor`
- `ccb doctor --bundle`

仓库本地的内存文件 [AGENTS.md](/home/bfly/yunwei/ccb_source/AGENTS.md) 必须指向本文档，而非重复规则。

## 2. 目标

诊断必须让另一个用户无需交互式 shell 访问原始机器即可复现后端状态和失败上下文。

这意味着诊断面必须至少回答：

- 项目锚点是什么
- 哪个配置处于活跃状态
- 后端是挂载、重启、恢复还是关闭
- 哪些 agent 被期望、挂载、降级或停止
- 守护进程和 keeper 最近记录了什么
- 导出时存在哪些权威文件和事件流

## 3. 硬契约

### 3.1 项目范围

- 诊断范围限定为一个 `.ccb` 锚点。
- 所有项目诊断记录必须存在于该锚点的 `.ccb/ccbd/` 下，除了可能存在于项目外部并被引用为证据的 provider session 文件。
- 诊断导出不得将多个项目锚点合并到一个包中。

### 3.2 启动报告

路径：

- `.ccb/ccbd/startup-report.json`

最新启动报告必须捕获最近的启动相关事务，包括：

- `trigger`
  - 至少 `daemon_boot` 或 `start_command`
- `status`
  - 至少 `ok` 或 `failed`
- `generated_at`
- `daemon_generation`
- 可选 `daemon_started`
  - 前景 `ccb` 命令是否必须启动新守护进程
- `requested_agents`
- `desired_agents`
- `actions_taken`
- `agent_results`
- `inspection`
- 可选 `failure_reason`

规则：

- 守护进程启动必须写入启动报告
- 前景 `start` 必须用更具体的 `start_command` 报告覆盖它
- 启动报告写入失败不得用诊断专用错误替换原始启动错误

### 3.3 关闭报告

路径：

- `.ccb/ccbd/shutdown-report.json`

最新关闭报告必须捕获最近的关闭相关事务，包括：

- `trigger`
  - 至少 `shutdown`、`stop_all`、`kill` 或 `kill_fallback`
- `status`
- `generated_at`
- `forced`
- `stopped_agents`
- `actions_taken`
- `cleanup_summaries`
- `inspection_after`
- 可选 `failure_reason`

规则：

- 正常服务器端 stop/shutdown 必须写入关闭报告
- CLI 回退 kill 也必须写入关闭报告
- 最终持久化的关闭报告必须反映关闭后状态，而非中间预卸载快照

### 3.4 后端日志

项目后端日志必须保留在 `.ccb/ccbd/` 下：

- `ccbd.stdout.log`
- `ccbd.stderr.log`
- `keeper.stdout.log`
- `keeper.stderr.log`

规则：

- 守护进程和 keeper 必须将日志追加到稳定文件路径
- 诊断读取器必须将这些视为证据，而非权威
- 大日志可在导出期间被尾部读取，但清单必须显式标记截断

### 3.5 命名空间状态和生命周期

路径：

- `.ccb/ccbd/state.json`
- `.ccb/ccbd/start-policy.json`
- `.ccb/ccbd/lifecycle.jsonl`
- `.ccb/ccbd/heartbeats/<subject-kind>/*.json`

规则：

- `state.json` 记录最新持久化的项目 tmux 命名空间事实
- `start-policy.json` 记录持久化的项目恢复启动策略，包括继承的 `auto_permission` 和强制的恢复恢复语义
- `lifecycle.jsonl` 记录命名空间创建/销毁和后续运行时生命周期事件
- `heartbeats/<subject-kind>/*.json` 记录长寿命受监督主体（如运行中的 job）的非租约心跳状态；这些文件是诊断/证据，而非后端所有权权威
- 守护进程租约心跳和主体心跳必须保持为独立概念和独立文件
- `doctor` 和包导出必须在存在时包含这些记录
- `ping('ccbd')` 和 `doctor` 应在可用时展示启动策略摘要字段
- `ping('ccbd')` 和 `doctor` 必须在可用时展示命名空间摘要字段，如 epoch、tmux socket 路径、session 名称和最新生命周期事件
- 格式错误的命名空间诊断必须作为诊断错误展示，而非静默消失

### 3.6 Doctor 读取路径

`ccb doctor` 是尽力而为的项目诊断读取路径。

规则：

- 它必须汇总当前后端检查加最新持久化报告
- agent 绑定诊断必须在已知时同时包含 `tmux_socket_name` 和 `tmux_socket_path`，以便仅凭日志即可诊断项目范围命名空间错误
- 它不得仅因一个诊断产物缺失或格式错误而崩溃
- 格式错误的诊断文件必须作为诊断错误展示，而非静默省略

### 3.7 支持包导出

命令：

- `ccb doctor --bundle`

默认输出位置：

- `.ccb/ccbd/support/<bundle-id>.tar.gz`

支持包必须包含：

- 清单
- 生成的 doctor 快照
- 来自 `.ccb/ccb.config` 的当前项目配置
- 最新生命周期报告
- 存在时的后端权威文件，如租约、keeper、关闭意图和命名空间状态
- 存在时的后端恢复策略权威，如 `start-policy.json`
- 存在时的 `.ccb/ccbd/heartbeats/` 下的持久化非租约心跳状态
- 近期的后端事件流，如监督、命名空间生命周期和清理历史
- 后端 stdout/stderr 日志
- 每 agent 运行时权威和近期 agent/provider 日志
- 从运行时权威可发现时的相关外部 session 文件

规则：

- 包导出必须是尽力而为的，并在某些文件缺失或格式错误时继续
- 清单行必须包含原始源路径、归档路径、包含状态和截断状态
- 包导出不得要求后端健康
- 包导出必须是项目本地且足够确定以用于支持用途

### 3.8 Keeper 子进程收割

Keeper 可能直接生成 `ccbd`，但它必须收割已退出的直接子进程。

规则：

- 崩溃或被杀的 `ccbd` 进程不得仅因 keeper 仍然存活而保持为未收割的僵尸可见

## 4. 操作工作流

推荐的支持工作流：

1. 在项目锚点中复现问题
2. 运行 `ccb doctor`
3. 运行 `ccb doctor --bundle`
4. 发送生成的 tarball

包是传输单元。其中的报告是权威时间线。

## 5. 更新纪律

- 如果启动或关闭报告变更，在同一次补丁中更新本文档。
- 如果 `doctor` 或包内容发生重大变更，在同一次补丁中更新本文档。
- 将具体事件和复现发现记录在 [docs/ccbd-manual-test-issue-log.md](/home/bfly/yunwei/ccb_source/docs/ccbd-manual-test-issue-log.md) 中。
