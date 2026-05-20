# CCB 跨设备安装指南 (Cross-Device Installation Guide)

> 版本：适用于 CCB v6.0.x | 最后更新：2026-05

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
11. [架构说明](#架构说明)

---

## CCB 简介

**CCB (Claude Code Bridge)** 是一个多 AI Agent CLI 协作平台。它基于 **tmux** 终端多路复用器，让你在一个终端窗口中同时运行和管理多个 AI Agent（Claude、Codex、Gemini、OpenCode、Kimi、Droid、MMX），并让它们通过 `/ask`、`/ping`、`/pend` 命令互相通信和委派任务。

核心能力：
- 一键启停多个 AI CLI Agent
- Agent 间异步通信（邮箱系统）
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
git clone https://github.com/bfly123/claude_codex_bridge.git
cd claude_codex_bridge
```

### 2. 执行安装

```bash
./install.sh install
```

> **Windows 用户**：`install.ps1` 仅支持基础安装（不含 tmux 主题、`mmx-daemon`、Codex/Droid/Kimi skills），**推荐在 WSL 中使用 `install.sh` 获得完整功能**。

### 安装脚本会做什么

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

5. **配置 PATH**
   - 自动将 `~/.local/bin` 添加到 shell 配置文件（`.zshrc` / `.bashrc` / `.bash_profile`）

6. **安装 Skills**
   - Claude skills → `~/.claude/skills/`（ask, ping, pend, review, all-plan, file-op, autonew, continue, tp, tr）
   - Codex skills → `~/.codex/skills/`
   - Droid/Factory skills → `~/.factory/skills/`（若检测到 droid CLI）
   - Kimi skills → `~/.kimi/skills/`（若检测到 kimi CLI）

7. **注入 CCB 配置到 CLAUDE.md**
   - 在 `~/.claude/CLAUDE.md` 中写入 CCB 协作规则
   - 包括角色分配表、Peer Review 框架、Async Guardrail

8. **配置权限**
   - 在 `~/.claude/settings.json` 中添加 `Bash(ccb ask/ping/pend *)` 权限

9. **配置 tmux**
   - 追加 CCB 专用 tmux 配置到 `~/.tmux.conf`（或 `~/.tmux.conf.local`）
   - 包括 Tokyo Night 主题、vim 风格按键、鼠标支持、剪贴板集成

10. **注册 Droid MCP 委托（可选）**
    - 若检测到 `droid` CLI，自动注册 `ccb-delegation` MCP 工具
    - 使 Droid 能通过 CCB 向其他 Agent 发送 `/ask` 任务

### 安装目录结构

```
~/.local/
├── bin/
│   ├── ccb                 # 主入口
│   ├── ask                 # Agent 通信
│   ├── autonew             # 自动新建会话
│   ├── ctx-transfer        # 上下文传递
│   ├── mmx-daemon          # MMX 守护进程
│   ├── ccb-status.sh       # 状态栏脚本
│   ├── ccb-border.sh       # 边框颜色脚本
│   ├── ccb-git.sh          # Git 状态脚本
│   ├── ccb-tmux-on.sh      # 主题启用
│   └── ccb-tmux-off.sh     # 主题关闭
└── share/
    └── ccb/
        ├── ccb             # Python 入口
        ├── lib/            # Python 核心库
        ├── config/         # 配置模板
        ├── claude_skills/  # Claude agent 技能
        ├── codex_skills/   # Codex agent 技能
        ├── droid_skills/   # Droid agent 技能
        ├── kimi_skills/    # Kimi agent 技能
        ├── mcp/            # MCP 委托服务
        ├── docs/           # 架构文档
        └── VERSION         # 版本号
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

### ccb.config 语法

CCB 的行为由项目级 `.ccb/ccb.config` 文件控制。该文件不会被安装脚本自动创建，需要手动维护。

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

#### 完整配置示例

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

# 全部 Provider
cmd, agent1:codex; agent2:codex, agent3:claude; agent4:kimi
```

---

## 更新与升级

### 自动更新

```bash
ccb update              # 更新到最新稳定版
ccb update 6            # 更新到 v6.x.x 最高版本
ccb update 6.0.29       # 更新到指定版本
```

### Source Dev 模式更新

如果你是从 Git Clone 安装的（source dev 模式）：

```bash
cd /path/to/claude_codex_bridge
git pull
./install.sh install     # 重新安装以更新 links 和 skills
```

> **Source dev 模式特性**：安装目录通过 **符号链接（symlink）** 指向原始 git checkout，修改代码后立即生效，无需重新安装。

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
cd /path/to/claude_codex_bridge
./install.sh uninstall
```

卸载会移除：
- `~/.local/share/ccb` — 安装目录
- `~/.local/bin/ccb`, `ask`, `autonew`, `ctx-transfer`, `mmx-daemon` — 主可执行文件
- `~/.local/bin/ccb-status.sh`, `ccb-border.sh`, `ccb-git.sh`, `ccb-tmux-on.sh`, `ccb-tmux-off.sh` — tmux 辅助脚本
- `~/.claude/CLAUDE.md` 中的 CCB 配置块
- `~/.claude/settings.json` 中的 CCB 权限
- `~/.tmux.conf` / `~/.tmux.conf.local` 中的 CCB tmux 配置
- `~/.claude/skills/` 中的 CCB skills
- `~/.codex/skills/` 中的 CCB skills
- `~/.factory/skills/` 中的 CCB skills
- `~/.kimi/skills/` 中的 CCB skills

不会移除：
- Python、tmux 等系统依赖
- 项目目录下的 `.ccb/` 配置

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
which claude    # 若使用 Claude agent
which codex     # 若使用 Codex agent
which gemini    # 若使用 Gemini agent
```

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

### Q10: PCI 校验失败

```bash
# 清除 Python 编译缓存
find ~/.local/share/ccb -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find ~/.local/share/ccb -name "*.pyc" -delete 2>/dev/null
```

---

## 配置文件速查

| 文件 | 位置 | 作用 |
|------|------|------|
| `ccb.config` | `<project>/.ccb/ccb.config` | 项目 Agent 团队布局和 API 配置 |
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
│       └── provider-state/ # Provider 隔离状态
└── history/                # 会话历史归档
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
  → 原始调用方通过 /pend reviewer 获取结果
```

### Provider 隔离

每个 Agent 的 Provider 状态完全隔离：
- Claude agent 的 `~/.claude/` 等价状态存储在 `.ccb/agents/<name>/provider-state/claude/home/`
- Codex agent 的 `~/.codex/` 等价状态存储在 `.ccb/agents/<name>/provider-state/codex/home/`
- 互不污染，全局 Provider 配置不会被修改

---

## 快速命令参考

```bash
# 项目管理
ccb                    # 启动 Agent 团队
ccb -s                 # 安全启动（保留权限策略）
ccb -n                 # 重建运行时（保留 ccb.config）
ccb kill               # 停止项目运行时
ccb kill -f            # 强制清理

# 安装/更新
./install.sh install   # 安装或更新
./install.sh uninstall # 卸载
ccb update             # 更新到最新版
ccb reinstall          # 重新安装

# Agent 间通信（在 Agent 内部使用）
/ask <agent> <message> # 向指定 Agent 委派任务
/ping <agent|ccbd>     # 检查 Agent 或控制平面健康
/pend <agent|job_id>   # 查看 Agent 回复

# 高级诊断
ccb ps                 # 运行时清单
ccb logs <agent>       # 查看 Agent 日志
ccb doctor             # 项目诊断
ccb doctor --output    # 导出诊断支持包
ccb watch <agent>      # 实时回复流
ccb cancel <job_id>    # 取消任务
ccb config validate    # 验证 ccb.config
```
