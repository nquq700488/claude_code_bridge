<!-- CCB_ROLES_START -->
## Role Assignment

Abstract roles map to concrete AI providers. Skills reference roles, not providers directly.

| Role | Provider | Description |
|------|----------|-------------|
| `planner` | `codex` | Primary planner and architect — owns plans and designs |
| `inspiration` | `opencode` | Flexible collaboration — skip divergent perspectives, fill alternatives, or execute per substituted role spec |
| `executor` | `claude` | Code implementation — writes and modifies code |
| `reviewer` | `codex` | Scored quality gate — evaluates plans/code using Rubrics |
| `tester` | `kimi` | Test engineering — validates features, writes tests, ensures quality |

To change a role assignment, edit the Provider column above.
When a skill references a role (e.g. `reviewer`), resolve it to the provider listed here.
<!-- CCB_ROLES_END -->
