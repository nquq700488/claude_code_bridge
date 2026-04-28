# Agent 消息管理路线图

详细设计：

- 见 [`docs/agent-mailbox-kernel-design.md`](/home/bfly/yunwei/ccb_source/docs/agent-mailbox-kernel-design.md)

## 当前位置

- 基线分数：overall=50.33, structure=64.16, governance/full=36.49
- diff 读取：overall=66.88, incremental=100.0, governance/full=36.49
- 当前读取：增量变更在架构上是安全的，但整仓瓶颈仍然是治理和 `lib:askd` 中的复杂度集中，这正是信息管理层必须锚定的地方

## 现有构建块

- `JobDispatcher` 已拥有持久的 submit/tick/complete/cancel 转换
- `JobStore`、`JobEventStore`、`SubmissionStore` 和快照写入已提供持久状态和重播锚点
- `CompletionTrackerService` 已分离执行与完成检测
- `AgentRegistry` 和运行时同步已暴露足够信息来构建活跃度和队列视图
- `watch/get/cancel` 已覆盖薄控制面，但它们止于单 job 观察

## 硬边界

Provider/backend 层和信息管理层不得共享策略职责。

### Provider/backend 层拥有

- 如何启动特定 provider
- 如何读取 provider 原生进展
- 如何解码完成证据
- 如何观察 runtime/session/pane 健康
- 看到了什么 provider 原生失败原因或降级信号

### 信息管理层拥有

- 队列策略
- 等待语义
- 重试/重新提交策略
- 回复聚合
- 谱系和相关性
- 操作者可见的状态模型
- 死信和恢复工作流

这意味着 provider 代码报告事实；管理局决定策略。

## Provider 状态隔离

不同的 provider 绝对应该有不同的状态判断逻辑。隔离点应在 askd 编排之下，而非混入重试或队列逻辑中。

### 提议的底层分割

```text
provider_execution
  -> transport/runtime adapter
  -> provider progress adapter
  -> completion detector
  -> provider health snapshot
```

### 推荐契约

在 `ProviderSubmission` 和 `ProviderPollResult` 旁边添加显式的面向 provider 的状态契约。

```text
ProviderHealthSnapshot
  - job_id
  - provider
  - agent_name
  - runtime_alive
  - session_reachable
  - progress_state
  - completion_state
  - last_progress_at
  - observed_at
  - degraded_reason
  - diagnostics
```

```text
progress_state
  - not_started
  - submitted
  - accepted
  - actively_running
  - quiet_wait
  - output_advancing
  - stalled
  - runtime_lost
  - session_lost
  - unknown
```

```text
completion_state
  - not_complete
  - terminal_complete
  - terminal_incomplete
  - terminal_failed
  - terminal_cancelled
  - indeterminate
```

### 为什么这很重要

- Claude、Codex、Gemini、OpenCode 和 Droid 各有不同的证据模型
- 完成检测器已经不同；健康检测器也应允许不同
- 管理局永远不需要知道 provider 使用协议轮次、session 边界、空闲窗口还是安静文本标记
- 管理局只需要规范化的健康/状态快照和终端证据

### 具体 provider 职责

- `provider_execution` adapter：
  - 启动
  - 恢复
  - provider 原生轮询
  - 发出原始进展项
  - 发出 `ProviderHealthSnapshot`
- `completion` 层：
  - 将原始进展转换为 `CompletionItem`
  - 维护 `CompletionDecision`
- `askd/runtime` 层：
  - 提供 `ProviderRuntimeContext`
  - 更新 agent runtime 注册表和队列深度

## 管理局状态模型

信息管理局应定义自己的面向操作者的状态模型，而非直接复用 provider 状态。

```text
MessageState
  - queued
  - dispatching
  - running
  - waiting_replies
  - partially_replied
  - completed
  - incomplete
  - failed
  - cancelled
  - dead_letter
```

```text
AttemptState
  - pending
  - running
  - stalled
  - runtime_dead
  - abandoned
  - superseded
  - completed
  - incomplete
  - failed
  - cancelled
```

映射规则应为单向：

- provider 报告 `ProviderHealthSnapshot`
- 管理局将快照 + job 状态 + 策略映射为 `AttemptState`
- 用户工具只消费 `AttemptState` / `MessageState`

这使 provider 特定的复杂度远离队列和重试逻辑。

## 当前差距

- job 之上没有一流的 mailbox/channel 抽象，因此 request/reply 相关性仍是隐式的
- 队列语义是 per-agent 的，且局限于分派器，但作为受管理的通信契约不可见
- 阻塞等待作为客户端行为存在（`ask --wait`、`watch_job`），而非可复用的协调原语
- Runtime 健康可见，但 dead/alive/stalled 区分未被提升为统一任务策略层
- 重试和重新提交仍是操作者动作，而非带有谱系的策略支持生命周期特性
- 缺少扇出/扇入协调：广播存在，但没有 wait-all、quorum、barrier 或回复聚合

## 消息管理局服务

管理局应拆分为小服务，而非单个巨型协调器。

### 1. MailboxService

职责：

- 创建 `message_id`
- 拥有目标组和相关性标签
- 决定预期回复基数
- 将提交/广播链接到一个逻辑消息

### 2. AttemptSupervisor

职责：

- 从消息创建 attempts
- 映射 `message -> attempt -> job`
- 应用重试/重新提交策略
- 将 attempt 标记为被取代、废弃或死信

### 3. LivenessService

职责：

- 结合 `AgentRegistry` 运行时健康与 `ProviderHealthSnapshot`
- 确定 `running` vs `stalled` vs `runtime_dead`
- 检测 askd 重启或 runtime 丢失后的孤儿 job

### 4. ReplyAggregator

职责：

- 跨 attempts 收集回复
- 支持 single、any、all 和 quorum 风格等待
- 在扇出期间暴露部分进展
- 决定逻辑消息何时完成

### 5. OperatorControl

职责：

- 暴露 `wait`、`queue`、`retry`、`resubmit`、`barrier`
- 渲染状态摘要
- 展示死信项和恢复动作

## 分派和接收流

### 发送路径

```text
public request
  -> MailboxService.create_message(...)
  -> AttemptSupervisor.start_attempt(...)
  -> JobDispatcher.submit(...)
  -> ExecutionService.start(...)
```

### 接收路径

```text
provider poll
  -> ProviderHealthSnapshot + CompletionItem/Decision
  -> LivenessService.update_attempt_state(...)
  -> ReplyAggregator.ingest(...)
  -> MessageState recomputed
  -> completion notification / waiter wakeup / operator view update
```

### 重试路径

```text
attempt terminal or unhealthy
  -> AttemptSupervisor.evaluate_policy(...)
  -> new attempt or dead-letter
  -> lineage updated
  -> prior attempt frozen, never overwritten
```

## 等待语义

阻塞和异步应作为同一状态图的视图实现，而非作为单独的执行模式。

### 必需的等待原语

- `wait_job(job_id)`
- `wait_message(message_id)`
- `wait_any(submission_id)`
- `wait_all(submission_id)`
- `wait_quorum(submission_id, min_replies=N)`

### 规则

- provider 层从不阻塞
- 管理局协调等待者
- CLI/MCP/mail 只选择是否阻塞调用者或立即返回

这使阻塞语义远离后端。

## 重试和重新提交设计

重试和重新提交不是一回事，应分别建模。

### 重试

- 同一逻辑消息
- 同一目标 agent，除非策略另有规定
- 新的 attempt
- 保留原始相关性和 mailbox 身份

### 重新提交

- 从前一条消息派生的新逻辑消息
- 可更改目标、负载或策略
- 通过 `origin_message_id` 链接回来

### 推荐策略输入

- runtime 在首次回复前死亡
- 超过策略超时停滞
- 终端不完整
- 显式操作者动作
- askd 重启恢复结果

## 推荐的新记录

为管理局添加持久记录，而非重载 `JobRecord`。

```text
MessageRecord
  - message_id
  - origin_message_id
  - from_actor
  - target_scope
  - target_agents
  - reply_policy
  - retry_policy
  - created_at
  - updated_at
```

```text
AttemptRecord
  - attempt_id
  - message_id
  - job_id
  - agent_name
  - attempt_state
  - retry_index
  - health_snapshot
  - started_at
  - updated_at
```

```text
ReplyRecord
  - reply_id
  - message_id
  - attempt_id
  - agent_name
  - terminal_status
  - reply
  - diagnostics
  - finished_at
```

## 建议的目录结构

```text
lib/askd/services/message_bureau/
  models.py
  store.py
  mailbox.py
  attempts.py
  liveness.py
  aggregation.py
  waits.py
  control.py
```

## 立即

- 保持公开接口严格仅限 agent：无新的面向 provider 的提交面、别名或 MCP 工具
- 围绕 `job`、`message`、`attempt` 和 `reply` 作为独立概念，引入消息管理文档和待办事项
- 添加持久的 `attempt_lineage` 模型，以便记录重试/重新提交而非覆盖 job 历史
- 添加从运行时健康加完成静默导出的显式 `stalled` 和 `orphaned` 生命周期读取
- 在管理局下方添加规范化的 `ProviderHealthSnapshot` 契约
- 在一个管理视图中暴露队列深度、活跃 job、最后 heartbeat 和最后终端决策

## 下一步

- 在 `JobDispatcher` 之上添加 `MailboxService`
- 显式化 mailbox 概念：
  - `message_id`：稳定的逻辑请求 id
  - `attempt_id`：一次具体执行尝试
  - `reply_id`：一个终端响应产物
  - `channel`：目标 agent 或广播组
- 添加等待原语：
  - `wait_one(message_id)`
  - `wait_all(submission_id)`
  - `wait_any(submission_id)`
  - `barrier(group_id)`
- 添加重试策略对象：
  - `manual`
  - `on_dead_runtime`
  - `on_incomplete`
  - `bounded_backoff`
- 存储重试/重新提交谱系，使用户可以看到"原始请求 -> attempt 2 -> attempt 3 -> 最终回复"
- 添加将 provider 健康事实映射为管理局 attempt 状态的 `LivenessService`

## 稍后

- 为广播和多 agent 工作流添加回复聚合
- 为永久失败或废弃的工作添加死信存储
- 添加类似 MPI 标签或通信器的 channel 级流控制：
  - 目标组
  - 消息类
  - 相关性标签
  - 回复期望
- 添加超出 serial-per-agent 的调度器策略：
  - 加权公平
  - 截止期限优先
  - 交互 vs 批处理通道
- 添加恢复的操作者工具：
  - `ccb retry <job_id>`
  - `ccb resubmit <job_id>`
  - `ccb wait <job_id|submission_id>`
  - `ccb queue <agent|all>`
  - `ccb barrier <group>`

## 提议的模型

### 分层

```text
CLI / MCP / Mail
  -> Message Management Layer
  -> JobDispatcher
  -> ProviderExecution
  -> CompletionTracker
  -> Storage / Runtime Registry
```

### 核心记录

```text
MessageRecord
  - message_id
  - from_actor
  - target_scope
  - target_agents
  - body
  - policy
  - created_at

AttemptRecord
  - attempt_id
  - message_id
  - job_id
  - agent_name
  - status
  - runtime_health
  - retry_index
  - started_at
  - updated_at

ReplyRecord
  - reply_id
  - message_id
  - attempt_id
  - agent_name
  - terminal_status
  - reply_excerpt
  - finished_at
```

## 建议的排序

1. 第一阶段：可观测性优先
   - 添加 `ProviderHealthSnapshot`、队列/活跃度/attempt 谱系记录和读取 API
2. 第二阶段：策略层
   - 添加重试/重新提交/停滞检测，而不更改执行适配器
3. 第三阶段：协调原语
   - 添加 wait-all/any、barrier 和回复聚合
4. 第四阶段：公开工具
   - 添加 `ccb wait/queue/retry/resubmit` 并更新 MCP/mail 面以使用消息 id

## 为什么适合当前仓库

- 它复用持久的 job/event/snapshot 系统而非替换它
- 它将 provider 实现保留在执行适配器之后
- 它让面向 agent 的接口在更丰富的编排于分派器之上增长时保持稳定
- 它匹配仓库现有的执行、完成、运行时状态和 CLI 视图之间的分割
