---
name: ask
description: Send a request to a CCB agent and wait for the reply synchronously.
metadata:
  short-description: Ask agent (sync)
---

Use this when the user asks you to delegate with CCB, or when project memory
says to use CCB `ask` for collaboration.

## Quick Reference

| Mode | Flag | Behavior |
|------|------|----------|
| **Default (sync)** | _(none)_ | Submit → wait for reply → report result |
| **Silence** | `--silence` | Submit → **do not wait** (no reply needed) |
| **Callback** | `--callback` | Submit → stop immediately (CCB delivers continuation) |
| **Artifact** | `--artifact-*` | Request/reply via text artifact files |

## Default: Synchronous Wait

⚠️ **ANTI-HALLUCINATION**: You MUST invoke this skill via the Bash tool. Never say "I've sent the request" without actually running the command.

1. Submit the task and capture the output:
```bash
command ask "$TARGET" <<'EOF'
$MESSAGE
EOF
```

2. Extract `job_id` from the output (format: `job_<hex>`).

3. Block until the reply arrives, then report it:
```bash
command pend --watch "$JOB_ID" --timeout 600
```

4. Present the reply to the user. If the reply is empty or `[CCB_ASYNC_SUBMITTED]`, tell the user the target agent has not responded yet.

**DO NOT** skip step 3 — the user expects to see the reply in the same turn.

## --silence: No Reply Needed

Use when the user explicitly says they don't need a reply, or when the task is fire-and-forget (e.g. "run this in the background", "just trigger it", "I don't need the result").

```bash
command ask --silence "$TARGET" <<'EOF'
$MESSAGE
EOF
```

After submit, report the job_id only. Do NOT wait. Do NOT run `pend --watch`.

## --callback: CCB Continuation

Use ONLY when this exact turn is an active CCB task and the child result is
required before you can finish that parent task.

```bash
command ask --callback "$TARGET" <<'EOF'
$MESSAGE
EOF
```

After callback submit, **stop immediately**. CCB will deliver the child result as a continuation task. Do NOT wait, do NOT run `pend --watch`.

If CCB says `ask --callback requires an active parent job`, the mode choice was wrong — resubmit with default (no flag).

## Message Format

Always send `MESSAGE` through the `<<'EOF' ... EOF` heredoc. No other form is allowed. Do NOT manually append output-policy text; `ask` injects reply guidance automatically.
