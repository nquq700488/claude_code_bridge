# CCB 项目记忆

本项目使用 CCB 进行多智能体可见协作。

## 协作方式

- 你是 CCB 管理项目团队中的一个智能体。
- 使用 `/ask <agent>` 或 `ccb ask` 委托任务给配置的其他智能体，
  然后从输出中提取 `[CCB_ASYNC_SUBMITTED job=<job_id>]` 中的 `job_id`，
  阻塞等待回复：`ccb pend --watch --timeout 600 <job_id>`。
- 委托时需明确：目标、范围/文件、假设、预期输出和验证需求。
- 回复时简洁说明：发现、变更、验证结果、阻塞项和风险。
