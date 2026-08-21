# 项目 CLAUDE.md

## 项目 Agent 团队（CCB 管理）

本项目（claude_code_bridge-6）的 AI Agent 团队由 CCB 管理，agent 与 provider 映射如下：

| Agent | Provider | 角色职责 |
|-------|----------|----------|
| `planner` | Codex | 方案设计 - 系统架构、技术选型、模块划分 |
| `developer` | Claude | 核心开发 - 编码实现、功能开发、Bug 修复 |
| `reviewer` | Codex | 代码审查 - 代码质量、潜在风险、最佳实践检查 |
| `tester` | Claude | 执行分析测试 - 命令执行、结果分析、回归测试 |

> **本项目的 agent 就是以上 4 个。** 定义见 `.ccb/ccb-compact.config`（`config_profile = "compact"`）与 `.ccb/ccb.config` 的 `[teams.team]`。
>
> 全局 `~/.claude/CLAUDE.md` 中提到的 `designer` / `inspiration` / `executor` 等是**抽象角色映射**（用于技能引用解析），**不是本项目的 agent**。除非被明确引用，否则以本项目的 agent 配置为准。

## 协作方式

- 通过 `/ask <agent>` 或 `ccb ask <agent> <message>` 向指定 agent 发送任务
- 默认同步等待回复：`ask` → 解析 `job_id` → `pend --watch <job_id>`
- 手动查看回复：`ccb pend <agent>` 或 `ccb pend --watch <agent>`
- **时区注意**：CCB 日志时间戳均为 **UTC**，向用户报告时换算为**北京时间（UTC+8）**

## 相关文档

- [AGENTS.md](AGENTS.md) — 项目 Agent 团队与布局
- [CCB_INSTALL_GUIDE.md](CCB_INSTALL_GUIDE.md) — 安装与配置指南
