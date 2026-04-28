## OpenCode 完成契约

本文档定义 `ccb_source` 中 `opencode` provider 的权威完成契约。

### 权威

- `CCB_REQ_ID` 仅是请求绑定标记。
- `CCB_DONE` 不是 `opencode` 完成权威的一部分。
- 权威运行时证据来自 `opencode` 结构化存储：session 记录、消息记录、部件记录和助手时间戳。

### 请求绑定

- 受管理的 `opencode` job 将 `CCB_REQ_ID: <job_id>` 写入用户 prompt。
- 仅当观察到的助手消息通过 `parentID` 或 `parent_id` 指向用户消息，且父 prompt 解析回同一 `CCB_REQ_ID` 时，回复才属于该 job。
- Session 身份和 `session_id_filter` 范围限定存储读取器，但它们不替代请求绑定。

### 完成

- `opencode` 助手回复仅在匹配的助手消息具有 `time.completed` 时才变为完成。
- 在 `time.completed` 之前，回复文本可作为进行中预览展示，但它不得最终确定 job。
- 当匹配的助手达到完成时，执行适配器发出带有原因 `assistant_completed` 的 `TURN_BOUNDARY`。

### 无包装模式

- `no_wrap` 故意跳过受管理的请求绑定。
- 在 `no_wrap` 中，`opencode` 仍可从绑定 session 展示回复预览和已完成回复，但结果是降级的，因为它不受 `CCB_REQ_ID` 锚定。

### 非目标

- 安静终端周期不是 `opencode` 的完成权威。
- 不得将 `CCB_DONE`、终端空闲时间或窗格文本标记重新引入为 `opencode` 的主要完成路径。
