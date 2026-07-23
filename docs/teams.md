# CCB Team 使用文档

> **适用版本：** v8.3.0+

Team 是 CCB 的多 Agent 编组功能。在项目中用 `[teams.<name>]` TOML 段定义成员后，`ccb team start` 会为每个成员创建动态 Agent 并注入协作协议，`ccb team ui` 启动本地 Web 群聊页面进行实时对话。

---

## 目录

- [快速开始](#快速开始)
- [配置格式](#配置格式)
- [四种拓扑](#四种拓扑)
  - [mesh — 自由协作](#mesh--自由协作)
  - [hub-spoke — 中心分发](#hub-spoke--中心分发)
  - [review-loop — 审查循环](#review-loop--审查循环)
  - [debate — 独立辩论](#debate--独立辩论)
- [Policy 配置](#policy-配置)
- [CLI 命令](#cli-命令)
- [Team UI 群聊页面](#team-ui-群聊页面)
- [生命周期](#生命周期)
- [运行时文件结构](#运行时文件结构)
- [完整示例](#完整示例)

---

## 快速开始

**1. 配置 team**

在项目 `.ccb/ccb.config` 中添加 `[teams]` 段（推荐写在 `ccb.config`，compact 和 multi 模式共用）：

```toml
[teams.demo]
topology = "mesh"
description = "示例团队"

[[teams.demo.members]]
name = "alice"
provider = "claude"
description = "架构设计"

[[teams.demo.members]]
name = "bob"
provider = "codex"
description = "代码实现"
```

**2. 启动 team**

```bash
ccb team start demo
```

**3. 打开群聊 UI**

```bash
ccb team ui demo
```

浏览器自动打开 `http://127.0.0.1:8888/`，可以在群聊界面中 @成员发送消息。

---

## 配置格式

Team 配置推荐写在 `.ccb/ccb.config` 中（`teams` 和 `providers` 是共享配置，compact 和 multi 模式自动继承）。也可以写在模式专属配置（如 `.ccb/ccb-compact.config` 的 TOML overlay）中，后者中的同名字段优先级更高。完整格式：

```toml
[teams.<name>]
topology = "<topology>"          # 必填：hub-spoke | review-loop | mesh | debate
description = "..."              # 可选：团队描述

[[teams.<name>.members]]         # 必填，至少 2 个
name = "<agent-name>"            # 必填：1-32 字符，字母数字 + _-
provider = "<provider>"          # 必填：已注册的 provider 名
description = "..."              # 可选：成员职责描述
model = "<model>"                # 可选：覆盖 agent 默认模型
role = "<role-pack>"             # 可选：绑定 role pack

[teams.<name>.policy]            # 可选，控制拓扑行为
leader = "<name>"                # hub-spoke / review-loop 的 leader
synthesizer = "<name>"           # debate 的汇总者
rounds_max = 3                   # review-loop 最大轮次
pass_score = 7.0                 # review-loop 通过线 (0-10)
```

### 校验规则

| 规则 | 说明 |
|------|------|
| `members` 最少 2 个 | Team 至少需要 2 名成员 |
| `name` 唯一且不与已有 agent 冲突 | 成员名不能与 config 中已有 agent 同名 |
| `provider` 必须已注册 | 内置 provider 或已 reload 生效的自定义 provider |
| `topology` 仅限四种 | hub-spoke / review-loop / mesh / debate |
| `policy.leader` / `synthesizer` | 必须是 members 中存在的 name |
| `pass_score` 范围 | 0 < pass_score ≤ 10 |
| `rounds_max` 范围 | ≥ 1 |

---

## 四种拓扑

拓扑决定了 team start 时注入每个成员的协作协议文本。

### mesh — 自由协作

无固定流程，成员自由通信。适合开放式讨论、探索性任务。

```toml
[teams.brainstorm]
topology = "mesh"
```

**协议内容（所有成员相同）：**

- 任何人可以向任何人发起 `/ask`
- 用户可以直接向任意成员发消息
- 做完任务后向用户汇报结果

**适用场景：** 自由讨论、知识共享、非结构化协作。

### hub-spoke — 中心分发

用户只与 leader 交互，leader 拆解任务并分派给成员。

```toml
[teams.crew]
topology = "hub-spoke"

[teams.crew.policy]
leader = "coordinator"
```

**协议差异：**

| 角色 | 流程 |
|------|------|
| **Leader** | 接收用户任务 → 拆解 → `/ask` 分派成员 → `/pend` 收集回复 → 汇总报告用户 |
| **Member** | 等待 leader 分派 → 完成并回复 → 不直接向用户报告（除非被要求） |

**适用场景：** 任务分发、项目协调、一对多管理模式。

### review-loop — 审查循环

leader 发起 → coder 实现 → reviewer 打分 → 低于 pass_score 则退回修改 → 循环直至通过或达到最大轮次。

```toml
[teams.review-squad]
topology = "review-loop"

[teams.review-squad.policy]
leader = "squad-leader"
rounds_max = 3
pass_score = 7.0
```

**协议差异：**

| 角色 | 流程 |
|------|------|
| **Leader** | 收任务 → 打包需求 → 发给 coder → 等 reviewer 分数 → PASS 则报告用户，否则让 coder REVISE |
| **Reviewer**（名中含 "reviewer"） | 等 coder 提交 → 按 rubric 打分（返回 JSON）→ < pass_score 发 REVISE，≥ pass_score 发 PASS |
| **Coder**（其他成员） | 等 leader 任务包 → 实现 → 提交 diff 给 reviewer → 收到 REVISE 则修改重提 → PASS 后报告 leader |

> **注意：** reviewer 角色按成员名中是否包含 "reviewer" 自动识别；若成员名不含该字样则走 coder 流程。

**适用场景：** 代码审查、质量门控、需要评分反馈的迭代任务。

### debate — 独立辩论

synthesizer 向全员广播同一问题，成员独立作答，汇总对比后报告用户。

```toml
[teams.debate-club]
topology = "debate"

[teams.debate-club.policy]
synthesizer = "moderator"
```

**协议差异：**

| 角色 | 流程 |
|------|------|
| **Synthesizer** | 收用户问题 → 广播给全员 → 收集所有独立回复 → 对比分析（异同点 + 推荐）→ 汇总报告用户 |
| **Panelist**（其他成员） | 收到问题 → 独立作答（不看队友答案）→ 提供推理过程 → 回复 synthesizer |

**适用场景：** 多视角分析、方案评估、决策辅助。

---

## Policy 配置

`[teams.<name>.policy]` 段控制拓扑特定的行为参数：

| 字段 | 类型 | 默认值 | 适用拓扑 | 说明 |
|------|------|--------|----------|------|
| `leader` | string | — | hub-spoke, review-loop | leader 成员名，必须存在于 members 中 |
| `synthesizer` | string | — | debate | 汇总者成员名，必须存在于 members 中 |
| `rounds_max` | int | 3 | review-loop | 最大审查轮次 |
| `pass_score` | float | 7.0 | review-loop | 审查通过线（0-10） |

---

## CLI 命令

```bash
# 列出所有 team 定义及实例状态
ccb team list [--json]

# 启动 team（创建动态 agent + 注入协议）
ccb team start <name> [--window NAME] [--parked] [--json]

# 停止 team（默认 park，--unload 彻底释放）
ccb team stop <name> [--unload] [--json]

# 查看 team 状态（成员状态、定义是否有变更）
ccb team status <name> [--json]

# 启动群聊 UI（浏览器打开 http://127.0.0.1:8888/）
ccb team ui <name> [--port PORT]
```

### 命令详解

#### `team start`

为每个成员创建动态 Agent（写入 lifecycle.json），将拓扑协议注入 agent private memory（`memory.md`），写入 team 实例状态。

- **幂等：** 重复 `start` 已运行的 team 返回 `already_running`，不做任何变更
- **Park 恢复：** 对已 park 的 team 执行 `start` 会重新激活所有成员
- **部分失败：** 若部分成员创建失败，状态标记为 `partial`，再次 `start` 只重试缺失成员

#### `team stop`

- **默认（park）：** 保留生命周期文件，`dispatch_disabled=true`，agent 不可用但数据保留。下次 `start` 可恢复
- **`--unload`：** 标记 agent 为 unloaded，移除 team 实例状态

#### `team status`

检查实例状态和定义一致性：

- 各成员 lifecycle state 和 agent status
- `definition_changed`：若 TOML 定义与上次 `start` 时的 `definition_hash` 不一致则为 true

#### `team ui`

启动本地 Web 群聊页面：

| 属性 | 值 |
|------|-----|
| 绑定地址 | `127.0.0.1`（仅本机可访问） |
| 默认端口 | `8888` |
| URL | `http://127.0.0.1:8888/` |
| 数据来源 | 当前项目 `.ccb/` 运行时数据 |
| 空闲超时 | 30 分钟无请求自动退出 |
| 鉴权 | 无需 token，127.0.0.1 即信任边界 |

---

## Team UI 群聊页面

### 布局

```
┌──────────────────────────────────────────────┐
│  demo · mesh · ● running         [Start][Stop]│
├─────────────┬────────────────────────────────┤
│  成员 (4)    │  时间线                         │
│  ● planner  │  ┌────────────────────────────┐ │
│  ● developer│  │ @planner 帮我看看这个模块    │ │
│  ● reviewer │  └────────────────────────────┘ │
│  ● tester   │          planner · codex  14:09  │
│             │  ┌────────────────────────────┐ │
│             │  │ 这个模块负责...              │ │
│             │  └────────────────────────────┘ │
├─────────────┴────────────────────────────────┤
│ [@planner ▾]  输入消息…                [发送] │
└──────────────────────────────────────────────┘
```

### 功能

| 功能 | 说明 |
|------|------|
| **@成员发送** | 下拉框选择目标成员，输入消息点发送 |
| **@all 广播** | 消息发给所有成员 |
| **实时时间线** | 每 2 秒轮询增量事件，自动去重 |
| **Ask/Reply 双向可见** | 提问和回复都在时间线中展示，不会被过滤 |
| **思考指示器** | Agent 处理中显示 provider 颜色闪烁动画，按钮置灰 |
| **Markdown 渲染** | 服务端渲染 Markdown 为 HTML（代码块、JSON、列表等） |
| **自动滚动** | 新消息到达自动滚到底部（距底部 40px 内时） |
| **气泡着色** | 左侧 3px 色条按 provider 着色：Claude 橙、Codex 靛、Gemini 绿、Kimi 红 |
| **时间戳** | 精确到秒的 HH:MM:SS 格式 |

### 数据来源

所有时间线数据从项目 `.ccb/` 目录实时读取：

- `jobs.jsonl` — Job 记录快照（提问内容、from_actor、job_id）
- `events.jsonl` — 事件流（completion_terminal 事件的 agent 回复）
- `lifecycle.json` — Agent 运行状态

不产生任何假数据或独立数据库。重启 Server 后数据不丢失（数据在磁盘上）。

---

## 生命周期

```
                 team start
    ┌──────────── 启动 ────────────┐
    │                              │
    ▼                              │
 [running] ── team stop ──▶ [parked] ── team start ──▶ [running]
    │                         │
    │    team stop             │
    │    --unload              │
    ▼                          
 [unloaded]                   [parked]（保留状态）
  - agent marked unloaded       - dispatch_disabled
  - instance state removed      - 数据保留
```

### Park vs Unload

| | Park | Unload |
|---|------|--------|
| Agent 状态 | lifecycle_state='parked', dispatch_disabled | agent_lifecycle_status='unloaded' |
| Team 实例 | 保留 state.json（status='parked'） | 移除 state.json |
| 数据文件 | 保留 | 保留 |
| 恢复方式 | `ccb team start <name>` | 重新 `team start` |
| 用途 | 暂时停用，稍后恢复 | 彻底拆除 |

### 部分失败与重试

如果 `team start` 时部分成员创建失败：

1. Team 实例状态标记为 `status: "partial"`
2. 成功创建的成员正常运行
3. 再次执行 `team start` 只创建缺失的成员（去重已有成员）
4. 全部创建成功后状态自动切换为 `running`

---

## 运行时文件结构

`ccb team start` 后产生的文件：

```
.ccb/
├── agents/<name>/memory.md          # 拓扑协议注入（追加到已有内容后）
├── runtime/
│   ├── agents/<name>/
│   │   └── lifecycle.json           # Agent 生命周期状态
│   └── teams/<name>/
│       └── state.json               # Team 实例状态
```

**state.json 格式：**

```json
{
  "team_name": "demo",
  "topology": "mesh",
  "upped_at": "2026-07-23T08:00:00Z",
  "definition_hash": "a1b2c3d4e5f6g7h8",
  "status": "running",
  "members": [
    {"name": "planner", "provider": "codex"},
    {"name": "developer", "provider": "claude"}
  ]
}
```

---

## 完整示例

### 场景：代码审查团队

```toml
[teams.code-review]
topology = "review-loop"
description = "三阶段代码审查团队"

[[teams.code-review.members]]
name = "lead"
provider = "claude"
description = "任务接收与分派，结果汇总"
model = "sonnet"

[[teams.code-review.members]]
name = "coder"
provider = "codex"
description = "代码实现"
model = "gpt-5"

[[teams.code-review.members]]
name = "reviewer"
provider = "claude"
description = "按 rubric 评分审查"

[teams.code-review.policy]
leader = "lead"
rounds_max = 5
pass_score = 8.0
```

### 场景：方案讨论团队

```toml
[teams.think-tank]
topology = "debate"
description = "多视角方案评估"

[[teams.think-tank.members]]
name = "analyst"
provider = "claude"
description = "广度分析：市场规模、竞品、政策"

[[teams.think-tank.members]]
name = "engineer"
provider = "codex"
description = "技术可行性、架构复杂度"

[[teams.think-tank.members]]
name = "moderator"
provider = "claude"
description = "汇总各方观点，给出推荐方案"

[teams.think-tank.policy]
synthesizer = "moderator"
```

### 操作流程

```bash
# 1. 启动审查团队
ccb team start code-review

# 2. 查看状态
ccb team status code-review

# 3. 打开群聊 UI 进行对话
ccb team ui code-review

# 4. 用完暂停（保留数据）
ccb team stop code-review

# 5. 重新激活
ccb team start code-review

# 6. 彻底拆除
ccb team stop code-review --unload
```

---

## 参考

- [CCB 安装指南](../CCB_INSTALL_GUIDE.md)
- [Provider 配置文档](../CCB_INSTALL_GUIDE.md#自定义-provider)
- [CHANGELOG](../CHANGELOG.md)
