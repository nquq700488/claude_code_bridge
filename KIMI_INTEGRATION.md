# Kimi Provider 接入 CCB 流程与踩坑记录

## 背景

CCB v6 官方文档和 TROUBLESHOOTING 中明确标注"不支持 kimi（Moonshot）"。但 Kimi CLI（v1.37.0）实际上具备完整的非交互模式（`--print`）、session 管理（`--session`/`--continue`）和结构化日志（`context.jsonl`），具备接入 CCB 的条件。

## 核心设计思路

采用 **Pane-backed + Session Snapshot** 模式：
- 在 tmux pane 中运行 `kimi`（交互 TUI 模式）
- 通过 `tmux send-keys` 发送消息
- 通过读取 `~/.kimi/sessions/<work_dir_md5>/<uuid>/context.jsonl` 获取 assistant 回复
- 使用 `_checkpoint` 增量检测回复完成状态

## 需要修改/新增的文件（不涉及代码细节）

### 1. Provider Backend 核心

新增 `lib/provider_backends/kimi/` 目录，包含：
- `__init__.py` — 组装 ProviderBackend
- `manifest.py` — 声明 provider 能力（不支持 resume/permission_auto/stream_watch/subagents）
- `execution.py` — ProviderExecutionAdapter（start + poll）
- `launcher.py` — 生成 `kimi` 启动命令，含二进制路径探测逻辑
- `session.py` — KimiProjectSession（基于 PaneLogProjectSessionBase）
- `comm.py` — KimiLogReader（读取 context.jsonl，提取 assistant 文本）
- `protocol.py` / `protocol_runtime.py` — prompt 包装与回复提取

### 2. Provider 注册（4 处必须改）

| 文件 | 修改内容 |
|------|---------|
| `lib/provider_core/pathing.py` | `PROVIDER_SESSION_FILENAMES` 增加 `kimi: '.kimi-session'` |
| `lib/provider_core/registry_runtime/builtin_backends.py` | `OPTIONAL_PROVIDER_NAMES` 增加 `kimi`，并 import/build backend |
| `lib/provider_core/runtime_specs.py` | 增加 `KIMI_RUNTIME_SPEC` / `KIMI_CLIENT_SPEC`，并加入两个字典 |
| `lib/provider_core/runtime_shared.py` | `_PROVIDER_START_ENV_VARS` 和 `_PROVIDER_DEFAULT_EXECUTABLES` 增加 `kimi` |

### 3. Skills

- 新增 `kimi_skills/` 目录（ask / ping / pend / all-plan）
- 更新 `install.sh`：增加 `install_kimi_skills()` / `uninstall_kimi_skills()`
- Skills 安装目标：`~/.kimi/skills/`

### 4. 文档更新

- `README.md` — 标题增加 Kimi
- `TROUBLESHOOTING.md` — 把 kimi 从"不支持"改为"支持"

## 部署踩坑记录

### 坑 1：修改的是源码，但 ccb 跑的是已安装版本

**现象**：改完代码启动仍报 "unsupported session filename provider: kimi"

**原因**：`ccb` 脚本加载的是 `~/.local/share/ccb/lib/`，而不是项目源码目录 `lib/`

**解决**：必须把修改同步到 `~/.local/share/ccb/lib/` 下的对应文件

### 坑 2：ccbd daemon 缓存已加载的 Python 模块

**现象**：文件已同步，清除了 `__pycache__`，仍然报同样的错

**原因**：`ccbd` 是一个长期运行的 Python 进程，import 的模块驻留在内存中

**解决**：`ccb kill` 彻底杀掉 daemon，再重新启动

### 坑 3：kimi 不在 PATH 中，`shutil.which('kimi')` 返回 None

**现象**：ccb 启动时报 "kimi executable not found in PATH"

**原因**：CCB 在启动 pane 前会用 `shutil.which` 验证 provider 可执行文件是否存在。Kimi CLI 默认安装在 VS Code 扩展目录，不在 PATH 中

**解决**：创建符号链接到 PATH 目录：
```bash
ln -s "$HOME/Library/Application Support/Code/User/globalStorage/...
  moonshot-ai.kimi-code/bin/kimi/kimi" "$HOME/.local/bin/kimi"
```

### 坑 4：`runtime_specs.py` 漏注册 kimi

**现象**：pathing.py 和 builtin_backends.py 都改了，仍然报 "unsupported session filename provider"

**原因**：`runtime_specs.py` 中的 `RUNTIME_SPECS_BY_PROVIDER` 和 `CLIENT_SPECS_BY_PROVIDER` 也需要增加 kimi 条目

**解决**：补注册 `KIMI_RUNTIME_SPEC` 和 `KIMI_CLIENT_SPEC`

### 坑 5：旧的 `.ccb` session 文件与新配置冲突

**现象**：改了 `ccb.config` 加入 kimi 后，启动时只有部分 agent 起来，或者 pane ID 错乱

**原因**：`.ccb/` 目录下残留了之前配置的 `.claude-*-session`、`.codex-*-session` 等历史文件

**解决**：重建 `.ccb` 状态：
```bash
# 保存配置
cp .ccb/ccb.config /tmp/
rm -rf .ccb
mkdir -p .ccb
mv /tmp/ccb.config .ccb/
ccb
```

## CCB 配置

### ccb.config 格式

```text
cmd, claude:claude, codex:codex, kimi:kimi, creative:mmx
```

规则：
- `agent_name:provider` 定义一个 agent
- `cmd` 添加 shell pane
- `;` 水平分割，`,` 垂直分割
- 需要隔离环境加 `(worktree)`，如 `qa:gemini(worktree)`

### kimi 启动命令

launcher 生成的实际命令示例：
```bash
export KIMI_RUNTIME_DIR=/.../agents/kimi/provider-runtime/kimi; /Users/zhangtao/.local/bin/kimi
```

### Session 文件位置

- CCB 创建的 session 文件：`.ccb/.kimi-<agent_name>-session`
- Kimi CLI 自身的 session 日志：`~/.kimi/sessions/<work_dir_md5>/<uuid>/context.jsonl`
- work_dir hash 算法：`md5(绝对路径)`，小写 hex

## 验证方式

### 1. 确认 pane 启动
```bash
tmux -S .ccb/ccbd/tmux.sock list-panes -a -F '#{pane_id} #{pane_title}'
```
期望看到 `%3 kimi` 类似的输出

### 2. 确认进程存活
```bash
ps aux | grep "Kimi Code"
```

### 3. 测试消息收发
```bash
# 向 kimi 发送消息
tmux -S .ccb/ccbd/tmux.sock send-keys -t %3 "hello" Enter

# 查看 context.jsonl 确认回复已生成
~/.kimi/sessions/<md5>/<uuid>/context.jsonl
```

### 4. 通过 CCB ask 跨 agent 通信
```bash
# 让 kimi 向 claude 打招呼（kimi 会调用 Shell 执行 ccb ask）
tmux -S .ccb/ccbd/tmux.sock send-keys -t %3 \
  'ccb ask claude "你好 claude，我是 kimi"' Enter
```

## 已知限制

1. **不支持 resume**：Kimi 的 session 恢复机制与 CCB 的持久化模型不匹配，manifest 中声明 `supports_resume=False`
2. **Approval 模式**：Kimi CLI 默认需要手动批准 Shell 命令（非 yolo 模式），执行 `ccb ask` 等命令时会弹出 approval 提示，需要发送 `y` 批准
3. **Session ID 获取**：`--print` 模式下 session_id 只输出到 stderr，CCB 采用 work_dir hash + 扫描最新 uuid 目录的方式定位 session
4. **工具调用可见性**：Kimi 在交互模式下会自动执行工具，CCB 只能通过 context.jsonl 观测结果，无法干预每一步

## 总结

接入一个新的 provider 到 CCB，表面上是实现几个 adapter 接口，实际部署时的主要工作量在于：
1. 理解 CCB 的三层注册体系（backend + pathing + runtime_specs）
2. 处理已安装版本与源码的同步问题
3. 处理 daemon 进程缓存和旧 session 状态
4. 处理 provider 二进制不在 PATH 的问题

Kimi 由于提供了结构化的 `context.jsonl` 和标准的 tmux TUI 交互，整体接入难度与 OpenCode/Droid 相当，属于中等复杂度。
