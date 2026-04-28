# CCB 接入 MiniMax (mmx) 完整流程与踩坑记录

> 记录将 MiniMax CLI (`mmx`) 接入 CCB (Claude Code Bridge) v6.0.4 的全过程。

## 一、环境准备

### 1.1 系统环境
- macOS
- Python 3.10+
- CCB v6.0.4 安装在 `~/.local/share/ccb`
- `ccb` 命令已在 PATH (`~/.local/bin/ccb`)

### 1.2 安装 mmx-cli
```bash
npm install -g mmx-cli
mmx auth login --api-key sk-xxxxx
```
验证：
```bash
mmx text chat --message "hello" --output json
```

### 1.3 macOS bash 升级（重要）
**踩坑 #1**：macOS 默认 bash 3.2 不支持 `${var@Q}` 语法，运行 `install.sh` 会报 `bad substitution`。
```bash
brew install bash
```
升级后重新运行 `install.sh`。

---

## 二、项目配置

### 2.1 项目目录结构
当前项目根目录：
```
/Users/zhangtao/Documents/study/claude_code_bridge-6/
├── .ccb/
│   └── ccb.config          # agent 映射配置
├── lib/
│   └── provider_backends/
│       └── mmx/             # 新建的 mmx provider
└── bin/
    └── mmx-daemon           # mmx 交互包装器
```

### 2.2 ccb.config 配置
**踩坑 #2**：ccb 的 agent 映射不是通过 `ccb start` 参数传递的，而是写在 `.ccb/ccb.config` 中。

```
# .ccb/ccb.config
creative:mmx
```
格式：`agent_name:provider_name`

后续扩展为：
```
creative:mmx, claude:claude
```

---

## 三、mmx Provider Backend 创建

在 `lib/provider_backends/mmx/` 下创建以下模块：

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块导出 |
| `session.py` | Session 绑定（`.mmx-session` 文件读写） |
| `comm.py` | PaneLog 通信器（`MmxLogReader`, `MmxCommunicator`） |
| `protocol_runtime.py` | Prompt 包装 + Reply 提取（处理 `CCB_DONE`） |
| `manifest.py` | Provider manifest（能力声明） |
| `launcher.py` | Tmux 启动命令构建 + session payload 写入 |
| `execution.py` | **核心**：`start()` / `poll()` / `resume()` 生命周期 |

### 3.1 mmx-daemon 设计
`bin/mmx-daemon` 是一个运行在 tmux pane 中的 Python 包装器：
- 循环读取 stdin（每行一条消息）
- 调用 `mmx text chat --message ... --output json`
- 打印 API 返回的 reply
- 打印 `CCB_DONE` 标记
- 退出信号：`exit` / `quit` / `shutdown` / EOF

**关键**：daemon 本身不需要处理 req_id，ccb 的 poll 机制通过 pane log 读取输出。

---

## 四、注册到 CCB 系统

需要在 4 个地方注册 mmx：

| 文件 | 注册内容 |
|------|----------|
| `lib/provider_core/runtime_specs.py` | `MMX_RUNTIME_SPEC`, `MMX_CLIENT_SPEC` |
| `lib/provider_core/registry_runtime/builtin_backends.py` | 加入 `OPTIONAL_PROVIDER_NAMES`，在 `build_builtin_backends()` 中实例化 |
| `lib/provider_core/pathing.py` | `PROVIDER_SESSION_FILENAMES['mmx'] = '.mmx-session'` |
| `install.sh` | 链接 `bin/mmx-daemon` |

**踩坑 #3**：如果同时注册其他可选 provider（如 kimi），pathing.py 中也必须注册其 session filename，否则 ccbd 启动报 `unsupported session filename provider: kimi`。

---

## 五、核心踩坑与修复

### 踩坑 #4：源码目录 vs 安装目录不同步

**现象**：修改了源码目录的 `lib/provider_backends/mmx/execution.py`，但 ccb 运行时还是旧代码。

**原因**：ccb 的 Python `sys.path` 指向的是安装目录 `~/.local/share/ccb/lib/`，而不是当前项目目录的 `lib/`。

**解决**：每次修改源码后，同步到安装目录：
```bash
# 创建 sync-to-install.sh 脚本
rsync -av --delete "./lib/" "~/.local/share/ccb/lib/"
rsync -av --delete "./bin/" "~/.local/share/ccb/bin/"
find "~/.local/share/ccb/lib" -type d -name __pycache__ -exec rm -rf {} +
```

---

### 踩坑 #5：`load_session_fn` 签名不匹配

**现象**：
```
TypeError: load_project_session() got an unexpected keyword argument 'agent_name'
```

**原因**：`provider_execution/active_runtime/start.py:44` 调用 `load_session_fn(work_dir, agent_name=...)`，但 mmx 的 `load_project_session(work_dir, instance=None)` 不接受 `agent_name`。

**解决**：添加包装器函数：
```python
def _load_session(work_dir: Path, *, agent_name: str):
    return _load_project_session(work_dir, instance=agent_name)
```
然后在 `start()` 和 `resume()` 中传入 `load_session_fn=_load_session`。

---

### 踩坑 #6：`PaneLogReader` 未配置 pane log 路径

**现象**：job 提交后 mmx-daemon 确实在 pane 中运行并输出了 `CCB_DONE`，但 ccb  poll 一直检测不到完成，agent 永远 `busy`。

**原因**：`MmxLogReader` 继承自 `PaneLogReaderBase`，初始化时只传了 `work_dir`，没有设置 `pane_log_path`。`resolve_log_path()` 返回 `None`，reader 读不到任何内容。

**解决**：在 `start()` 和 `resume()` 中：
```python
log_path = prepared.backend.ensure_pane_log(prepared.pane_id)
reader = MmxLogReader(work_dir=prepared.work_dir)
if log_path:
    reader.set_pane_log_path(log_path)
```

**注意**：pane log 文件实际存储在 `~/.cache/ccb/pane-logs/tmux/pane-{id}.log`，不在项目目录下。

---

### 踩坑 #7：ccb CLI 命令理解

| 错误操作 | 正确操作 |
|----------|----------|
| `ccb start` / `ccb stop` | `ccb`（不带参数启动） / `ccb kill`（停止） |
| `ccb --help start` | `ccb` 的 start/kill 不是子命令，help 直接显示 start 帮助 |

---

## 六、验证流程

### 6.1 启动 ccb
```bash
cd /Users/zhangtao/Documents/study/claude_code_bridge-6
ccb
```
输出应包含：
```
start_status: ok
agents: creative, claude
```

### 6.2 检查 agent 状态
```bash
ccb ps
```
期望：
```
agent: name=creative state=idle provider=mmx queue=0 pane_state=alive
agent: name=claude   state=idle provider=claude queue=0 pane_state=alive
```

### 6.3 发送消息
```bash
ccb ask creative "你好，mmx！"
```
输出：
```
accepted job=job_xxx target=creative
[CCB_ASYNC_SUBMITTED job=xxx target=creative]
```

### 6.4 查看回复
```bash
# 等待 agent 变 idle 后查看 replies 日志
cat .ccb/ccbd/replies/replies.jsonl | jq 'select(.agent_name=="creative" and .terminal_status=="completed")'
```

---

## 七、claude agent 额外踩坑

### 踩坑 #8：claude CLI Bypass Permissions 确认弹窗

**现象**：claude agent 启动后 pane 显示交互式确认：
```
WARNING: Claude Code running in Bypass Permissions mode
❯ 1. No, exit
   2. Yes, I accept
Enter to confirm · Esc to cancel
```
ccb 发送的消息被阻塞，job 最终报 `pane_dead` 失败。

**解决**：首次启动时需要手动向 pane 发送确认：
```bash
tmux -S .ccb/ccbd/tmux.sock send-keys -t %2 -l "2"
tmux -S .ccb/ccbd/tmux.sock send-keys -t %2 Enter
```
（`%2` 是 claude 的 pane id，通过 `ccb ps` 查看）

确认一次后，claude 进入正常工作状态，后续 job 可直接通过 `ccb ask claude` 提交。

---

## 八、最终配置快照

### `.ccb/ccb.config`
```
creative:mmx, claude:claude
```

### 环境变量
```bash
# 可选：调整轮询间隔
export MMX_POLL_INTERVAL=0.1
export MMX_SYNC_TIMEOUT=30
```

### 目录映射
| 目录 | 用途 |
|------|------|
| `~/.local/share/ccb/` | CCB 安装目录（运行时加载） |
| `~/.cache/ccb/pane-logs/` | tmux pane 日志（reader 读取） |
| `.ccb/ccbd/replies/replies.jsonl` | 所有 agent 的回复记录 |
| `.ccb/.mmx-creative-session` | mmx session 元数据 |

---

## 九、总结

| 阶段 | 关键动作 |
|------|----------|
| 环境 | 安装 mmx-cli、升级 bash、认证 API key |
| 配置 | 写 `.ccb/ccb.config`，配置 agent:provider 映射 |
| 开发 | 创建 `lib/provider_backends/mmx/` 全套模块 + `bin/mmx-daemon` |
| 注册 | 在 runtime_specs、builtin_backends、pathing、install.sh 中注册 |
| 调试 | 解决签名不匹配、pane log 路径、源码同步问题 |
| 验证 | `ccb ask creative "..."` → `completed` 状态 + 正确 reply |

**最大教训**：ccb 运行时加载的是安装目录的代码，不是项目目录的源码。修改后务必同步！
