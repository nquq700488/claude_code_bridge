---
name: pend
description: Inspect the latest CCB mailbox/job reply for a named agent or `job_id`.
metadata:
  short-description: Inspect CCB reply
---

# Pend Job Or Agent

Inspect the latest mailbox/job reply for a named agent or a specific `job_id`.

## Usage

The first argument must be:
- an agent name from `.ccb/ccb.config`, or
- a `job_id`

Optional: Add a number N to show the latest N conversations.

## Options

| Option | Description |
|--------|-------------|
| `--watch` | Wait and stream replies as they arrive (blocking). Default timeout: **600s (10 min)**. |
| `--timeout <seconds>` | Override watch timeout. Only meaningful with `--watch`. |
| `<agent> <N>` | Show latest N conversations instead of just the most recent one. |

### Environment Variable

`CCB_WATCH_TIMEOUT_S` — default timeout in seconds for `--watch` (default: `600`).

## Execution (MANDATORY)

```bash
ccb pend $ARGUMENTS
```

## Timezone Note

All CCB timestamps are stored in **UTC** (e.g. `2026-06-04T08:23:05Z`).
When reporting or interpreting these timestamps to the user, convert to **Beijing Time (UTC+8)**.

Examples:
- `2026-06-04T08:23:05Z` → **2026-06-04 16:23:05 (Beijing)**
- `2026-06-04T08:41:34Z` → **2026-06-04 16:41:34 (Beijing)**

## Examples

```bash
ccb pend agent1                    # Show latest reply
ccb pend agent2 3                  # Show latest 3 conversations
ccb pend --watch agent1            # Stream replies (10 min timeout)
ccb pend --watch --timeout 300 agent1  # Stream replies (5 min timeout)
ccb pend job_1234567890ab          # Show reply for a specific job
```
