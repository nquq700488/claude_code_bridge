# CCBD 启动与监督契约

## 1. 目的

本文档定义 `ccb_source` 中项目范围启动、后端所有权、运行时监督、窗格恢复和 kill/关闭行为的不漂移契约。

它是以下内容的权威设计锚点：

- `ccb` 启动行为
- `ccb open` 附着行为
- `ccbd` 守护进程生命周期
- 项目范围运行时所有权
- 配置 agent 挂载
- 窗格/session/运行时恢复
- `ccb kill` 语义

仓库本地的 agent 内存文件 [AGENTS.md](/home/bfly/yunwei/ccb_source/AGENTS.md) 必须始终指向本文档，而非重复它。

诊断专用规则存在于 [docs/ccbd-diagnostics-contract.md](/home/bfly/yunwei/ccb_source/docs/ccbd-diagnostics-contract.md) 中。启动/关闭行为和诊断必须一起演进。

项目范围 tmux 命名空间模型的模块/函数级重新设计存在于 [docs/ccbd-project-namespace-lifecycle-plan.md](/home/bfly/yunwei/ccb_source/docs/ccbd-project-namespace-lifecycle-plan.md) 中。

窗格恢复分层和连续前景附着的详细重新设计存在于 [docs/ccbd-pane-recovery-continuous-attach-plan.md](/home/bfly/yunwei/ccb_source/docs/ccbd-pane-recovery-continuous-attach-plan.md) 中。

面向用户的配置和 tmux 布局规则存在于 [docs/ccb-config-layout-contract.md](/home/bfly/yunwei/ccb_source/docs/ccb-config-layout-contract.md) 中。启动行为必须尊重该布局契约，而非发明自己的窗格拓扑。

## 2. 问题陈述

当前代码库已包含所需行为的片段：

- 通过租约/锁的项目范围后端所有权
- 运行时检查和窗格健康检查
- provider 端 `ensure_pane()` 恢复钩子
- 下次命令时守护进程重启行为
- stop/kill 清理逻辑

但这些片段目前尚未形成单一的始终在线控制面契约。

主要失败模式是结构性的：

- 启动权威分散在配置、租约、运行时存储、provider session 文件和 tmux 事实中
- 运行时恢复已部分实现，但仅在部分路径上执行
- 窗格死亡可将 agent 标记为降级，而不触发守护进程拥有的协调循环
- 关闭行为分散在服务器端和 CLI 回退逻辑之间

本文档首先修复契约边界，以便后续实现不会漂移回零散补丁。

## 3. 范围

在范围内：

- 每个 `.ccb` 锚点一个后端
- 守护进程启动和接管规则
- 配置 agent 期望状态规则
- 运行时监督和恢复规则
- 窗格死亡处理
- `.ccb/ccbd/` 下的记录
- `ccb kill` 端到端语义
- 启动和恢复测试矩阵

不在范围内：

- provider 特定的 prompt/协议细节
- 完成提取策略
- 除非依赖运行时活跃度的 mailbox/消息语义

## 4. 术语

- `project anchor`
  - 包含 `.ccb/` 的目录
- `project backend`
  - 一个项目锚点的唯一权威 `ccbd` 进程
- `desired agents`
  - 由 `.ccb/ccb.config` 定义的配置 agent 集
- `authority`
  - 被允许定义当前项目真相的状态来源
- `evidence`
  - 用于恢复决策的可观察事实，但不允许重新定义权威
- `residue`
  - 来自先前运行、重命名或损坏的陈旧或额外状态；仅作为清理输入
- `runtime supervision`
  - 守护进程拥有的保持期望 agent 挂载和健康的循环
- `keeper`
  - 在崩溃后重启 `ccbd` 的小型看门狗进程；它不是项目后端

## 5. 硬契约

### 5.1 项目范围

- 一个 `.ccb` 锚点定义一个项目控制面范围。
- 拥有 `.ccb/` 的目录是该项目的唯一权威根。
- 项目生命周期状态必须仅存在于该项目 `.ccb/` 下。
- 启动、监督和关闭必须按项目锚点推理，从不全局推理。

### 5.2 唯一权威后端

- 每个项目锚点最多可有一个权威 `ccbd` 后端。
- `lease.json` 加启动锁加 socket 所有权定义后端权威。
- 第二个 `ccbd` 仅可通过显式接管规则替换当前守护进程。
- Provider 特定的后台守护进程不得成为竞争的项目权威。

### 5.3 期望 Agent 集

- `.ccb/ccb.config` 是项目期望 agent 挂载集和前景布局的唯一前向权威。
- `.ccb/ccb.config` 逻辑名称也是项目命名空间窗格显示名称的唯一前向权威。
- 在出现显式 `enabled` 或 `desired_state` 字段之前，所有配置 agent 都是期望 agent。
- `default_agents` 和 CLI `requested_agents` 不重新定义长寿命后端所有权。
- `requested_agents` 仅可影响前景行为或热启动顺序。

### 5.4 权威层级

权威顺序必须精确执行如下：

1. `.ccb/ccb.config`
2. `.ccb/ccbd/lease.json`
3. `.ccb/ccbd/start-policy.json`
4. 当前守护进程代际的 `.ccb/agents/<configured-agent>/runtime.json`

证据来源：

- provider session 文件
- tmux 窗格活跃度
- provider 运行时 pid 文件
- runtime-root 内容

残留来源：

- `.ccb/agents/<unknown-agent>/`
- 陈旧 session 文件
- 先前代际的陈旧运行时文件
- 格式错误的运行时文件

规则：

- 证据可指导恢复
- 残留可指导清理
- 配置 agent 的 provider session 文件按 `.ccb/ccb.config` 逻辑 agent 名称限定为 agent 范围
- 基于 provider 的 session 文件（如 `.codex-session` 或 `.claude-session`）仅是旧版或无范围证据：
  - 它们不得被重新解释为配置 agent 的身份
  - 仅在无显式 agent 绑定时可咨询
- 残留（如 provider session 文件或保留的工作区）不得自身阻止配置引导
- 证据和残留均不得静默重新定义权威
- 运行时 pid 丢失仅是证据；对于 pane-backed 运行时，它不得抢占基于窗格/session 的恢复检查

缺失配置恢复规则：

- 如果 `.ccb/ccb.config` 缺失且锚点为空，引导可写入默认配置
- 如果 `.ccb/ccb.config` 缺失且 `.ccb/agents/*/agent.json` 提供完整的可恢复 agent 规范集，引导可从这些规范重建 `.ccb/ccb.config`
- 如果 `.ccb/ccb.config` 缺失且权威状态存在但 agent 规范不完整或格式错误，启动仍必须明确失败，而非发明项目真相

运行时启动策略规则：

- `.ccb/ccbd/start-policy.json` 记录当前项目运行的恢复启动策略
- `auto_permission` 是继承的项目运行时策略，非一次性窗格本地标志
- 恢复恢复不是从原始 CLI 调用继承的；守护进程拥有的恢复必须始终使用恢复语义
- 无显式标志的普通前景 `ccb` 定义为 `restore=true` 和 `auto_permission=true`
- 因此：
  - 显式前景 `ccb` 启动使用 CLI 提供的 `restore` 标志和 `auto_permission` 标志
  - 守护进程拥有的恢复挂载、窗格恢复、命名空间重流和崩溃后重新挂载必须始终使用 `restore=true`
  - 这些相同的守护进程拥有的恢复路径必须复用来自 `.ccb/ccbd/start-policy.json` 的持久化 `auto_permission` 策略
- `ccb kill` / 项目 stop-all 必须清除 `.ccb/ccbd/start-policy.json`

### 5.5 启动事务

启动必须是单一项目范围的事务：

1. 检查锚点状态
2. 检查配置状态
3. 检查后端租约/socket/心跳状态
4. 确保项目 tmux 命名空间
5. 计算期望 agent
6. 计算恢复/启动计划
7. 提交启动动作
8. 发出启动结果并持久化启动报告

仅当以下条件满足时，`start_status: ok` 才有效：

- 项目后端健康且权威
- 项目 tmux 命名空间存在于 `.ccb/ccbd/` 下记录的项目拥有的 socket/session
- 项目 tmux 命名空间在该项目拥有的 socket/session 上应用了当前 session 范围的 CCB UI 契约
- 该项目 session 包含当前命名空间窗口契约：
  - 一个用作长寿命 session 锚点的控制窗口
  - 一个用作可见窗格布局锚点的工作区窗口
- 项目生成的 tmux 标识符必须保持 tmux 目标安全：
  - 项目命名空间 session 名称必须在使用为 tmux 目标前规范化
  - 瞬态工作区重流操作必须通过 tmux `window_id` 寻址窗口，而非临时点分窗口名称
- 配置对当前锚点有效
- 期望 agent 已达到可接受的挂载状态

可接受的挂载状态意味着以下之一：

- 健康且已附着
- 正在恢复，带有显式持久化原因和活跃协调所有权

它绝不意味着：

- 陈旧绑定被接受为成功
- 缺失配置在有现有项目状态时仍被静默替换
- 降级运行时被报告为健康启动完成

前景命令分割：

- `ccb`
  - 确保后端权威
  - 确保项目 tmux 命名空间
  - 确保期望 agent 已挂载
  - 普通 `ccb` 是默认交互式启动路径，隐式包含 `-a -r`
  - 不自行定义 UI 附着成功
- `ccb -n`
  - 是启动前的显式破坏性项目重置
  - 必须要求交互式确认
  - 必须清除并重建所有项目拥有的 `.ccb` 运行时状态、日志、session、工作区和邮件/消息残留
  - 存在时必须精确保留 `.ccb/ccb.config`
  - 不存在 `.ccb/ccb.config` 时，重置后启动可引导默认配置
  - 同一调用随后必须通过正常的 `ccb` 启动事务继续，而非使用单独的启动实现
  - 重置后的首次启动必须强制 `restore=false`，以便 provider 全局历史无法静默重新附着旧对话
  - 新鲜重置后启动完成后，后续普通 `ccb` 运行回到默认 `-a -r` 语义
- `ccb open`
  - 仅附着到现有项目命名空间
  - 必须在附着完成前选择该 session 内的权威工作区窗口
  - 不得创建新守护进程、命名空间或期望 agent 计划
  - 命名空间权威缺失时必须明确失败

项目命名空间兼容性：

- 命名空间 `layout_version` 覆盖可见窗格拓扑和项目 socket tmux UI 契约，而非仅分割几何
- 项目命名空间状态还必须持久化从 `.ccb/ccb.config` 前景裁剪后产生的当前可见布局签名
- 当存储的命名空间 `layout_version` 与当前代码契约不同时，启动必须重新创建项目命名空间，而非尝试就地变更陈旧 session
- 当存储的可见布局签名与当前前景启动的期望可见布局签名不同时，启动必须重新创建项目命名空间，而非增量分割旧窗格树
- 当启动创建全新项目命名空间 session 时，根窗格必须开始为静默占位进程，而非交互式 shell
- 对于全新命名空间，`cmd` 窗格引导仅在布局完成后发生，且必须就地替换该静默占位
- 启动不得依赖 "先启动真实 shell，再 respawn" 的 `cmd` 窗格行为，因为这会留下陈旧 prompt 残留并可能显示 zsh no-newline `%` 标记
- `cmd` 锚定项目必须将精确的项目命名空间窗格成员身份视为 pane-backed 绑定的复用门
- 对于项目命名空间复用，精确成员身份意味着：
  - 同一项目拥有的 tmux socket
  - 同一权威 tmux session
  - 同一逻辑 `slot_key`
  - 同一当前权威工作区 `window_id`
- 禁用 `cmd` 的仅 agent 旧版布局可在该 session 文件未显式声明冲突 tmux socket 时复用实例范围的 provider session 证据
- 该旧版复用例外是狭窄的：
  - 如果 session 文件显式声明 tmux socket 且它不是项目 socket，启动必须拒绝它
  如果同 socket 窗格检查证明窗格属于分离的兄弟 session 或外部项目身份，启动必须拒绝它
  - 推断的默认服务器 socket 事实不得覆盖否则有效的实例范围旧版绑定

### 5.6 运行时监督是守护进程职责

项目后端必须持续保持期望 agent 挂载。

当 `.ccb/ccb.config` 启用 `cmd` 时，后端还必须持续保持权威工作区窗口内项目拥有的 `cmd` 槽位存在且健康。

此职责属于守护进程拥有的监督循环，而非：

- 下一个 CLI 命令
- 下一个 job 启动
- 像 `ps` 或 `doctor` 这样的偶然读取路径
- 像 `HealthMonitor.check_all()` 这样的健康检查路径

监督循环必须在后端心跳/tick 上运行，并协调每个期望 agent，无论是否有排队工作。

对于启用 `cmd` 的项目：

- `cmd` 是项目命名空间槽位，非 `AgentRegistry` 中的条目
- 因此 `cmd` 监督必须在命名空间层发生，而非假装 `cmd` 是 provider 运行时
- 健康的 `cmd` 槽位意味着权威工作区根窗格仍匹配：
  - `role=cmd`
  - `slot_key=cmd`
  - `managed_by=ccbd`
  - 当前权威工作区 `window_id`

### 5.7 窗格死亡恢复契约

当期望 agent 的窗格死亡时，守护进程必须按此顺序在后台协调它：

1. 检查当前运行时权威
2. 检查 provider session 和终端事实
3. 如果 `ensure_pane()` 可恢复窗格，就地重新绑定运行时权威
4. 如果原始窗格目标已消失但当前项目工作区窗口仍健康，本地恢复必须在当前工作区窗口内创建替换窗格，并立即将其重新绑定到同一逻辑 `slot_key`
5. 否则，如果项目 tmux session 仍健康且需要命名空间级修复，在同一 session 内重流工作区窗口，并在那里重新启动配置布局
6. 否则，如果运行时事实证明 session 级损坏且全项目重流安全，重新创建项目命名空间并重新启动配置布局
7. 否则拆除陈旧绑定权威
8. 通过正常启动路径重新启动运行时
9. 持久化恢复结果和重试/退避状态

重要规则：

- 即使 agent 空闲且没有新 job 到达，恢复也必须发生
- 当 `cmd` 启用时，`cmd` 的窗格死亡或槽位漂移也必须在心跳上检测和修复，即使没有用户命令在该窗格中运行
- `cmd` 恢复必须首先尝试 session 保留的本地槽位替换，然后再升级到项目重流
- 普通的 `pane-dead` / `pane-missing` 恢复不得将项目服务器销毁作为首选路径
- pane-backed 运行时权威必须携带 `slot_key`、当前工作区 `window_id` 和 `workspace_epoch`；窗格 id 是证据，非身份
- 本地替换必须针对该项目 session 的权威当前工作区窗口，而非 provider 后端默认创建的任意 tmux 目标
- 如果本地替换在项目拥有的命名空间内更改窗格 id，且全项目重流当前安全，守护进程必须立即继续进入 session 保留的工作区重流，使窗格回到规范布局位置
- session 保留的工作区重流是 `pane_recovery:*` 的首个命名空间级升级
- 如果本地替换无法恢复 `cmd`，`cmd` 槽位恢复必须通过同一 session 保留的 `pane_recovery:*` 重流路径升级，以 `pane_recovery:cmd` 作为规范原因
- 如果窗格恢复由项目命名空间重流完成，窗格位置必须回到从 `.ccb/ccb.config` 派生的规范布局，而非本地恢复期间 tmux 碰巧分配的槽位
- 工作区重流必须保留 tmux 服务器和 tmux session；仅工作区窗口可被替换
- 即使原始前景 `ccb` 调用未传递 `-r`，恢复也必须始终使用恢复语义
- 恢复必须从持久化的项目启动策略继承 `auto_permission`，而非回退到硬编码默认值

项目命名空间重流安全规则：

- 全项目重流是升级路径，非普通窗格死亡的默认响应
- 仅当受影响运行时属于 `.ccb/ccbd/` 下记录的项目拥有的 tmux socket/session 时，才允许 session 保留的工作区重流
- 仅当 session 本身不再是可信的修复边界时，才允许全项目重流
- 仅当没有其他配置 agent 当前为 `BUSY` 时才重流
- 如果重流不安全，回退到本地 provider 恢复，而非干扰无关工作

项目 socket 清理规则：

- 启动必须计算当前项目拥有的 tmux socket 的权威活跃窗格集
- 同 socket 窗格/session 残留仅是证据；不得仅因为它存在于项目 socket 上就静默容忍
- 启动必须在启动事务期间清理项目拥有的 socket 上的孤儿窗格，而非等待后续手动清理路径

### 5.8 守护进程不得保持死亡

严格满足"后端不得死亡"需要在 `ccbd` 本身之外的进程。

目标架构：

- `ccbd` 仍是唯一权威项目后端
- 轻量级项目范围 `keeper` 进程监控它
- keeper 可在崩溃后重启 `ccbd`
- keeper 从不拥有项目运行时权威
- keeper 必须收割已退出的直接子进程，以便崩溃的 `ccbd` pid 不会作为僵尸证据滞留
- keeper/CLI 强制接管仅在租约进入真正的接管窗口后才允许：
  - `MISSING`
  - `UNMOUNTED`
  - `STALE`
- 带有活跃 pid 加新鲜心跳的 `DEGRADED` 仅是观察，非重启权威，即使项目 socket 暂时不可达
- 因此活跃工作期间的临时 UNIX-socket 接受停滞必须表现为降级可用性，而非 keeper 触发的守护进程替换

如果 keeper 缺失，系统只能提供"下次 `ccb` 命令时重启"，这比目标契约更弱。

当 `ccb` 在显式关闭后重新进入项目时，启动必须先清除先前的关闭意图，然后 keeper/守护进程保活才能恢复。

### 5.9 Kill 和关闭事务

项目锚点的 `ccb kill` 必须执行单一关闭事务：

1. 获取关闭意图
2. 阻止 keeper 重启
3. 停止新摄入
4. 停止运行中的 agent 执行
5. 停止所有期望 agent
6. 在项目拥有的 socket/session 销毁项目 tmux 命名空间
7. 终止在命名空间销毁后存活的 provider 运行时 pid
8. 将配置 agent 运行时权威标记为已停止
9. 卸载后端租约
10. 关闭 socket 服务器
11. 持久化关闭报告

关闭必须对残留尽力而为，对权威严格。

这意味着：

- 格式错误或未知的残留不得阻塞 kill
- 配置 agent 权威必须以干净的停止/卸载状态结束
- 一旦获取关闭意图，后端不得在相同关闭事务中运行任何可能重新挂载期望 agent 的协调/心跳 tick
- 本地守护进程关闭辅助函数不得在 `mark_unmounted()` 加 socket 关闭处停止；它们必须先运行相同的 stop-all 清理事务，以便 provider 运行时 pid 文件、命名空间状态和配置 agent 权威不会在后端本地关闭中存活

## 6. 必需的运行时状态

至少，监督模型必须区分以下状态：

- `unmounted`
- `starting`
- `healthy`
- `recovering`
- `degraded`
- `stopped`
- `failed`

对于期望 agent，`recovering` 和 `degraded` 不同：

- `recovering`
  - 守护进程当前拥有活跃的协调尝试
- `degraded`
  - agent 不健康，且尚无活跃恢复成功

当前代码已记录 `degraded`，但目标契约需要独立的受监督恢复状态。

## 7. `.ccb` 下的记录

需要以下记录。

### 7.1 后端权威

路径：

- `.ccb/ccbd/lease.json`
- `.ccb/ccbd/state.json`

必需字段：

- `project_id`
- `ccbd_pid`
- `namespace_epoch`
- `tmux_socket_path`
- `tmux_session_name`
- `socket_path`
- `generation`
- `started_at`
- `last_heartbeat_at`
- `mount_state`
- `config_signature`
- 可选 `keeper_pid`
- 可选 `daemon_instance_id`

### 7.2 启动报告

路径：

- `.ccb/ccbd/startup-report.json`

必需目的：

- 捕获启动成功、失败、接管或恢复的原因

最少内容：

- 锚点状态
- 配置状态
- 守护进程检查
- 期望 agent
- 已执行动作
- 最终状态

### 7.3 监督事件日志

路径：

- `.ccb/ccbd/supervision.jsonl`

必需目的：

- 窗格死亡检测、重新启动尝试、恢复失败和成功转换的仅追加记录

### 7.4 Agent 运行时权威

路径：

- `.ccb/agents/<agent>/runtime.json`

超出当前基线的必需字段：

- `daemon_generation`
- `desired_state`
- `reconcile_state`
- `restart_count`
- `last_reconcile_at`
- `last_failure_reason`
- 可选 `tmux_socket_name`
- 可选 `tmux_socket_path`

`.ccb/agents/` 下的未知 agent 目录是残留，除非它们存在于当前配置中。

### 7.5 Keeper 状态

路径：

- `.ccb/ccbd/keeper.json`

必需目的：

- 记录当前拥有守护进程保活的项目范围 keeper 进程
- 使 keeper 重启尝试和近期失败原因可检查，而不将 keeper 视为后端权威

最少内容：

- `project_id`
- `keeper_pid`
- `started_at`
- `last_check_at`
- `state`
- `restart_count`
- 可选 `last_restart_at`
- 可选 `last_failure_reason`

### 7.6 关闭意图

路径：

- `.ccb/ccbd/shutdown-intent.json`

必需目的：

- 持久化显式关闭意图，以便 keeper 不会在 `ccb kill` 期间或之后重启 `ccbd`

最少内容：

- `project_id`
- `requested_at`
- `requested_by_pid`
- `reason`

### 7.7 诊断包

命令：

- `ccb doctor --bundle`

必需目的：

- 导出一个项目范围的支持产物，足以在无需交互式 shell 访问的情况下进行远程错误分类

必需内容：

- 最新启动/关闭/恢复报告
- 后端权威文件
- 后端 stdout/stderr 日志
- 监督和清理事件历史
- 每 agent 运行时权威和近期 provider/运行时日志
- 显式标记缺失或截断文件的清单行

## 8. 实现形态

设计应向以下领域收敛：

- `startup inspection`
- `startup policy`
- `startup transaction`
- `runtime supervision`
- `shutdown transaction`
- `reporting/read path`

推荐的模块分割：

- `lib/ccbd/startup/inspection.py`
- `lib/ccbd/startup/policy.py`
- `lib/ccbd/startup/transaction.py`
- `lib/ccbd/supervision/inspector.py`
- `lib/ccbd/supervision/loop.py`
- `lib/ccbd/shutdown/transaction.py`
- `lib/ccbd/reports/startup_report.py`

关键规则不是确切的包名。关键规则是分离：

- 先检查
- 再决定
- 最后变更

## 9. 当前代码对齐和差距

当前代码已在某些地方与契约对齐：

- 唯一后端所有权部分由 `OwnershipGuard` 强制执行
- `CcbdApp` 中存在心跳和租约刷新
- `HealthMonitor` 中存在窗格/session 检查
- provider 恢复钩子通过 `ensure_pane()` 存在
- 运行时重新启动支持存在于运行时启动路径中

但有一个关键差距：

- 恢复不由连续的守护进程监督循环拥有

当前行为：

- `HealthMonitor` 可检测窗格死亡并有时修复绑定
- 进一步恢复主要在新 job 即将启动时尝试

目标行为：

- 守护进程心跳本身必须持续协调期望 agent

这个差距是当前系统可能"知道如何恢复"，但在窗格死亡后仍无法保持空闲 agent 挂载的主要原因。

## 10. 分阶段交付

### A 阶段：契约保持

- 每个锚点保持一个权威后端
- 保持配置作为期望 agent 权威
- 保持残留不阻塞 kill
- 停止静默权威漂移

### B 阶段：运行时监督循环

- 为所有期望 agent 添加守护进程拥有的协调循环
- 无需等待 job 启动即可恢复窗格死亡
- 持久化监督状态和重试/退避

### C 阶段：Keeper

- 添加项目范围 keeper
- 崩溃后重启 `ccbd`
- 尊重关闭意图，使 `ccb kill` 保持权威

### D 阶段：统一报告

- 启动报告
- 监督事件日志
- 关闭报告
- 读取路径消费报告，而非临时推断部分真相

## 11. 验收矩阵

设计在以下场景自动化且通过前不算完成。

锚点和配置：

- `.ccb` 缺失
- `.ccb` 为空
- `.ccb` 存在持久化状态但配置缺失
- 配置格式错误
- 后端存活时配置变更

后端所有权：

- 健康挂载的守护进程
- 带死亡 pid 的陈旧租约
- 带死亡 socket 的挂载租约
- 带配置不匹配的健康租约
- keeper 活跃时后端崩溃
- 显式 `ccb kill` 不触发 keeper 重启

运行时监督：

- 启动时陈旧绑定
- agent 空闲时窗格死亡
- agent 有排队工作时窗格死亡
- `ensure_pane()` 成功
- `ensure_pane()` 失败且重新启动成功
- 重复重新启动失败进入退避/恢复状态

关闭：

- 正常 `ccb kill`
- 强制 `ccb kill -f`
- 存在未知陈旧 agent 目录
- 存在格式错误的运行时残留
- 移除项目拥有的窗格
- 后端租约以卸载状态结束

## 12. 变更纪律

如果未来工作变更以下任何内容，必须在同一次补丁中更新本文档：

- 谁拥有后端权威
- 什么定义期望 agent
- 守护进程或 job 路径是否拥有运行时恢复
- keeper 是否存在以及它被允许做什么
- `ccb kill` 保证什么
- `.ccb/ccbd/` 下哪些是权威的

如果实现和本文档不一致，必须将不一致视为架构问题，而非挥手当作实现细节。
