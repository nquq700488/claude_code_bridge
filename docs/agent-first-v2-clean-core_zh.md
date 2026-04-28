# Agent-First V2 纯净核心

## 目的

本文档是 `ccb_source` v2 的精简基线。

它取代任何早期假设长期兼容层、混合旧路径或双运行时轨道的旧设计说明。

目标不是保留旧的内部结构，而是产生一个更小、更稳定的 agent-first 核心，能够干净地成长。

当前具体目录布局见 `docs/current-project-structure.md`。

## 架构基线

最新可用的 `archi --skip-auth` 产物仍指向非常弱的整仓基线：

- 完整分数快照：`25.2`
- 等级：`E`
- 发布建议：`block`

即使精确分数落后于实时工作树，缓存的热点排序仍然有用：

1. `lib/opencode_comm.py`
2. `lib/claude_comm.py`
3. `lib/terminal.py`
4. `lib/codex_comm.py`
5. `lib/laskd_registry.py`
6. `ccb`

解读：

- 通过打磨标志或添加兼容分支，项目无法达到 `90`
- 唯一可信的上升路径是切割大文件、移除混合职责，并收窄高分支 provider/runtime 边界
- `ccb` 本身曾是顶级债务来源，现在正通过将启动职责提取到专用模块来进行原地缩减

## 硬边界

v2 核心遵循以下规则：

- Agent 名称是主要运行时身份。
- Provider 只是 agent 的属性。
- 每个项目有一个 `askd`。
- 项目状态仅存在于 `.ccb/` 下。
- Session 查找仅向上读取 `.ccb/<session-file>`。
- `ccb` v2 行为必须收敛到单一路径：`cli -> askd -> provider_execution -> completion -> storage`。
- `codex`、`claude` 和 `gemini` 是第一阶段核心 provider。
- 旧版 provider 可以存在，但不得影响核心抽象。
- 顶层 `ccb` 入口点必须先尝试 phase2，再进入任何旧版回退路径。

v2 核心明确拒绝以下旧模式：

- `.ccb_config/`
- `.ccb/` 之外的根目录级 provider session 文件（如 `.codex-session`）
- agent 模型中的全局 `compatibility_mode` 策略
- 回退标志泄漏到共享完成模型中
- tmux session-name / pane-id 混合目标语义作为核心运行时契约
- 多个 provider 特定守护进程作为主要架构
- phase1/phase2 长期共存作为目标状态

针对 tmux 的具体规则：

- 旧模块仍可能调用接受 session-name 回退的通用终端方法
- v2 运行时路径必须调用 pane-only 辅助函数，并将 `%<pane>` 视为唯一有效的 tmux 运行时目标

## 核心模型决策

### Agent 规范

`AgentSpec` 缩减为仅影响实际 v2 行为的字段：

- `name`
- `provider`
- `target`
- `workspace_mode`
- `workspace_root`
- `runtime_mode`
- `restore_default`
- `permission_default`
- `queue_policy`
- `startup_args`
- `env`
- `branch_template`
- `labels`
- `description`
- `watch_paths`

从核心中移除：

- `compatibility_mode`

原因：

- 完成回退不是 agent 范围的全局策略开关
- 它将不相关的 provider 耦合在一起
- 它将退化的传输行为变成全局配置面

### 完成模型

结构化 provider 与旧版 provider 通过检测器族分离，而不是通过共享的兼容性开关。

当前干净分割：

- `codex` -> `protocol_turn`
- `claude` -> `session_boundary`
- `gemini` -> `anchored_session_stability`
- 旧版文本 provider -> `legacy_text_quiet`

从共享完成配置文件/请求上下文中移除：

- `compatibility_mode`
- `supports_legacy_quiet_fallback`

原因：

- 结构化 provider 不应携带它们不使用的回退元数据
- 旧版超时行为应保留在旧版检测器实现内部
- 共享完成 API 应描述信号形状，而非迁移策略

## 路径规则

唯一有效的项目配置目录是：

```text
<project>/.ccb/
```

唯一有效的向上 session 查找是：

```text
<ancestor>/.ccb/<session_filename>
```

拒绝的查找路径：

```text
<ancestor>/.ccb_config/<session_filename>
<ancestor>/<session_filename>
```

小别名可能仅保留在辅助代码中，以保持未触及模块的导入安全，但运行时路径仍为 `.ccb/` 唯一。

## 默认配置策略

第一阶段默认生成的 agent 现在是：

- `codex`
- `claude`
- `gemini`

从默认生成配置中移除：

- `opencode`
- `droid`

原因：

- 默认值应代表稳定核心，而非每个历史适配器
- 非核心 provider 可在需要时由用户显式添加

## askd 稳定性规则

`askd` 必须在长时间运行回合和关闭竞争中保持稳定。

当前规则：

- heartbeat 不得复活已卸载的租约
- `serve_forever()` 必须在 `finally` 中标记租约已卸载
- 仅移除 socket 不被视为足够的关闭状态
- 租约状态是挂载/卸载转换的真相来源

操作说明：

- 运行集成或黑盒测试时，如果启动真正的 pane-backed provider，请保持测试串行
- 如果多个 pytest 进程在同一主机 session 环境中并行启动，tmux-backed provider 测试可能相互干扰

## 入口点规则

顶层 `ccb` 脚本正在缩减为 phase2 优先调度器。

当前纯净核心行为：

- `ccb` 先尝试 `maybe_handle_phase2()`
- `ccb config validate` 由 phase2 处理，而非 phase1 仅预分派路径
- 旧分支仍可能存在于非 v2 命令，但它们不再是 v2 项目的一级路由决策
- 非 phase2 CLI 处理被隔离在 `lib/cli/router.py` 下，因此顶层脚本仅连接处理程序
- phase2 输出渲染正在移入 `lib/cli/render.py`，以便 `phase2.py` 保持为控制层，而非重度打印的混合模块

当前目标文件角色：

- `ccb`：仅顶层路由选择和旧处理程序连接
- `lib/cli/phase2.py`：phase2 命令解析、上下文构建、服务分派
- `lib/cli/render.py`：phase2 命令的文本输出格式化
- `lib/cli/router.py`：非 phase2 辅助/管理/启动参数路由
- `lib/cli/start.py`：项目锚点检查、provider 解析、默认启动选择
- `lib/cli/management.py`：管理命令实现（`version/update/uninstall/reinstall`）
- `lib/cli/kill.py`：kill 命令实现（session 清理、守护进程关闭、僵尸清理）
- `lib/cli/auxiliary.py`：辅助命令实现（`droid`、`mail`）
- `lib/launcher/daemon_manager.py`：启动器范围的 provider 守护进程启动、askd 所有权检查、看门狗生命周期
- `lib/launcher/session_store.py`：启动器范围的项目 session 持久化、Claude 本地 session 回填、session 停用辅助函数

## 终端规则

`terminal.py` 仍包含旧的通用方法，因为旧代码共存于仓库中。

纯净的 v2 规则更窄：

- `provider_execution/*` 必须使用运行时目标辅助函数，而非直接调用 `backend.send_text()` / `backend.is_alive()`
- `TmuxBackend.send_text_to_pane()` 是 tmux-backed agent 的 v2 提交路径
- `TmuxBackend.is_tmux_pane_alive()` 是 tmux-backed agent 的 v2 存活路径
- `TmuxBackend.kill_tmux_pane()` 和 `TmuxBackend.activate_tmux_pane()` 是 v2 pane 管理原语
- session-name 回退仅保留在通用旧方法中

## 第一阶段测试契约

纯净核心变更的最小回归集：

```bash
python -m pytest -q \
  test/test_v2_config_loader.py \
  test/test_v2_completion_models.py \
  test/test_v2_completion_detectors.py \
  test/test_v2_completion_registry.py \
  test/test_v2_policy.py \
  test/test_v2_agent_store.py \
  test/test_v2_runtime_launch.py \
  test/test_v2_workspace_manager.py \
  test/test_session_utils.py
```

askd 生命周期和黑盒检查：

```bash
python -m pytest -q test/test_v2_askd_mount_ownership.py
python -m pytest -q test/test_v2_askd_dispatcher.py test/test_v2_phase1_entrypoint.py
python -m pytest -q test/test_v2_phase2_entrypoint.py -k "ccb_v2_project_lifecycle or fake_legacy_provider_degraded_done_marker_completion or two_named_codex_agents_concurrent_ask_isolated"
python -m pytest -q test/test_tmux_backend.py test/test_v2_runtime_isolation.py test/test_v2_execution_service.py -k "strict or runtime_isolation or codex_adapter_prefers_strict_tmux_target_helpers"
python -m pytest -q test/test_v2_cli_render.py test/test_v2_cli_router.py
python -m pytest -q test/test_v2_cli_management.py test/test_v2_cli_kill.py test/test_v2_cli_auxiliary.py test/test_v2_cli_start.py
```

## 后续清理

下一次结构性删除应按此顺序进行：

1. 删除任何剩余对已删除旧版 `lib/launcher` 树的历史引用，以便活动文档仅描述当前的 `cli -> ccbd/provider_backends` 运行时。
2. 将 `lib/terminal.py` 拆分为后端特定的运行时模块，使 pane 生命周期、输入注入和布局控制不再耦合在一个文件中。
3. 继续将通信逻辑折叠到 `lib/provider_backends/*` 中，使后端特定的日志扫描、session 解析和完成辅助函数不再存在于巨大的顶层文件中。
4. 从共存辅助模块中移除剩余的 `.ccb_config` 和根 session 回退假设。
5. 进一步将 `askd/adapters/*` 从主运行时路径中折叠出来，使 `provider_execution/*` 成为 agent-first 流的唯一执行路径。
6. 继续缩减顶层 `ccb` 文件，使其保持为围绕 `cli.entrypoint` 的薄 CLI 入口包装器。
7. 将非核心 provider 推到显式 opt-in 注册之后，而非默认目录压力。

## 验收标准

当满足以下条件时，纯净核心基线被视为健康：

- v2 配置不再接受 `compatibility_mode`
- 生成的配置仅包含第一阶段核心 provider
- session 查找仅解析 `.ccb/` 文件
- codex/claude/gemini 完成路径不依赖文本标记或安静回退
- v2 provider 执行不直接调用 tmux 通用 `send_text` / `is_alive` API
- 旧版超时行为仅隔离在旧版检测器代码中
- askd 关闭即使在并发 tick 下也将租约留在 `unmounted` 状态
