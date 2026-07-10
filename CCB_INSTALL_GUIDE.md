# CCB 跨设备安装指南 (Cross-Device Installation Guide)

> 版本：适用于 CCB v8.0.16 | 最后更新：2026-07-06

---

## 目录

1. [CCB 简介](#ccb-简介)
2. [环境要求](#环境要求)
3. [方式一：Git Clone 全新安装](#方式一git-clone-全新安装)
4. [方式二：Release 包安装](#方式二release-包安装)
5. [安装后验证](#安装后验证)
6. [项目配置（在新设备上创建 Agent 团队）](#项目配置在新设备上创建-agent-团队)
7. [更新与升级](#更新与升级)
8. [卸载](#卸载)
9. [常见问题排查](#常见问题排查)
10. [配置文件速查](#配置文件速查)
11. [开发工具与实用工具](#开发工具与实用工具)
12. [架构说明](#架构说明)

---

## CCB 简介

> **名称演变**：CCB 最初代表 **Claude Code Bridge**。随着项目扩展到支持多模型协作（15 个 CLI 家族：Codex、Claude、Gemini、Kimi、MiMo、Qwen、Cursor、Copilot、Crush、Kiro、Pi、Z.ai、OpenCode、Antigravity、Droid，Fork 额外支持 MMX），这个缩写现在代表 **Collaborative Code Bridge** —— 协作代码桥。

**CCB (Collaborative Code Bridge)** 是一个多 AI Agent CLI 协作平台。它基于 **tmux** 终端多路复用器，让你在一个终端窗口中同时运行和管理多个 AI Agent，并让它们通过 `/ask`、`/ping`、`/pend` 命令互相通信和委派任务。

核心能力：
- 一键启停多个 AI CLI Agent
- **原生 Agent Sidebar（v7.0+）**：每个 tmux 窗口左侧实时显示所有 Agent 状态，支持点击切换焦点
- **Agent Roles Store（v7.3.0+）**：外部 Agent Roles manager 作为角色唯一写入通道，支持空白环境自动回退安装
- **Artifact Transport（v7.3.0+）**：大消息自动/手动溢写到 text artifact，防止超 context 限制
- **Provider Activity 追踪（v7.0.11+）**：通过 provider-native hook 产物精确识别 Agent 的 active / pending / idle / failed 状态，Sidebar 状态显示更准确
- **Sidebar 面板高度可配置（v7.1.1+）**：Tree/Agent、Comms、Tips 三个面板的高度支持自定义（百分比或行数）
- **Dynamic Reload（v7.1.0+）**：编辑 `ccb.config` 后无需重启整个项目，通过 `ccb reload` 动态应用支持的配置变更
- **多窗口拓扑（v7.0+）**：一个项目可配置多个 tmux 窗口，每个窗口有独立的 Agent 布局和 Sidebar
- Agent 间通信（支持同步等待和异步发送）
- 按项目配置 Agent 团队和 tmux 分屏布局
- 每个 Agent 独立配置 API key、模型、端点
- 可选 git worktree 隔离
- 会话持久化和恢复

---

## 环境要求

| 依赖 | 必需？ | 安装方式 |
|------|--------|----------|
| **Python 3.10+** | 是 | 见下方各平台说明 |
| **tmux** | 是 | 见下方各平台说明 |
| **git** | 是（安装时） | 系统包管理器 |
| **bash 3.2+** | 是（安装脚本） | 系统自带 |
| **curl** | 推荐（更新用） | 系统包管理器 |
| **watchdog >= 2.1.0** | 可选 | 安装脚本自动尝试安装 |

### 安装 tmux

```bash
# macOS
brew install tmux

# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y tmux

# Fedora/CentOS/RHEL
sudo dnf install -y tmux

# Arch/Manjaro
sudo pacman -S tmux

# Alpine
sudo apk add tmux

# openSUSE
sudo zypper install -y tmux
```

### 安装 Python 3.10+

```bash
# macOS
brew install python

# Debian/Ubuntu
sudo apt-get install -y python3

# Fedora/CentOS/RHEL
sudo dnf install -y python3

# Arch/Manjaro
sudo pacman -S python
```

---

## 方式一：Git Clone 全新安装

这是最推荐的方式，适用于新设备首次安装。安装脚本会自动处理所有平台差异。

### 1. 克隆仓库

```bash
git clone https://github.com/nquq700488/claude_code_bridge.git
cd claude_code_bridge
```

### 2. 执行安装

```bash
./install.sh install
```

> **Windows 用户**：`install.ps1` 仅支持基础安装（不含 tmux 主题、`mmx-daemon`、Codex/Droid/Kimi skills），**推荐在 WSL 中使用 `install.sh` 获得完整功能**。

### 安装脚本会做什么（v7.0.x）

安装脚本会按顺序执行以下步骤，每步有中文/英文双语提示：

1. **环境检查**
   - 检查 Python 3.10+
   - 检查 tmux
   - WSL 环境检测与确认
   - 禁止 root 用户执行

2. **安装 watchdog（可选）**
   - 优先使用 `uv pip install`，其次 `pip install --user`，再次 `pipx install`
   - 若全部失败，降级为轮询模式（不影响核心功能）

3. **复制/链接安装树**
   - 默认安装到 `~/.local/share/ccb`
   - 可执行文件链接到 `~/.local/bin/`

4. **创建可执行链接**
   - `ccb` → 主入口
   - `ask` → Agent 间通信
   - `autonew` → 自动新建会话
   - `ctx-transfer` → 上下文传递
   - `mmx-daemon` → MMX 守护进程
   - `ccb-agent-sidebar` → Agent Sidebar 原生 TUI（v7.0+）
   - `ccb-provider-activity-hook` → Provider Activity Hook（v7.0.11+）
   - `build-ccb-agent-sidebar` → Sidebar 构建脚本（v7.0+）
   - `package-ccb-agent-sidebar-release` → Sidebar 发布打包（v7.0+）

5. **配置 PATH**
   - 自动将 `~/.local/bin` 添加到 shell 配置文件（`.zshrc` / `.bashrc` / `.bash_profile`）

6. **安装 Inherited Skills（v7.0+）**
   - 技能源文件从 `inherit_skills/` 目录复制到各 Provider 的 skills 目录
   - Claude skills → `~/.claude/skills/`（ask, ccb-clear 等）
   - `ccb-config` skill 已迁移至 `agentroles.ccb_self` Role Pack（v7.4.0+），不再通过 `inherit_skills/` 安装
   - Codex skills → `~/.codex/skills/`
   - Droid/Factory skills → `~/.factory/skills/`（若检测到 droid CLI）
   - Kimi skills → `~/.kimi/skills/`（若检测到 kimi CLI）
   - 安装时会自动清理旧版本的 obsolete skills（如 `ping`、`pend`、`autonew`、`all-plan` 等已废弃的独立 skill）

7. **注入 CCB 配置到 CLAUDE.md**
   - 在 `~/.claude/CLAUDE.md` 中写入 CCB 协作规则
   - 包括角色分配表、Peer Review 框架、CCB Sync Workflow
   - **v6.2.5+**：managed home 中的 `.claude/CLAUDE.md` 不再复制项目根目录的 `CLAUDE.md`，避免重复加载

8. **配置权限**
   - 在 `~/.claude/settings.json` 中添加 `Bash(ccb ask/ping/pend *)` 权限

9. **配置 tmux（v7.0+ 隔离）**
   - CCB 管理的 tmux 命令默认使用 `tmux -f /dev/null`，**用户的 `~/.tmux.conf` 插件和 hook 不会影响 CCB pane 拓扑**
   - 如需显式指定 tmux 配置文件，可通过环境变量 `CCB_TMUX_CONFIG=/path/to/custom.conf`
   - 安装脚本仍会追加 CCB 专用 tmux 配置到 `~/.tmux.conf`（或 `~/.tmux.conf.local`），供手动 attach 时使用
   - 包括 Tokyo Night 主题、vim 风格按键、鼠标支持、剪贴板集成

10. **构建 Agent Sidebar 二进制（v7.0+）**
    - 若系统安装了 Rust 工具链（`cargo`），自动编译 `tools/ccb-agent-sidebar/`
    - Sidebar 作为原生 TUI 嵌入每个 tmux 窗口左侧，实时显示 Agent 状态
    - 未安装 Rust 时，Sidebar 功能不可用，但 CCB 核心功能不受影响

11. **注册 Droid MCP 委托（可选）**
    - 若检测到 `droid` CLI，自动注册 `ccb-delegation` MCP 工具
    - 使 Droid 能通过 CCB 向其他 Agent 发送 `/ask` 任务

### 安装目录结构

```
~/.local/
├── bin/
│   ├── ccb                         # 主入口
│   ├── ask                         # Agent 通信
│   ├── autonew                     # 自动新建会话
│   ├── ctx-transfer                # 上下文传递
│   ├── mmx-daemon                  # MMX 守护进程
│   ├── ccb-provider-activity-hook  # Provider Activity Hook（v7.0.11+）
│   ├── ccb-agent-sidebar           # Agent Sidebar 原生 TUI（v7.0+）
│   ├── build-ccb-agent-sidebar     # Sidebar 构建脚本（v7.0+）
│   ├── package-ccb-agent-sidebar-release  # Sidebar 发布打包（v7.0+）
│   ├── ccb-status.sh               # 状态栏脚本
│   ├── ccb-border.sh               # 边框颜色脚本
│   ├── ccb-git.sh                  # Git 状态脚本
│   ├── ccb-tmux-on.sh              # 主题启用
│   └── ccb-tmux-off.sh             # 主题关闭
└── share/
    └── ccb/
        ├── ccb             # Python 入口
        ├── lib/            # Python 核心库
        ├── config/         # 配置模板
        ├── inherit_skills/  # Inherited skills 源文件（v7.0+）
        │   ├── claude_skills/
        │   ├── codex_skills/
        │   ├── droid_skills/
        │   └── kimi_skills/
        ├── tools/           # 原生工具（v7.0+）
        │   └── ccb-agent-sidebar/  # Rust TUI Sidebar
        ├── dev_tools/       # 维护者开发工具（不随 release 安装）
        ├── useful_tools/    # 可选用户工具（随 release 分发，不自动安装）
        ├── mcp/             # MCP 委托服务（含 ccb-delegation）
        ├── docs/            # 架构文档
        ├── plans/           # 架构设计与路线图
        └── VERSION          # 版本号
```

### 环境变量覆盖

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CODEX_INSTALL_PREFIX` | `~/.local/share/ccb` | 安装目录 |
| `CODEX_BIN_DIR` | `~/.local/bin` | 可执行文件目录 |
| `CCB_PYTHON_BIN` | 自动检测 | 指定 Python 路径 |
| `CCB_INSTALL_WATCHDOG` | `1` | 设为 `0` 跳过 watchdog 安装 |
| `CCB_CLAUDE_MD_MODE` | `inline` | CLAUDE.md 注入模式：`inline`（内联）/ `route`（指针+外部文件） |
| `CCB_INSTALL_ASSUME_YES` | 空 | 设为 `1` 跳过所有交互确认 |
| `CCB_CONFIRM_MAJOR_UPGRADE` | 空 | 设为 `1` 确认从 pre-v6 升级到大版本 |
| `CCB_LANG` | 自动检测 | 语言：`zh` / `en` |
| `CCB_USE_MANAGED_VENV` | `auto` | 托管 Python venv：`auto` / `1` / `0` |
| `CCB_DROID_AUTOINSTALL` | `1` | 设为 `0` 跳过 Droid MCP 委托自动注册 |
| `CCB_DROID_AUTOINSTALL_FORCE` | `0` | 设为 `1` 强制重新注册 Droid MCP 委托 |
| `CCB_DROID_AUTOINSTALL_TIMEOUT_S` | `10` | Droid MCP 注册超时（秒） |
| `CCB_TMUX_CONFIG` | `/dev/null` | 显式指定 CCB 管理的 tmux 配置文件 |
| `CCB_INSTALL_TOMLI` | `1` | Python 无 tomllib 时自动安装 tomli（v6.2.4+） |
| `CCB_KIMI_NO_TERMINAL_TIMEOUT_S` | `600` | Kimi Agent 无进度超时（秒） |
| `CCB_MMX_NO_TERMINAL_TIMEOUT_S` | `600` | MMX Agent 无进度超时（秒） |
| `CCB_WATCH_TIMEOUT_S` | `600` | `pend --watch` 默认超时（秒，v7.2.1+） |
| `CCB_WAIT_POLL_INTERVAL_S` | `0.1` | `pend --watch` 轮询间隔（秒） |
| `CCB_KEYCHAIN_SERVICE_OVERRIDE` | 空 | macOS Keychain 服务名覆盖（v7.0.4+） |
| `CODEX_CLAUDE_COMMAND_DIR` | 自动检测 | 自定义 Claude commands 目录 |

---

## 方式二：Release 包安装

如果你先通过 Git Clone 安装，之后可以切换到 Release 包模式（支持 `ccb update` 自动更新）：

```bash
# 从 Git Clone 安装后，运行更新切换到 Release 模式
ccb update

# Release 模式特性：
# - 创建托管 Python venv（~/.local/share/ccb/.venv）
# - 可执行文件绑定到托管 venv Python
# - 支持 ccb update 自动更新
# - 不依赖原始 git checkout
```

> **本 fork 说明**：本 fork 不发布 npm 包，全新安装请使用上方「方式一：Git Clone 全新安装」（源码安装）。

---

## 安装后验证

### 1. 检查可执行文件

```bash
which ccb ask
# 应输出：
# ~/.local/bin/ccb
# ~/.local/bin/ask
```

### 2. 检查版本

```bash
ccb --help
# 或
cat ~/.local/share/ccb/VERSION
```

### 3. 在新的项目中测试

```bash
# 创建测试项目
mkdir ~/ccb-test && cd ~/ccb-test

# 创建最小 ccb.config
mkdir -p .ccb
echo 'cmd, agent1:claude' > .ccb/ccb.config

# 启动 CCB（确保 agent CLI 已安装）
ccb
```

### 4. 验证 Skills 安装

```bash
ls ~/.claude/skills/ask/SKILL.md
ls ~/.codex/skills/ask/SKILL.md
```

### 5. 验证 CLAUDE.md 注入

```bash
grep -A 5 "CCB_CONFIG_START" ~/.claude/CLAUDE.md
```

---

## 项目配置（在新设备上创建 Agent 团队）

> **Fork 独有功能**：此 Fork 支持「配置档案路由」——`ccb.config` 写一行 `config_profile = "compact"` 即可在不同布局间切换，无需手动替换文件。详见 [USING_THIS_FORK.md §2.8](./USING_THIS_FORK.md#28-配置档案切换fork-独有功能)。

### ccb.config 语法

CCB 的行为由项目级 `.ccb/ccb.config` 文件控制。该文件不会被安装脚本自动创建，需要手动维护。项目已内置两套档案：`ccb-compact.config`（紧凑单窗口）和 `ccb-multi.config`（多窗口分屏）。

#### 基础布局

第一行定义 Agent 布局：

```text
cmd; writer:codex, reviewer:claude; qa:gemini(worktree)
```

语法说明：
- `cmd` — shell 终端面板
- `agent:provider` — Agent 名和其 AI 服务提供商
- `;` — 左右分屏（horizontal split）
- `,` — 上下堆叠（vertical split）
- `(worktree)` — 该 Agent 使用独立 git worktree 隔离
- `(N)` — 该 pane 的权重比例（默认 1），数字越大占空间越多
- `@N` — 该 pane 的绝对百分比（v7.3.3+），如 `@50` 表示占 50%。`@N` 优先级高于 `(N)` 权重

比例规则：分割按权重总和分配空间，`right_size = round(right_weight_sum / total_weight_sum × 100%)`。叶子权重相同则等高/等宽；权重不同则按比例分配。任一 pane 指定 `@N` 百分比时，百分比直接生效并覆盖权重计算。

```text
# 权重示例：b 占 2 份，a 占 1 份 → b 宽度是 a 的两倍
(a; b(2)), (c; d)  →  顶行左 33%，右 67%；底行等分

# 百分比示例（v7.3.3+）：b 直接占 60%
(a; b@60), (c; d)  →  顶行左 40%（自动计算），右 60%；底行等分

# @N 优先于 (N)：指定 @30 时，括号权重被忽略
(a@30; b(2))  →  a 占 30%，b 占 70%

# 无括号时左结合
a, b; c, d, e       →  左列 a+b，右列 c+d+e（三行等高）
```

#### 完整配置示例（单窗口 / 经典模式）

```toml
cmd; builder:codex, reviewer:claude; research:gemini(worktree)

[agents.builder]
key = "sk-..."
url = "https://api.example.com/v1"
model = "gpt-5"

[agents.reviewer]
key = "sk-ant-..."
url = "https://api.anthropic.com"
model = "opus"

[agents.research]
key = "gemini-key"
model = "gemini-pro"
```

#### 多窗口拓扑（v7.0+）

当 Agent 数量较多时，可将它们拆分到多个 tmux 窗口，每个窗口有独立的 Sidebar：

```toml
# 定义多个窗口及其布局
[windows]
main   = "architect:codex; reviewer:claude"
code   = "developer:codex"
test   = "tester:codex"

# 指定启动后默认进入的窗口
entry_window = "main"

# Sidebar 配置（可选，默认启用）
[ui.sidebar]
mode = "every_window"   # "every_window" 每个窗口都显示 / "off" 关闭
width = "15%"
bottom_height = 20

[ui.sidebar.view]
agents_height = "50%"   # Tree/Agent 面板高度（v7.1.1+）
comms_height = "15%"    # Comms 面板高度（v7.1.1+）
tips_height = "35%"     # Tips 面板高度（v7.1.1+）
comms_limit = 5
comms_compact = true
tips_enabled = true

[agents.architect]
description = "架构设计"

[agents.reviewer]
description = "代码审查"

[agents.developer]
description = "核心开发"

[agents.tester]
description = "测试工程师"
```

多窗口规则：
- `cmd` 面板**不支持**放在 `windows` 中（多窗口模式下没有全局 cmd）
- 每个 window 内的 Agent 必须显式声明 provider（如 `architect:codex`）
- 同一个 Agent **不能**出现在多个 window 中
- 不声明 `[windows]` 时，回退到经典单窗口一行布局语法

Agent 配置字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | string | API Key（如 OpenAI / Anthropic / Google 等） |
| `url` | string | API Base URL（自定义端点或代理） |
| `model` | string | 模型名称（覆盖 provider 默认模型） |
| `api` | table | 嵌套表写法 `[agents.x.api]`，等价于 `key`/`url` |
| `env` | mapping | 额外注入的环境变量（`{ "FOO" = "bar" }`） |
| `startup_args` | list | 传给 provider CLI 的额外启动参数 |
| `workspace_root` | string | 自定义工作目录（必须是**绝对路径**） |
| `provider_profile` | table | Provider 状态隔离配置，见下方说明 |
| `queue_policy` | string | 任务队列策略，如 `"serial-per-agent"`（串行单 Agent） |
| `permission` | string | 权限模式：`"auto"` / `"manual"` |

#### 项目级共享记忆 `.ccb/ccb_memory.md`（v6.2.1+）

在项目根目录创建 `.ccb/ccb_memory.md`，写入项目级的工作流指南、代码规范、架构约定等。所有 Agent 在启动时都会读取这份共享记忆，无需在每个 Agent 的 `memory.md` 中重复定义。

```markdown
# Project Memory

## 技术栈
- Python 3.12 + FastAPI
- PostgreSQL + SQLAlchemy
- pytest + mypy

## 代码规范
- 所有函数必须带类型注解
- 异步函数统一使用 `async def`
```

#### Per-Agent 记忆 `.ccb/agents/<agent>/memory.md`（v6.2.1+）

针对特定 Agent 的角色补充说明，放在 `.ccb/agents/<agent-name>/memory.md`。例如给 reviewer Agent 写入审查重点：

```markdown
# Reviewer Guidelines

- 重点关注类型安全和异常处理
- 检查是否有未处理的边界条件
```

#### `ccb_config` Skill → `agentroles.ccb_self`（v7.4.0+）

从 v7.4.0 开始，`ccb-config` skill 从 `inherit_skills/` 迁移至 **`agentroles.ccb_self`** Role Pack，作为 CCB 专属的自维护角色资产。安装 `agentroles.ccb_self` 后，绑定的 Agent 将自动获得 ccb-config 能力：

```bash
# 安装 ccb_self 角色（install.sh 和 ccb update 也会交互提示）
ccb roles install agentroles.ccb_self

# 在项目中使用：将 ccb_self 绑定到一个 Agent
ccb roles add agentroles.ccb_self:codex
```

该 skill 支持通过自然语言设计或更新 Agent 团队：

```text
$ccb_config Design a team for a Python library with one coordinator,
two worktree implementation agents, and one reviewer.
```

此 skill 持续验证 `.ccb/ccb.config` 是配置的唯一权威来源。

#### `provider_profile` 隔离配置

```toml
[agents.my-agent.provider_profile]
mode = "inherit"          # "inherit" 继承全局配置（默认）/ "isolated" 完全隔离
home = "/custom/home"     # 自定义 provider home 目录
env = { "CUSTOM_VAR" = "value" }
inherit_api = true        # 是否继承全局 API 设置
inherit_auth = true       # 是否继承全局认证信息
inherit_config = true     # 是否继承全局配置
inherit_skills = true     # 是否继承全局 skills
inherit_commands = true   # 是否继承全局 commands
```

#### Job Heartbeat 超时配置（v7.6.4+）

Job Heartbeat 是 CCB 的任务级心跳监控机制。当 Agent 收到任务后在指定时间内无进度输出（如 extended thinking），CCB 会判定超时并标记任务失败。从 v7.6.4 起，超时参数可在项目级 `ccb.config` 中配置：

```toml
[maintenance.heartbeat]
# Job 心跳超时配置（所有值必须是正整数）
job_silence_start_after_s = 600    # 静默多久开始心跳检测（默认 600s，即 10 分钟）
job_repeat_interval_s = 300        # 每次心跳通知间隔（默认 300s，即 5 分钟）
job_terminal_notice_count = 3      # 多少次通知后判定超时（默认 3 次）
# 总超时窗口 = job_silence_start_after_s + job_repeat_interval_s × job_terminal_notice_count
# 默认：600 + 3×300 = 1500s（25 分钟）
```

**超时窗口计算**：`总等待时间 = silence_start + repeat_interval × terminal_notice_count`

| 场景 | silence_start | repeat_interval | terminal_notices | 总等待 |
|------|---------------|-----------------|------------------|--------|
| 默认（extended thinking 友好） | 600s | 300s | 3 | 25 分钟 |
| 激进（快速反馈） | 120s | 120s | 3 | 8 分钟 |
| 宽松（大型任务） | 900s | 600s | 5 | 65 分钟 |
| 禁用超时检测 | 任意 | 任意 | 0 | ∞ |

> **注意**：`job_terminal_notice_count = 0` 会完全禁用 Job Heartbeat 超时检测。`job_silence_start_after_s` 和 `job_repeat_interval_s` 建议根据 Agent 使用的模型推理速度调整——使用 Extended Thinking（DeepSeek/Claude）时建议不小于默认值。

### 常用布局模板

```text
# 最简单：一个 Agent + 终端
cmd, agent1:claude

# 双 Agent 上下排列
writer:codex, reviewer:claude

# 标准三角色团队
cmd; writer:codex, reviewer:claude; qa:gemini(worktree)

# 同一 Provider 不同模型
cmd; fast:codex, deep:codex

# 全部 Provider（v7.5.2+ 支持 14 个 CLI 家族：Codex、Claude、Gemini、Kimi、Antigravity、OpenCode、Droid、MMX、DeepSeek、MiMo、Qwen、Cursor、Copilot、Crush、Kiro、Pi）
cmd, agent1:codex; agent2:claude, agent3:kimi; agent4:mmx, agent5:agy

# 按权重非对称布局：主面板更宽
cmd; main:codex(3), reviewer:claude; qa:gemini

# 按百分比精确分割（v7.3.3+）：主面板固定 70%
cmd; main:codex@70, reviewer:claude; qa:gemini
```

#### Chain Ask（链式委派，v8.0.9+）

当 Agent 正在处理 CCB 任务时，如果需要另一个 Agent 的结果才能继续，必须使用 `--chain`（旧名 `--callback`）而非普通 `ask`：

```bash
# 在 Agent 内部调用（支持链式委派：agent2 -> agent4 -> agent1 -> agent3）
ccb ask --chain reviewer <<'EOF'
Review this failing test and return the minimal blocker.
EOF

# --callback 作为兼容别名仍然可用
ccb ask --callback reviewer <<'EOF'
Review this failing test and return the minimal blocker.
EOF
```

CCB 会记录父子任务关系，子任务完成后自动将结果回传给父 Agent 作为新的 continuation 任务。普通 `ask` 仅在**没有活跃 CCB 任务**时使用；在活跃任务内使用普通 `ask` 可能导致任务状态混乱。

#### Notify Sender（v7.0.9+）

当向其他 Agent 发送任务后，除了默认的同步等待回复外，还可以通过 `--notify-sender` 要求**在任务完成时向 sender inbox 发送一条通知**（无论成功、失败或取消）：

```bash
# 发任务时附加通知标志
ccb ask --notify-sender planner <<'EOF'
请设计登录页面
EOF

# 后续在 sender 的 inbox 中查看通知
ccb inbox executor
```

通知内容示例：
```
CCB job job_abc for agent `planner` has finished with status: completed.
Use `ccb trace job_abc` to view the full result.
```

与 `--chain`（旧名 `--callback`）的区别：
- `--chain`：标记为链式任务，创建 continuation job，**要求 parent Agent 有活跃的 provider session 来接收回传任务**（Claude/Codex 支持，Kimi pane-log 模式不支持持续 watch）
- `--notify-sender`：仅在任务完成时向 sender inbox 发送一条系统 notice，**不创建 continuation job，不依赖 provider watch 机制**，适合所有 provider（包括 Kimi）
- 两者可以独立使用，也可以组合使用

#### Artifact Transport（v7.3.0+）

当消息体超过 4 KiB 时，CCB 会自动将请求/回复存入 text artifact 文件，防止超过 provider 的上下文限制。也可以通过显式标志强制启用：

```bash
# 强制将请求正文存入 artifact（无论大小）
ccb ask --artifact-request agent2 <<'EOF'
这个需求文档非常长...
EOF

# 强制目标 Agent 的回复也存入 artifact
ccb ask --artifact-reply agent2 帮我收集所有日志

# 等价于同时启用 --artifact-request 和 --artifact-reply
ccb ask --artifact-io agent2 处理大型数据集

# 可与其它标志组合使用
ccb ask --chain --artifact-reply agent2 collect long evidence
```

| 标志 | 作用 |
|------|------|
| `--artifact-request` | 强制将请求正文存储为 CCB text artifact |
| `--artifact-reply` | 强制目标 Agent 的最终回复存储为 text artifact |
| `--artifact-io` | 同时启用 `--artifact-request` 和 `--artifact-reply` |
| （不指定） | 请求 > 4 KiB 时自动溢出为 artifact（默认行为） |

#### Role Packs → Agent Roles Store（v7.3.0+）

从 v7.3.0 开始，Role Pack 机制升级为 **Agent Roles Store**，使用外部 Agent Roles manager 作为唯一的 Role 写入通道，已安装的 Role 仅从 Roles Store 读取。安装流程也更健壮：优先 `ccb roles update` 增量刷新，首次安装（空白环境）时自动回退到 `ccb roles install` 完成初始化。

目前内置两个推荐角色：

| Role | 用途 |
|------|------|
| `agentroles.archi` | 架构审查，由 Architec npm 包支撑 |
| `agentroles.ccb_self` | CCB 自维护角色，含 `ccb-config`、`ccb-self-diagnose`、`ccb-self-recover`、`ccb-self-chain` 等 skill |

**安装/刷新 Role**：

```bash
# 安装或刷新内置 role（install.sh 和 ccb update 也会交互提示）
ccb roles update ccb.archi
```

**在项目中使用 Role**：

```bash
# 将 role 绑定到项目，紧凑形式写入 ccb.config
ccb roles add ccb.archi:codex

# 动态应用变更
ccb reload
```

运行时 CCB 会将 `ccb.archi:codex` 解析为项目本地 agent `archi`，并自动投影 role memory 和 skills。

**配置格式**：在 layout 中直接使用 `role:provider` 形式：

```toml
[windows]
main = "ccb.archi:codex, developer:codex"
review = "reviewer:claude"
```

#### 托管工具 Window（v7.2.0+）

工具 window 是 CCB 管理的 tmux window，但不是 Agent。它不会出现在 `ccb ask` 目标中，也不会创建 provider runtime 记录。目前内置 Neovim 托管工具。

```toml
[tool_windows.neovim]
command = "ccb-nvim"
label = "neovim"
```

**工具安装与诊断**：

```bash
# 安装托管 Neovim（隔离的 ccb-nvim wrapper + LazyVim profile）
ccb tools install neovim

# 诊断托管 profile 健康状态
ccb tools doctor neovim
```

`install.sh install` 和 `ccb update` 会在交互终端询问是否安装；非交互安装会跳过并打印后续命令。设置 `CCB_INSTALL_NEOVIM=1` 可强制 provisioning，`CCB_INSTALL_NEOVIM=0` 跳过。

---

## 更新与升级

### 自动更新

```bash
ccb update              # 更新到最新稳定版
ccb update 6            # 更新到 v6.x.x 最高版本
ccb update 6.2.6        # 更新到指定版本
```

> **v7.0+ 升级注意**：如果当前是 source dev 模式，`ccb update` 会下载最新 release 并切换为 managed release 模式（全局 `ccb` 指向 release 安装目录，不再 symlink 到 git checkout）。如需保持 source dev 模式，请用 `git pull` + `./install.sh install` 更新。

### Source Dev 模式更新

如果你是从 Git Clone 安装的（source dev 模式）：

```bash
cd /path/to/claude_code_bridge
git pull                 # 拉取 upstream 最新代码
./install.sh install     # 重新安装以更新 links、skills 和 entrypoint smoke check
```

> **Source dev 模式特性**：
> - 安装目录通过 **符号链接（symlink）** 指向原始 git checkout，修改代码后立即生效，无需重新安装
> - `inherit_skills/` 下的技能也会跟随 git checkout 实时更新
> - 不参与 startup 时的自动更新提示
> - 运行 `ccb update` 后会切换为 managed release 模式

### Release 包与 Source Dev 切换

```bash
# Source dev -> Release（下载 GitHub release 资产）
ccb update

# Release -> Source dev（重新指向 git checkout）
cd /path/to/claude_code_bridge
./install.sh install
```

### 重新安装

```bash
ccb reinstall            # 清理后重新安装
```

---

## 卸载

```bash
# 方式一：ccb 命令卸载
ccb uninstall

# 方式二：安装脚本卸载
cd /path/to/claude_code_bridge
./install.sh uninstall
```

卸载会移除：
- `~/.local/share/ccb` — 安装目录（含 `inherit_skills/`、`dev_tools/`、`useful_tools/`）
- `~/.local/bin/ccb`, `ask`, `autonew`, `ctx-transfer`, `mmx-daemon`, `ccb-provider-activity-hook` — 主可执行文件
- `~/.local/bin/ccb-status.sh`, `ccb-border.sh`, `ccb-git.sh`, `ccb-tmux-on.sh`, `ccb-tmux-off.sh` — tmux 辅助脚本
- `~/.claude/CLAUDE.md` 中的 CCB 配置块
- `~/.claude/settings.json` 中的 CCB 权限
- `~/.tmux.conf` / `~/.tmux.conf.local` 中的 CCB tmux 配置
- `~/.claude/skills/` 中的 inherited CCB skills（v6.2.1+ 从 `inherit_skills/claude_skills/` 安装）
- `~/.codex/skills/` 中的 inherited CCB skills
- `~/.factory/skills/` 中的 inherited CCB skills
- `~/.kimi/skills/` 中的 CCB skills（本地 kimi_skills/ 安装）

不会移除：
- Python、tmux 等系统依赖
- 项目目录下的 `.ccb/` 配置
- 用户原始的 `~/.claude/`、`~/.codex/` 等 Provider 全局配置（仅移除 CCB 注入的部分）

### 高级：跨项目工作流

默认情况下，所有 Agent 都在当前项目的目录中运行。通过 `workspace_root` 可以让某个 Agent 在**任意目录**启动 provider CLI，从而分析和操作其他项目的代码。

#### 场景示例：分析项目 B 并在项目 A 中复现

假设你在 `/path/to/project-a` 中工作，需要参考 `/path/to/project-b` 的实现：

```toml
# project-a/.ccb/ccb.config
(cmd); ((architect:codex; reviewer:claude), (developer:codex; b-explorer:kimi))

[agents.architect]
description = "A 项目架构设计"

[agents.reviewer]
description = "A 项目代码审查"

[agents.developer]
description = "A 项目开发实现"

[agents.b-explorer]
provider = "kimi"
workspace_root = "/absolute/path/to/project-b"
description = "B 项目分析器 - 在 B 目录运行，读取 B 的代码"
```

工作流：

```bash
# 1. 让 b-explorer 分析 B 的实现
ccb ask b-explorer "分析 B 项目中 feature-x 的实现，输出技术方案"

# 2. 让 developer 在 A 项目中复现
ccb ask developer "参考以下方案在 A 项目中实现：[贴 b-explorer 回复]"
```

#### `workspace_root` 关键规则

| 规则 | 说明 |
|------|------|
| **必须是绝对路径** | `workspace_root = "/Users/xxx/project-b"`，不能是相对路径 |
| **Provider 在该目录运行** | Claude Code / Codex / Kimi 启动时的 cwd 就是该目录 |
| **pane 仍在当前项目** | tmux 分屏位置不变，只是 provider 进程的工作目录不同 |
| **B 最好是 git 仓库** | Claude Code 启动时会检查 git，非 git 目录可能报错 |
| **session 仍在当前项目管理** | `.ccb/.kimi-b-explorer-session` 等仍存放在项目 A 的 `.ccb/` 中 |

#### 简化版：不新增 agent，临时借用 cmd slot

如果你只是临时需要看一下 B 的代码，不需要改配置：

```bash
# 在 cmd pane 里
cd /path/to/project-b && cat src/feature-x.ts | head -100

# 把代码 copy 出来，ask A 项目的 agent
ccb ask developer "参考这段代码在 A 项目中实现：[贴代码]"
```

---

## 常见问题排查

### Q1: 安装时报 "Python version too old"

确保 Python 3.10+：

```bash
python3 --version
# 如版本过低，升级 Python 后重新运行 install.sh
```

### Q2: 安装时报 "Missing dependency: tmux"

先安装 tmux（参考上方 [安装 tmux](#安装-tmux) 章节）。

### Q3: macOS 上提示 "Homebrew not found"

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install tmux python
```

### Q4: WSL 环境安装注意事项

- CCB 和所有 Agent CLI 必须在 WSL 内运行（不是 Windows 原生）
- 对于挂载盘项目（`/mnt/c/...`），CCB 的运行时状态会自动迁移到本地 Linux 路径
- WSL 1 用户可能需要升级到 WSL 2

### Q5: 启动 CCB 后看不到 Agent 响应

检查 Agent CLI 是否已安装：

```bash
which claude     # 若使用 Claude agent
which codex      # 若使用 Codex agent
which gemini     # 若使用 Gemini agent
which kimi       # 若使用 Kimi agent
which mmx-daemon # 若使用 MMX agent
which agy        # 若使用 Antigravity agent
```

> **Kimi 安装提示**：Kimi Code 是 VS Code 扩展，需要先在 VS Code 中安装 [Kimi Code 扩展](https://marketplace.visualstudio.com/items?itemName=moonshot-ai.kimi-code)。`kimi` CLI 通常位于 `~/.local/bin/kimi` 或 VS Code 扩展目录中。
>
> **MMX 安装提示**：`mmx-daemon` 随 CCB 一起安装到 `~/.local/bin/mmx-daemon`，无需额外安装。

### Q6: `ccb` 命令找不到

```bash
# 重新加载 shell 配置
source ~/.zshrc   # zsh 用户
source ~/.bashrc  # bash 用户

# 或检查 PATH 是否包含 ~/.local/bin
echo $PATH | tr ':' '\n' | grep local
```

### Q7: tmux 中剪贴板无法使用

```bash
# macOS 需要 reattach-to-user-namespace
brew install reattach-to-user-namespace
```

### Q8: Claude 提示缺少权限

```bash
# 检查 settings.json 是否包含 CCB 权限
cat ~/.claude/settings.json | python3 -m json.tool | grep "ccb"
# 如缺失，重新运行 ./install.sh install 即可
```

### Q9: 如何重置某个项目的 CCB 状态

```bash
# 在项目目录下
ccb kill -f        # 强制停止当前运行时
rm -rf .ccb        # 删除运行时状态（保留 ccb.config 请先备份）
ccb -n             # 重建 .ccb，重新启动
```

### Q10: PCI 校验失败 / 修改代码后行为不变

通常是因为 Python `.pyc` 字节码缓存未更新。`sync-to-local.sh` 同步脚本会在 rsync 前自动清除缓存，但手动修改安装目录代码时需要：

```bash
# 清除 Python 编译缓存
find ~/.local/share/ccb -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find ~/.local/share/ccb -name "*.pyc" -delete 2>/dev/null

# 然后重启 CCB
ccb kill && ccb
```

### Q11: Tmux pane 布局异常 / 插件干扰（v7.0+）

CCB v7.0+ 默认使用 `tmux -f /dev/null` 运行管理的 tmux 命令，用户的 `~/.tmux.conf` 插件不会再干扰 CCB pane 拓扑。如果你之前通过 `~/.tmux.conf` 配置了 CCB 主题或按键，这些配置现在**仅在手动 `tmux attach` 时生效**。

如需为 CCB 显式指定 tmux 配置文件：

```bash
export CCB_TMUX_CONFIG="$HOME/.tmux.conf.ccb"
ccb
```

### Q12: Sidebar 不显示或显示异常（v7.0+）

Agent Sidebar 需要 Rust 工具链在**安装时**编译。如果 Sidebar 没有显示：

```bash
# 检查 sidebar 二进制是否存在
which ccb-agent-sidebar

# 如果不存在，手动构建（需要 Rust）
cd /path/to/claude_code_bridge
cargo build --release --manifest-path tools/ccb-agent-sidebar/Cargo.toml

# 然后重新安装以注册到 PATH
./install.sh install
```

### Q13: Codex Agent 任务失败或 bridge 日志报 "AF_UNIX path too long"

macOS 的 Unix Domain Socket 路径长度限制为 104 字节。当项目目录较深时，Codex bridge socket 路径可能超出限制，导致 socket server 启动失败。

**v7.0.9+ 已修复**：bridge socket 会自动降级到 `/tmp/ccb-codex-<hash>.sock` 短路径。如仍遇到问题，请确保 CCB 已更新到 v7.0.9+。

### Q14: Kimi/MMX Agent 任务卡住无响应

v7.6.4+ 为所有 Agent 引入项目级可配置的 Job Heartbeat 超时检测。当 Agent 在指定时间内无进度事件（如 `ANCHOR_SEEN`、`ASSISTANT_CHUNK`、`TURN_BOUNDARY`）时，任务自动标记为超时并结束。默认超时窗口为 25 分钟（600s 静默开始 + 3×300s 通知间隔），已为 Extended Thinking 模型优化。

调整方式：

```bash
# 方式一：环境变量（Kimi/MMX 专用，向后兼容）
export CCB_KIMI_NO_TERMINAL_TIMEOUT_S=300
export CCB_MMX_NO_TERMINAL_TIMEOUT_S=300
ccb
```

```toml
# 方式二：ccb.config 项目级配置（v7.6.4+，所有 Agent 通用）
[maintenance.heartbeat]
job_silence_start_after_s = 600    # 静默多久开始检测（默认 600s）
job_repeat_interval_s = 300        # 检测间隔（默认 300s）
job_terminal_notice_count = 3      # N 次后超时（默认 3 次）
```

详见上方 [Job Heartbeat 超时配置](#job-heartbeat-超时配置v764) 章节。

### Q15: Kimi Agent 启动后立即崩溃、陷入无限重启、或回复后任务不完成

**现象 A（启动崩溃）**：运行 `.ccb/clean.sh` 后启动项目，或首次启动 Kimi Agent 时，Kimi pane 反复崩溃重启，日志中出现 `OSError: [Errno 22] Invalid argument`。

**现象 B（任务卡住不完成）**：Kimi 在 pane 中生成了回复，但 CCB 未检测到任务完成，job 一直处于 running 状态直到超时。

**根因**：
1. **会话恢复冲突**：CCB 默认启动时会尝试恢复 provider 历史会话，但 Kimi 的 launcher 以前无条件传递 `--continue` 给 Kimi CLI。当本地无历史会话（如 `clean.sh` 清除后），Kimi CLI 会因找不到可恢复会话而崩溃，CCB  supervision 检测到崩溃后重启 pane，再次传入 `--continue`，形成无限崩溃循环。
2. **PTY 兼容性**：Kimi CLI 使用的 prompt_toolkit 在 tmux PTY（特别是 macOS kqueue Selector）环境下存在底层兼容性问题，可能触发 `OSError: [Errno 22]`。
3. **Kimi CLI v2.x 会话存储格式变更**：Kimi CLI v2.x 将回复从 `context.jsonl` 改为 `wire.jsonl` 事件协议，存储路径从 `~/.kimi/sessions/` 迁移到 `~/.kimi-code/sessions/`。CCB 已同时支持两种格式，通过 `session_index.jsonl` 自动发现新格式会话。

**修复状态**：v7.0.12+ 已修复启动崩溃问题；Kimi CLI v2.x wire 协议支持已合入。

**修复内容**：
- Kimi launcher 仅在 agent 配置中显式设置 `restore = "provider"` 时才传递 `--continue`；默认 `AUTO` / `FRESH` 模式下不再传递，避免无历史会话时崩溃。
- Kimi launcher 启动前自动注入两个环境变量缓解 PTY 兼容问题：
  - `PROMPT_TOOLKIT_NO_CPR=1` — 禁用 prompt_toolkit 的 Cursor Position Request
  - `TERM=xterm-256color` — 覆盖 tmux 默认的 `tmux-256color`，减少 terminfo 差异
- `KimiLogReader` 同时支持旧格式（`context.jsonl`）和新格式（`wire.jsonl`），优先通过 `session_index.jsonl` 发现新格式会话

**如需显式启用 Kimi 本地会话恢复**：

在 `.ccb/ccb.config` 中对应 agent 配置：

```toml
[agents.reviewer]
provider = "kimi"
restore = "provider"   # 仅在需要恢复 Kimi 本地历史会话时启用
```

> **注意**：Kimi 的 CCB manifest 声明 `supports_resume=True`（v7.5.0+），但执行适配器仍以 `resubmit_required` 模式运行——中断的 in-flight job 不支持跨重启恢复到原生 turn log 中间状态。

### Q16: Agent 长时间空闲后返回旧结果/过期回复

**现象**：Agent 空闲一段时间（如 10 分钟以上）后，orchestrator 拿到的是之前某次任务的旧结果，而不是当前最新执行的结果。但 agent 终端显示执行正常，手动重新 ask 后可以拿到正确结果。

**影响范围**：Claude、OpenCode、Kimi 三个 Provider 的 Agent。

**根因**：Agent 空闲期间，Provider CLI 可能自动创建新的本地会话文件。旧代码中，Completion Detector 的 session reader 被创建时绑定了旧的会话路径。当文件系统上出现新会话时，Claude 的 polling loop 会将读取偏移重置为 0，从而将新会话文件中的**全部历史消息**重新输出为"当前完成结果"。

**修复状态**：**v7.2.1+ 已修复**。三个 Provider（Claude、OpenCode、Kimi）的 Execution Adapter 现已遵循 Codex 在 ISSUE-017 中确立的刷新模式——每轮 poll 前主动检查当前磁盘会话绑定是否与 reader 中缓存的一致，发现变化则重建 reader 并从文件末尾开始读取，避免将历史消息误判为新完成结果。

**临时规避**（v7.2.0 及更早版本）：遇到此问题时，重新发起一次 ask（会创建新的 submission 和 reader，绑定到当前会话，跳过旧内容）。

### Q17: Source dev 安装后 `ccb` 报 Python 版本冲突

v7.0+ 源码安装使用 Python wrapper，会尝试检测并使用正确的 Python 解释器。如果系统同时存在多个 Python 版本（如 macOS 的 Xcode Python 3.9 和 Homebrew Python 3.12），可通过环境变量强制指定：

```bash
export CCB_PYTHON_BIN=/opt/homebrew/bin/python3.12
./install.sh install
```

---

## 配置文件速查

| 文件 | 位置 | 作用 |
|------|------|------|
| `ccb.config` | `<project>/.ccb/ccb.config` | 项目 Agent 团队布局和 API 配置 |
| `ccb_memory.md` | `<project>/.ccb/ccb_memory.md` | 项目级共享记忆文档（v6.2.1+） |
| `memory.md` | `<project>/.ccb/agents/<agent>/memory.md` | Per-Agent 角色记忆（v6.2.1+） |
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude 全局系统提示（含 CCB 协作规则） |
| `settings.json` | `~/.claude/settings.json` | Claude 权限设置 |
| `settings.local.json` | `<project>/.claude/settings.local.json` | 项目级 Claude 本地设置（Stop hooks） |
| `claude.json` | `~/.claude.json` | Claude 全局配置 |
| `AGENTS.md` | `~/.local/share/ccb/AGENTS.md` | Peer Review 评分维度与角色分配 |
| `.clinerules` | `~/.local/share/ccb/.clinerules` | CCB 角色分配与协作规则（IDE 扩展读取） |
| `tmux.conf` | `~/.tmux.conf` | Tmux 全局配置（含 CCB 主题和按键） |
| `install.sh` | `<repo>/install.sh` | 安装/卸载脚本 |
| `install.ps1` | `<repo>/install.ps1` | Windows PowerShell 安装脚本 |

### 运行时状态目录

```
<project>/.ccb/
├── ccb.config              # 用户维护的团队配置
├── ccb_memory.md           # 项目级共享记忆（v7.0+）
├── ccbd/                   # 控制平面守护进程状态
│   ├── state.json          # tmux 会话状态
│   ├── lifecycle.json      # 生命周期管理
│   ├── keeper.json         # 守护进程监控
│   ├── mailboxes/          # Agent 邮箱
│   ├── replies/            # 回复队列
│   └── *.log               # 守护进程日志
├── agents/                 # 各 Agent 运行时
│   └── <agent-name>/
│       ├── agent.json      # Agent 规格
│       ├── jobs.jsonl      # 任务队列
│       ├── memory.md       # Per-Agent 角色记忆（v7.0+）
│       ├── provider-runtime/  # Provider 运行时产物（v7.0+）
│       │   └── <provider>/
│       │       ├── bridge.sock      # Codex bridge socket（可能位于 /tmp）
│       │       ├── input.fifo       # Codex FIFO 输入
│       │       ├── output.fifo      # Codex FIFO 输出
│       │       ├── completion/      # Hook 完成事件
│       │       └── ...
│       └── provider-state/    # Provider 隔离状态
└── history/                # 会话历史归档
```

---

## 开发工具与实用工具

### `dev_tools/` — 维护者工具（不随 Release 安装）

位于源码仓库的 `dev_tools/` 目录，维护者专用，**不会被打包到 release 资产中**。

- **`dev_tools/skills/ccb-github/`**：Release Checker Skill
  - 检查 GitHub release 状态、Markdown 文档一致性、CI 工作流配置
  - 包含 `check_release_state.py` 等 7 个 Python 脚本模块
  - 用法：在支持 skill 的 Provider 中调用 `$ccb_github check release`

### `useful_tools/` — 可选用户工具（随 Release 分发）

位于源码仓库的 `useful_tools/` 目录，**随 release 分发但不自动安装**到 Provider home。

- **`useful_tools/claude_skills/plan-tree/`**：Claude 版本 plan-tree skill
- **`useful_tools/codex_skills/plan-tree/`**：Codex 版本 plan-tree skill

如需使用，手动复制到对应 Provider 的 skills 目录：

```bash
# 例如安装 plan-tree skill 到 Claude
cp -r useful_tools/claude_skills/plan-tree ~/.claude/skills/
```

---

## 架构说明

### CCB 如何工作

```
┌─────────────────────────────────────────────────┐
│                   tmux 窗口                       │
│  ┌──────────┬──────────────┬──────────────────┐  │
│  │   cmd    │   agent1     │   agent2         │  │
│  │ (shell)  │  (codex)     │  (claude)        │  │
│  │          │              │                  │  │
│  │  用户    │  执行代码    │  审查代码         │  │
│  │  交互    │              │                  │  │
│  └──────────┴──────────────┴──────────────────┘  │
│                   ccbd 守护进程                    │
│         (Unix Socket: .ccb/ccbd/ccbd.sock)        │
│   ┌──────────────────────────────────────────┐    │
│   │  邮箱系统 / 任务队列 / 生命周期管理        │    │
│   └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Agent 通信流程

```
用户/Agent → /ask reviewer <message>
  → ccb ask CLI 提交任务到 reviewer 邮箱
  → ccbd 路由到 reviewer 的 mailbox
  → reviewer Agent 检测到新消息（通过 stop hook）
  → reviewer 处理任务
  → 处理完成后，ccbd 将结果放入回复队列
  → /ask skill 自动通过 pend --watch <job_id> 阻塞等待回复
  → 调用方在同一回合看到 reviewer 的回复
```

### Provider 隔离

每个 Agent 的 Provider 状态完全隔离：
- Claude agent 的 `~/.claude/` 等价状态存储在 `.ccb/agents/<name>/provider-state/claude/home/`
- Codex agent 的 `~/.codex/` 等价状态存储在 `.ccb/agents/<name>/provider-state/codex/home/`
- Gemini agent 的 `~/.gemini/` 等价状态存储在 `.ccb/agents/<name>/provider-state/gemini/home/`
- Droid agent 的状态存储在 `.ccb/agents/<name>/provider-state/droid/home/`
- Kimi agent 使用 VS Code 扩展原生配置，CCB session 文件为 `.ccb/.kimi-<agent>-session`，Kimi CLI 自身的会话日志存储在 `~/.kimi/sessions/`（v1.x）或 `~/.kimi-code/sessions/`（v2.x，wire.jsonl 格式）
- MMX agent 使用 pane log 协议，无 managed home，session 状态存储在 pane log 中
- Antigravity (`agy`) agent 使用 Google Antigravity CLI，session 由 CCB 标准 session 机制管理
- 互不污染，全局 Provider 配置不会被修改

### Provider Activity 追踪（v7.0.11+）

v7.0.11 引入 Provider Activity Hook 机制，Sidebar 不再仅依赖 pane 文本推断 Agent 状态，而是通过 provider-native 的 hook 产物直接获取活动证据：

```
Provider CLI → hook artifact (.ccb/agents/<name>/provider-runtime/<provider>/completion/)
  → ccb-provider-activity-hook 写入结构化状态文件
  → ccbd 读取并聚合为 provider_activity 视图
  → Sidebar 实时展示 active / pending / idle / failed 状态
```

优势：
- **更准确**：区分 Agent 真正在处理任务 vs 仅 pane 有输出
- **更实时**：focus 切换后立即刷新缓存视图，减少 stale 状态
- **更轻量**：tmux pane 点击直接使用原生 `select-pane` binding，降低延迟

---

## 快速命令参考

```bash
# 项目管理
ccb                    # 启动 Agent 团队
ccb -s                 # 安全启动（保留权限策略）
ccb -n                 # 重建运行时（保留 ccb.config）
ccb kill               # 停止项目运行时
ccb kill -f            # 强制清理
ccb restart            # 重启所有 Agent pane
ccb restart <agent>... # 重启指定 Agent（可多个）
ccb maintenance status  # 查看 maintenance heartbeat 策略与状态（v7.4.1+）
ccb maintenance tick    # 运行一次诊断 tick（v7.4.1+）
ccb reload             # 动态应用支持的配置变更（v7.1.0+）
ccb rich               # 启动 Rich Workbench 生命周期管理（v7.6.0+）
ccb reload --dry-run   # 预览 reload 计划而不执行（v7.1.0+）

# Role Packs（v7.2.0+）
ccb roles add <role:provider>    # 将 role 绑定到项目
ccb roles install <role>         # 安装 role 资产和依赖
ccb roles update <role>          # 刷新 role 资产

# 托管工具（v7.2.0+）
ccb tools install <tool>         # 安装托管工具
ccb tools doctor <tool>          # 诊断托管工具健康状态

# 安装/更新
./install.sh install   # 安装或更新
./install.sh uninstall # 卸载
ccb update             # 更新到最新版
ccb reinstall          # 重新安装

# Agent 间通信（在 Agent 内部使用）
/ask <agent> <message>            # 向指定 Agent 委派任务（默认同步等待回复）
ccb ask --silence <agent>         # 静默提交（不等待回复，v6.2.x+）
ccb ask --callback <agent>        # 链式委派（--callback 兼容别名，v8.0.9+ 推荐 --chain）
ccb ask --notify-sender <agent>   # 任务完成后通知 sender（v7.0.9+）
/ping <agent|ccbd>                # 检查 Agent 或控制平面健康
/pend <agent|job_id>              # 查看 Agent 回复

# 等待与观察
ccb pend --watch <agent|job_id>   # 阻塞等待并流式查看回复
ccb wait-any <agent>...        # 等待任意一个 Agent 回复
ccb wait-all <agent>...        # 等待所有指定 Agent 回复
ccb wait-quorum <N> <agent>... # 等待 N 个 Agent 回复（法定多数）

# 高级诊断
ccb ps                 # 运行时清单
ccb logs <agent>       # 查看 Agent 日志
ccb doctor             # 项目诊断
ccb doctor --output    # 导出诊断支持包
ccb cancel <job_id>    # 取消任务
ccb config validate    # 验证 ccb.config
ccb queue              # 查看 Agent 队列状态
ccb queue --detail     # 查看详细队列状态（v6.2.x+）
ccb inbox <agent>      # 查看 Agent 收件箱
ccb trace <id>          # 查看任务/消息/回复的完整 lineage
ccb repair ack <agent>  # 确认 Agent 的回复/收件箱进度
ccb repair retry <id>   # 重试失败的任务
ccb clear [agent...]    # 发送 /clear 到 Agent pane
```
