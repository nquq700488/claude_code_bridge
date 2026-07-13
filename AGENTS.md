# Agents

## 项目 Agent 团队

本项目（claude_code_bridge-6）使用 CCB 管理以下 5 个 AI Agent：

| Agent | Provider | 角色职责 |
|-------|----------|----------|
| `planner` | Codex | 方案设计 - 负责系统架构、技术选型、模块划分 |
| `executor` | Codex | 核心开发 - 负责编码实现、功能开发、Bug 修复 |
| `reviewer` | Claude | 代码审查 - 负责代码质量、潜在风险、最佳实践检查 |
| `tester` | Kimi | 执行分析测试 - 负责命令执行、结果分析、回归测试 |
| `inspiration` | OpenCode | 弹性协作 - 跳过发散视角、补充备选方案，或按被替代角色规范代执行 |

分屏布局（tmux）：
```
┌───────────────┬───────────────┐
│    planner    │  executor     │
│    (codex)    │  (claude)     │
├───────────────┼───────────────┼
│   reviewer    │   tester      │
│   (codex)     │   (kimi)      │
└───────────────┴───────────────┘
```

- 通过 `/ask` skill 或 `ccb ask <agent> <message>` 向指定 agent 发送任务。默认**同步等待回复**（`ask` → 解析 job_id → `pend --watch <job_id>`），`--silence` 跳过等待。
- 手动查看回复：`ccb pend <agent>` 或 `ccb pend --watch <agent>`。
- **时区注意**：CCB 日志时间戳均为 **UTC**。向用户报告时，必须换算为 **北京时间（UTC+8）**。

## 指令执行规范（强制）

> **强制读取并执行**：在处理任何用户指令之前，必须先完整读取并严格遵循
> [INSTRUCTION_EXECUTION_SPEC.md](./INSTRUCTION_EXECUTION_SPEC.md) 中定义的
> 理解、拆解、执行、验证、收尾流程。
>
> 此规范优先级高于一般性默认行为，不得跳过、简化或选择性执行。

## 代码提交前检查（强制）

### 1. 检查上游更新

每次提交代码前，必须先检查上游源码项目是否有更新：

```bash
git fetch upstream
git log --oneline HEAD..upstream/main
```

如果有新提交：

- 执行 `git merge upstream/main` 合并更新
- 解决所有冲突
- 确保合并后的代码能正常工作
- 将合并提交与本次修改一起提交（不分开提交）

**目的**：避免推送过时的代码，减少合并冲突。

### 2. 检查文档同步

如果本次修改涉及以下内容，必须同步更新 [CCB_INSTALL_GUIDE.md](./CCB_INSTALL_GUIDE.md)：

- 新增或修改 CLI 命令
- 新增或修改 Provider 支持
- 配置文件格式变更
- 环境变量新增或变更
- 安装/部署步骤变更
- 常见问题或排查步骤变更

同时检查 [CHANGELOG.md](./CHANGELOG.md) 和 [KIMI_INTEGRATION.md](./KIMI_INTEGRATION.md) 是否需要更新。
