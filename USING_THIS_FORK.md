# 使用此 Fork 版本的 CCB

> **核心原则**：系统里只保留这一个 CCB 安装。它是官方 CCB（v8.0.16）的 Fork，额外添加了 **MiniMax (mmx)** provider 支持，并对 **Kimi** provider 做了增强（更健壮的 CLI 可执行文件查找 + 新 session 格式兼容）。官方版本已收录 Kimi、Gemini、Codex、Claude 等 15 个 CLI 家族。

---

## 1. 这个 Fork 与官方版本的区别

| 特性 | 官方 CCB (v8.0.16) | 此 Fork |
|------|---------------------|---------|
| Claude | ✅ | ✅ |
| Codex (OpenAI) | ✅ | ✅ |
| Gemini | ✅ | ✅ |
| Kimi | ✅ | ✅（增强版） |
| **MiniMax (mmx)** | ❌ | ✅ |
| MiMo / Qwen / Cursor / Copilot / Crush / Kiro / Pi / Z.ai / OpenCode / Antigravity / Droid | ✅ | ✅ |

- **安装目录**：`~/.local/share/ccb`
- **源码位置**：`/Users/zhangtao/Documents/study/claude_code_bridge`

---

## 2. 在其他项目中使用

### 2.1 前提条件

确保 `~/.local/bin` 在你的 `PATH` 中：

```bash
# 检查
which ccb
# 预期输出: /Users/zhangtao/.local/bin/ccb

# 如果不在 PATH，添加到 ~/.zshrc 或 ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
```

### 2.2 在项目目录中启动 CCB

进入任意项目目录，创建 CCB 配置并启动：

```bash
cd /path/to/your-project

# 创建配置目录
mkdir -p .ccb

# 编辑配置（示例：creative 用 mmx，reviewer 用 claude）
cat > .ccb/ccb.config << 'EOF'
creative:mmx
reviewer:claude
EOF

# 启动 CCB（会自动读取 .ccb/ccb.config）
ccb
```

### 2.3 使用项目脚本快捷操作（推荐）

当前项目 `.ccb/` 目录下提供了一套脚本模板，可以一键安装到其他项目中：

```bash
# 进入当前项目（脚本模板所在位置）
cd /Users/zhangtao/Documents/study/claude_code_bridge

# 安装脚本到目标项目（复制 start.sh / stop.sh / restart.sh）
./.ccb/install.sh /path/to/your-project --links
```

安装后，在目标项目中使用：

```bash
cd /path/to/your-project

# 启动（如果已在运行则提示，不会重复启动）
./ccb-start
# 或 ./.ccb/start.sh

# 停止
./ccb-stop
# 或 ./.ccb/stop.sh

# 强制停止（清理后停止）
./ccb-stop -f

# 重启
./ccb-restart

# 强制清理后重启
./ccb-restart -f
```

| 脚本 | 参数 | 说明 |
|------|------|------|
| `start.sh` | `-s` / `--safe` | 安全模式启动 |
| `start.sh` | `-n` / `--new` | 重建后启动 |
| `stop.sh` | `-f` / `--force` | 强制清理后停止 |
| `restart.sh` | `-f` | 强制清理后重启 |
| `restart.sh` | `-s` | 安全模式重启 |
| `restart.sh` | `-n` | 重建后重启 |

**脚本特点**：
- 自动推断项目根目录（不需要手动指定 `--project`）
- `start.sh` 会检查 ccb 是否已在运行，避免重复启动
- 彩色输出，状态一目了然

### 2.4 使用 `ccb ask` 向指定 agent 发送消息

```bash
# 向 creative agent（mmx）发送消息
ccb ask creative "写一个 Python 快速排序"

# 向 reviewer agent（claude）发送消息
ccb ask reviewer "review 这段代码"

# 查看所有 agent 状态
ccb status
```

### 2.5 支持的 Provider 简写

在 `.ccb/ccb.config` 中使用（完整列表见上游 README）：

| 配置写法 | Provider | 说明 |
|----------|----------|------|
| `agent:mmx` | MiniMax | Fork 独有，纯文本对话，无本地 tool calling |
| `agent:kimi` | Kimi | Fork 增强版（CLI 查找更健壮 + session 兼容），支持 skills |
| `agent:claude` | Claude | 支持 skills |
| `agent:codex` | Codex (OpenAI) | 支持 skills |
| `agent:gemini` | Gemini | 支持 skills |
| `agent:agy` | Antigravity | 支持 skills |
| 更多... | Qwen/Cursor/Copilot/Kiro/Pi/Z.ai/Droid 等 | 上游原生支持 |

### 2.6 各 Agent 使用规范与注意事项

不同 provider 的能力差异很大，**不能按同一个方式使用**。以下是各 agent 的适用场景和限制。

#### `creative:mmx` — MiniMax（纯文本对话）

**能力**：
- ✅ 代码生成、文本分析、头脑风暴、翻译、解释概念
- ✅ 长文本理解和生成
- ❌ **不能读写文件**（没有本地文件系统访问能力）
- ❌ **不能执行命令**（没有 shell 工具）
- ❌ **不支持 skills**（如 file-op、ask 等）

**使用规范**：
```bash
# ✅ 正确：把代码直接贴在 prompt 里
ccb ask creative "帮我优化这段代码：\n\ndef bubble_sort(arr):\n    ..."

# ✅ 正确：纯文本任务
ccb ask creative "解释快速排序的时间复杂度"

# ❌ 错误：期望它读取文件
ccb ask creative "帮我看看 src/main.py 有什么问题"
# ↑ mmx 看不到文件系统，它只会根据文件名瞎猜

# ❌ 错误：期望它执行命令
ccb ask creative "运行测试并告诉我结果"
# ↑ mmx 没有执行权限
```

**能否让 mmx 审查项目代码？**

**不能直接审查**。mmx 没有文件系统访问能力，以下命令**不会生效**：
```bash
# ❌ mmx 看不到 src/main.py 的内容
ccb ask creative "review src/main.py"
```

** workaround（手动粘贴，适合小文件）**：
```bash
# 手动读取后粘贴
cat src/main.py | pbcopy
ccb ask creative "review 这段代码：[粘贴内容]"
```

**推荐做法**：代码审查交给 claude：
```bash
# ✅ claude 会自动读取文件并分析
ccb ask claude "review src/main.py"
```

**最佳实践**：
- 需要 mmx 处理文件内容时，**先用 cat 读取，再粘贴到 prompt**（仅限小文件）
- 适合作为"第二意见"，和 claude 互补
- **不要试图改造 mmx-daemon 加文件读取** — mmx API 不支持 tool calling，且大文件容易超限

---

#### `reviewer:claude` — Claude（全功能）

**能力**：
- ✅ 支持完整的 skills 系统（file-op, ask, ping, all-plan 等）
- ✅ 可以读写文件、执行命令
- ✅ 适合代码审查、重构、复杂任务

**使用规范**：
```bash
# ✅ 正确：让它读取并分析文件
ccb ask reviewer "review src/main.py"
# ↑ claude 会调用 file-op skill 读取文件

# ✅ 正确：复杂任务
ccb ask reviewer "重构这个模块，添加类型注解和单测"

# ✅ 正确：执行命令
ccb ask reviewer "运行 pytest 并分析失败用例"
```

**注意事项**：
- **首次启动需要手动确认**：Claude CLI 第一次运行时可能会弹出 "Bypass Permissions" 确认，需要在 tmux pane 中按回车确认，或预先在 `~/.claude/settings.json` 中配置权限
- **worktree 模式**：如果多个 agent 需要隔离，可在配置中使用 `agent:claude(worktree)`

---

#### `agent:kimi` — Kimi

**能力**：
- ✅ 支持 skills（ask, ping, pend, all-plan 等）
- ✅ 可以读写文件
- ⚠️ 需要 `kimi` CLI 已安装并登录

**使用规范**：
```bash
# ✅ 正确：文件操作类任务
ccb ask kimi "分析这个日志文件"

# ✅ 正确：中文对话场景（Kimi 中文表现较好）
ccb ask kimi "用中文解释这段代码的逻辑"
```

**注意事项**：
- 需要 `kimi` CLI：`npm install -g kimi-cli` 或官方安装方式
- 需要登录：`kimi auth login`

---

#### `agent:codex` — Codex (OpenAI)

**能力**：
- ✅ 支持 skills
- ✅ 可以读写文件、执行命令
- ⚠️ 需要 OpenAI API Key

**使用规范**：
```bash
# ✅ 正确：代码生成
ccb ask codex "写一个处理 CSV 的 Python 脚本"

# ✅ 正确：OpenAI 模型相关任务
ccb ask codex "用 GPT-4 分析这段代码的复杂度"
```

**注意事项**：
- 需要配置 `OPENAI_API_KEY` 环境变量
- Codex CLI 行为可能与 Claude CLI 略有不同

---

### 2.7 多 Agent 协作最佳实践

推荐配置模式（`creative:mmx, claude:claude`）：

```bash
# 场景 1：先用 mmx 生成草稿，再用 claude 完善
ccb ask creative "写一个 Python 装饰器，用于缓存函数结果"
# 拿到 mmx 的回复后...
ccb ask claude "基于这段代码添加类型注解、错误处理和单元测试：\n[paste code]"

# 场景 2：claude 审查 mmx 的输出
ccb ask creative "解释 REST API 设计原则"
# 然后...
ccb ask claude "review 这段关于 REST API 的解释，补充缺失的部分"

# 场景 3：mmx 做头脑风暴，claude 做实现
ccb ask creative "设计一个任务队列系统，列出关键模块"
# 然后...
ccb ask claude "根据以下设计实现核心模块：\n[paste design]"
```

**原则**：
- **mmx** 负责"想"和"写"（纯文本生成）
- **claude** 负责"做"和"改"（文件操作、执行、审查）
- **不要**让 mmx 做需要文件系统的任务
- **不要**让 mmx 和 claude 同时操作同一个文件（避免冲突）

---

## 3. 安装与更新

### 3.1 首次安装

```bash
cd /Users/zhangtao/Documents/study/claude_code_bridge
bash install.sh install
```

### 3.2 修改代码后的同步

修改源码后同步到安装目录：

```bash
cd /Users/zhangtao/Documents/study/claude_code_bridge
bash install.sh install
```

`install.sh install` 会重新创建 symlink 和刷新 skills 安装。

### 3.3 完全重装

```bash
cd /Users/zhangtao/Documents/study/claude_code_bridge
bash install.sh uninstall
CODEX_INSTALL_PREFIX="$HOME/.local/share/ccb" bash install.sh install
```

---

## 4. ⚠️ 重要注意事项

### ❌ 绝对不要运行 `ccb update`

`ccb update` 会从官方 release 渠道下载最新版本，**这会覆盖掉此 Fork 中添加的 mmx provider 和 Kimi 增强**，导致这些功能失效。

如果看到以下提示，**忽略它**：

```
📦 Release update available: v6.0.7
   Run: ccb update
```

**正确做法**：
- 如果需要官方新功能，先 `git pull` 或 `git merge` 合并官方代码到此 Fork
- 然后重新运行 `bash install.sh install`

### 其他注意事项

1. **macOS 默认 Bash 不兼容**：macOS 自带的 bash 3.2 不支持 `${var@Q}` 语法，必须先安装新版 bash：
   ```bash
   brew install bash
   ```

2. **mmx 没有 skills 支持**：MiniMax 是纯文本对话 API，不能像 claude/codex 那样使用本地 tool calling 和 skills。

3. **mmx 需要 `mmx` CLI 已安装**：
   ```bash
   npm install -g mmx-cli
   mmx --version
   ```

4. **各项目的 session 文件**：
   - `.mmx-session` — mmx 的 session 绑定
   - `.kimi-session` — kimi 的 session 绑定
   - `.claude-session` — claude 的 session 绑定
   这些文件存在各自项目目录中，删除安装目录不会影响它们。

5. **tmux 是必需后端**：ccb 依赖 tmux 管理 agent pane，确保已安装：
   ```bash
   tmux -V
   ```

---

## 5. 故障排查

### Q: `ccb ask creative "hello"` 没有返回？

检查步骤：
```bash
# 1. 确认 ccb 用的是此 Fork
which ccb          # 应为 ~/.local/bin/ccb
ccb --version      # Install path 应为 ~/.local/share/ccb

# 2. 确认 mmx-daemon 存在
ls -la ~/.local/bin/mmx-daemon

# 3. 确认 tmux 中有 creative pane
tmux ls
ccb status

# 4. 直接测试 mmx API
mmx text chat --message "hello" --output json
```

### Q: 提示 `kimi` 或 `mmx` provider 未找到？

说明安装被官方版本覆盖了。重新安装此 Fork：
```bash
cd /Users/zhangtao/Documents/study/claude_code_bridge
bash install.sh uninstall
CODEX_INSTALL_PREFIX="$HOME/.local/share/ccb" bash install.sh install
```

### Q: 修改了代码但没生效？

```bash
# 同步到安装目录
bash sync-to-install.sh

# 重启 ccb
ccb stop
ccb
```

---

## 6. 相关文档

- [MMX 集成指南](./MMX_INTEGRATION_GUIDE.md) — MiniMax provider 的详细集成过程
- [KIMI 集成说明](./KIMI_INTEGRATION.md) — Kimi provider 的集成说明
- [INSTRUCTION_EXECUTION_SPEC.md](./INSTRUCTION_EXECUTION_SPEC.md) — 指令执行规范
