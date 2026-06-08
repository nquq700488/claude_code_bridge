<!-- CCB_CONFIG_START -->
## AI Collaboration
Use `/ask <agent>` to contact another CCB agent by name.
Use `/ping <agent|ccbd>` to inspect project control-plane health.
Use `/pend <agent|job_id>` to inspect mailbox/job replies.

Agent names come from `.ccb/ccb.config`. Providers are implementation details.

## Tool Execution Rule (MANDATORY)

All CCB commands (`ccb ask`, `ccb pend`, `ccb ping`, etc.) MUST be executed via the Bash tool.
Never describe, summarize, or claim to have executed a CCB command without actually running it.
If you mention `/ask`, `/ping`, or `/pend` in your response text, you MUST have a
corresponding Bash tool call in the same turn. Text-only simulation of CCB
commands is a protocol violation — it silently drops tasks and breaks the
multi-agent workflow.

## CCB Sync Workflow (MANDATORY)

When you invoke `/ask` or `ccb ask`, you MUST:

1. Capture the output; it will contain `[CCB_ASYNC_SUBMITTED job=<job_id>]`.
2. Extract the `job_id` (format: `job_<hex>`).
3. Block until the reply arrives:
```bash
ccb pend --watch --timeout 600 <job_id>
```
4. Present the reply to the user. If the reply is empty or the target agent has not responded yet, tell the user.

**DO NOT** skip step 2-3 — the user expects to see the reply in the same turn.

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
When a skill references a role (e.g. `reviewer`), resolve it to the configured agent that owns that role.
<!-- CCB_ROLES_END -->

<!-- CODEX_REVIEW_START -->
## Peer Review Framework

The `planner` MUST send to `reviewer` (via `/ask`) at two checkpoints:
1. **Plan Review** — after finalizing a plan, BEFORE writing code. Tag: `[PLAN REVIEW REQUEST]`.
2. **Code Review** — after completing code changes, BEFORE reporting done. Tag: `[CODE REVIEW REQUEST]`.

Include the full plan or `git diff` between `--- PLAN START/END ---` or `--- CHANGES START/END ---` delimiters.
The `reviewer` scores using Rubrics defined in `AGENTS.md` and returns JSON.

**Pass criteria**: overall >= 7.0 AND no single dimension <= 3.
**On fail**: fix issues from response, re-submit (max 3 rounds). After 3 failures, present results to user.
**On pass**: display final scores as a summary table.
<!-- CODEX_REVIEW_END -->

<!-- GEMINI_INSPIRATION_START -->
## Inspiration Consultation

For creative tasks (UI/UX design, copywriting, naming, brainstorming), the `planner` SHOULD consult `inspiration` (via `/ask`) for reference ideas.
The `inspiration` role is flexible: skip divergent perspectives when unnecessary, let the orchestrator fill alternatives, or execute on behalf of substituted roles per the collaboration spec. Exercise independent judgment and present suggestions to the user for decision.
<!-- GEMINI_INSPIRATION_END -->

<!-- CCB_CONFIG_END -->
