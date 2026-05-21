# CCB 项目代码审查报告

**审查日期**: 2026-05-21
**补丁范围**: Socket + FIFO 双轨通信 / `pend --timeout` / watch 最终探测优化 / ACK 修复

---

## 结论总览

| 严重级别 | 数量 | 关键发现 |
|----------|------|----------|
| 🔴 CRITICAL | 1 | socket handler 多线程调用 `process_request` 无锁，并发写 history_file 会损坏 JSONL，并发 `codex_session.send()` 会导致 tmux 输入交错乱码 |
| 🟠 HIGH | 2 | (1) 信号处理函数中 `binding_tracker.stop()` 与 `finally` 块双重停止； (2) watch_runtime.py fresh probe 路径中 terminal+events 场景静默丢 yield |
| 🟡 MEDIUM | 2 | (1) `_server_sock` 在 stop()/serve() 线程间无同步，细竞态下 handler 线程崩溃； (2) socket handler 线程数无上限 |
| 🔵 LOW | 3 | (1) 5s ACK timeout 增加成功路径延迟； (2) `UnicodeEncodeError` 未捕获不会触发 FIFO fallback； (3) socket 文件权限受 umask 控制 |

**总体评分**: 通过但建议合并前修复 CRITICAL 项

---

## 🔴 CRITICAL

### 1. `process_request` 多线程并发调用无锁

**文件**: `socket_server.py:100-131` → `service.py:99-100` → `runtime_io.py:27-48`
**严重性**: CRITICAL
**评分**: 1/10

**问题**:
`BridgeSocketServer._handle_connection` 为每个连接创建新线程，直接调用 `self._process_request(payload)`。与此同时，`DualBridge.run()` 的主循环也通过 `read_request()` 从 FIFO 读取并调用相同的 `process_request()`。

`process_request()` 中对 `state.codex_session.send(content)` 的调用（`session.py:13-20`）实际调用 tmux 的 `send_text_to_pane`，tmux 本身会将文本直接注入 pane。两个线程同时调用时，Codex CLI 收到的是**交错字符**，两条消息全部乱码：

```
Thread A: send "list files"  → tmux gets "l" from A, "s" from B, "i" from A ...
Thread B: send "show status" → 结果: "lshoow stw atlius st"
```

同时 `append_history()` 写入 JSONL 文件的逻辑分两步（`json.dump` + `write('\n')`），并发写入会产生**损坏的 JSONL**：

```json
{"role": "claude", ...}{"role": "codex", ...}
\n
→ 两条记录在同一行，JSON 解析器只能读到第一条
```

**建议修复**:
在 `BridgeSocketServer` 内部持有一个 `threading.Lock`，所有 handler 线程在调用 `process_request` 前获取锁。短期方案：

```python
class BridgeSocketServer:
    def __init__(self, ...):
        self._request_lock = threading.Lock()

    def _handle_connection(self, conn):
        ...
        try:
            with self._request_lock:
                self._process_request(payload)
            conn.sendall(b'{"status":"ok"}\n')
        except Exception as exc:
            ...
```

长期方案可考虑将 socket 请求入队、由主循环统一出队处理，消除额外线程。

---

## 🟠 HIGH

### 2. 信号处理函数中 `binding_tracker.stop()` 与 `finally` 块双重停止

**文件**: `service.py:57-60`, `service.py:89-91`
**严重性**: HIGH
**评分**: 4/10

**问题**:
`_handle_signal` 中调用了 `self.binding_tracker.stop()`，而 `run()` 的 `finally` 块中也调用了 `self.binding_tracker.stop()`。如果 `stop()` 非幂等（例如尝试 `join` 已 join 的线程），会导致异常，`_stop_socket_server()` 可能不会执行。

**建议修复**:
信号处理函数只设标志位，不执行清理逻辑。清理统一放在 `finally` 块：

```python
def _handle_signal(self, signum, _):
    self._running = False
    # 移除: self.binding_tracker.stop()
    self._log_console(f'Received signal {signum}, exiting...')
```

### 3. watch_runtime.py fresh probe 中 terminal+events 静默丢 yield

**文件**: `watch_runtime.py:110-118`
**严重性**: HIGH
**评分**: 4/10

**问题**:

```python
if fresh_batch.terminal:
    if not fresh_batch.events:
        yield fresh_batch
    return  # ← 如果 terminal=True 且 events 非空，直接 return 不 yield
```

当 fresh probe 返回一个 `terminal=True` 且 `events` 非空的 batch 时，函数 `return` 但不 `yield`，调用方得到空生成器。而 `_persisted_terminal_batch` 已经 else 过了（没有 fallback），所以调用方既没有数据也没有错误，静默无输出。

**说明**: 此逻辑假设 events 已通过正常 watch 循环 yield 过，fresh probe 仅用于检测 terminal 状态。但这个假设没有注释说明，且当 events 通过 fresh probe 首次到达时（例如 daemon 重启后），events 就丢失了。

**建议修复**:

```python
if fresh_batch.terminal:
    yield fresh_batch  # 始终 yield，由调用方决定是否丢弃 events
    return
```

或者补上显式注释说明设计意图。

---

## 🟡 MEDIUM

### 4. `_server_sock` 在 stop()/serve() 线程间无同步

**文件**: `socket_server.py:68-83`, `socket_server.py:86-98`
**严重性**: MEDIUM
**评分**: 5/10

**问题**:
`stop()` 设置 `self._server_sock = None` 前关闭了 socket，而 `_serve()` 线程在每个循环迭代中读取 `self._server_sock`。竞态窗口：

1. `_serve()` 检查 `self._server_sock is not None` → True
2. `stop()` 设置 `self._server_sock = None`
3. `_serve()` 调用 `self._server_sock.settimeout(1.0)` → **AttributeError** (NoneType)

由于 `AttributeError` 不在 `except (socket.timeout, OSError)` 的捕获范围，handler 线程会静默崩溃，socket 文件可能不会被清理。

**建议修复**:
使用局部变量持有 socket 引用，或加锁保护：

```python
def _serve(self) -> None:
    sock = self._server_sock  # 局部引用
    while self._running and sock is not None:
        try:
            sock.settimeout(1.0)
            conn, _ = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        handler = threading.Thread(target=self._handle_connection, args=(conn,), daemon=True)
        handler.start()
```

### 5. socket handler 线程数无上限

**文件**: `socket_server.py:96-98`
**严重性**: MEDIUM
**评分**: 5/10

**问题**:
每个客户端连接都创建一个新的 daemon thread，没有上限控制。虽然 `listen(128)` 做了 backlog 限制，但 handler 线程在 `recv()` 等待数据时可能阻塞最多 10 秒。快速建立大量连接（~100+）会产生对应数量的线程。

**建议修复**:
使用 `threading.BoundedSemaphore` 限制并发数，或使用线程池。最简单的短期修复：

```python
class BridgeSocketServer:
    def __init__(self, ...):
        self._handler_semaphore = threading.BoundedSemaphore(16)

    def _handle_connection(self, conn):
        with self._handler_semaphore:
            ...  # 原有处理逻辑
```

---

## 🔵 LOW

### 6. 5 秒 ACK timeout 增加成功路径延迟

**文件**: `asking.py:49-63`
**严重性**: LOW
**评分**: 6/10

**问题**:
`_SOCKET_TIMEOUT_S = 5.0` 用于 `connect` 和 `recv`。在 socket 路径成功的常见情况下，这意味着 `send_message()` 会阻塞至少一个 RTT（读取 ACK）。如果网络栈或进程调度导致 ACK 延迟，每次消息发送都会等待完整的 5 秒才开始 FIFO fallback。

**建议修复**:
考虑降低 ACK 的超时（例如 1-2 秒），或者使用独立的超时：

```python
sock.settimeout(_SOCKET_CONNECT_TIMEOUT)  # 连接超时 5s
sock.sendall(payload_bytes)
sock.settimeout(_SOCKET_ACK_TIMEOUT)      # ACK 超时 1s
ack = sock.recv(1024)
```

### 7. `_try_send_via_socket` 未捕获 `UnicodeEncodeError`

**文件**: `asking.py:48-52`
**严重性**: LOW
**评分**: 7/10

**问题**:
`payload.encode("utf-8")` 在 CPython 中基本不会失败（UTF-8 可以编码所有 Unicode 码位），但如果 payload 包含代理对代理（surrogate）等异常字符，会引发 `UnicodeEncodeError`。该异常不在 `except` 列表中，`fallback to FIFO` 不会触发。

**建议修复**:
functools 或将 `payload.encode("utf-8", errors="replace")` 使用 errors 参数，或在 try 块外编码。

### 8. 空 ACK / 无效 JSON 被直接视为成功

**文件**: `asking.py:55-63`
**严重性**: LOW
**评分**: 7/10

**问题**:
当 `recv` 收到有效载荷但 `json.loads` 解析失败时（例如服务端意外返回非 JSON），代码 fallthrough 到 `return True`（treat as success）。这意味着即便服务端发了错误响应，只要不是合法 JSON `{"status":"error"}`，都被认为是成功交付。消息不会被 FIFO 重试。

**建议修复**:

```python
try:
    ack_data = json.loads(ack.decode())
    return ack_data.get("status") == "ok"
except (json.JSONDecodeError, UnicodeDecodeError):
    return False  # 无效 ACK 触发 FIFO fallback
```

---

## ✅ 设计确认无问题

以下路径经审查确认安全：

### 向后兼容性

- `communicator_state.py:96`: `session_info.get("bridge_socket", "")` 的 `or` 回退正确处理空字符串/None → `runtime_dir / "bridge.sock"` ✓
- `loading.py:24`: 新增 `CODEX_BRIDGE_SOCKET` 环境变量默认空字符串，旧 session 无此 env var 时静默回退 ✓
- `asking.py:41-43`: `comm.bridge_socket` 为 None 时直接 `return False` → FIFO fallback ✓
- `validate_bridge_bootstrap():69`: `not socket.exists() and not fifo.exists()` 双轨检查 ✓

### Socket 文件清理

- `start()`: bind 前 unlink 旧 socket ✓
- `stop()`: close socket + unlink 文件 ✓
- `run()` finally: 保证 `_stop_socket_server()` 执行 ✓

### ACK 协议修复

- `asking.py:58-59`: `ack_data.get("status") == "ok"` 正确检查服务端状态字段 ✓
- `socket_server.py:123-127`: 正常路径发送 `{"status":"ok"}\n`，异常路径发送 `{"status":"error","reason":"..."}\n` ✓

### Health check

- `health.py:33-36`: socket 或 FIFO 存在均认为健康 ✓

### `pend --timeout`

- `commands.py:29-33`: 正数校验 + 仅 watch 模式允许 ✓
- `watch.py:26-30`: `command.timeout` → `_resolve_timeout_seconds()` 正确覆盖 ✓
- `handlers_mailbox.py:52`: `timeout_s` → `timeout` 字段名适配 ✓

---

## 建议修复优先级

1. **立即** (合并前): 修复 CRITICAL 项#1 — 为 `process_request` 加锁
2. **合并前**: 修复 HIGH 项#2 (信号双重 stop)、项#3 (fresh probe yield)
3. **合并后 1-2 轮迭代**: MEDIUM 项#4 (`_server_sock` 竞态)、项#5 (线程上限)
4. **按需**: LOW 项#6-8 为优化建议

---

*审查完毕，共计审查 14 个文件，发现 1 个 CRITICAL、2 个 HIGH、2 个 MEDIUM、3 个 LOW 问题。*
