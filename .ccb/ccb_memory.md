# CCB 项目记忆

本项目使用 CCB 进行多智能体可见协作。

## 项目 Agent 团队

本项目的 agent 团队如下（定义见 `.ccb/ccb-compact.config` 与 `.ccb/ccb.config` 的 `[teams.team]`）：

| Agent | Provider | 角色职责 |
|-------|----------|----------|
| `planner` | Codex | 方案设计 - 系统架构、技术选型、模块划分 |
| `developer` | Claude | 核心开发 - 编码实现、功能开发、Bug 修复 |
| `reviewer` | Codex | 代码审查 - 代码质量、潜在风险、最佳实践检查 |
| `tester` | Claude | 执行分析测试 - 命令执行、结果分析、回归测试 |

> 全局 `~/.claude/CLAUDE.md` 中的 `designer` / `inspiration` / `executor` 是**抽象角色映射**（供技能引用解析），**不是本项目的 agent**。本项目实际可委托的 agent 只有上表 4 个。

## 协作方式

- 你是 CCB 管理项目团队中的一个智能体。
- 使用 `/ask <agent>` 或 `ccb ask` 委托任务给配置的其他智能体，
  然后从输出中提取 `[CCB_ASYNC_SUBMITTED job=<job_id>]` 中的 `job_id`，
  阻塞等待回复：`ccb pend --watch --timeout 600 <job_id>`。
- 委托时需明确：目标、范围/文件、假设、预期输出和验证需求。
- 回复时简洁说明：发现、变更、验证结果、阻塞项和风险。
