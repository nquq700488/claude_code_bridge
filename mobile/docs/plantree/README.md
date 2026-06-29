# CCB Mobile Plan Tree

Date: 2026-06-27

## Purpose

This is the planning entrypoint for the standalone CCB mobile project.

## Authority Order

1. Active decisions under `docs/plantree/plans/mobile-tmux-control/decisions/`.
2. The mobile roadmap and execution plan under
   `docs/plantree/plans/mobile-tmux-control/`.
3. Baseline notes under `docs/plantree/baseline/`.
4. External CCB source contracts in `/home/bfly/yunwei/ccb_source/docs/` when
   server-side CCB behavior is relevant.

## Baseline

- [baseline/README.md](baseline/README.md)

## Active Plans

| Plan | Status | Current Phase | Last Landed | Next Target |
| :--- | :--- | :--- | :--- | :--- |
| [mobile-tmux-control](plans/mobile-tmux-control/README.md) | In Progress | Phase 4E Physical Tailnet Hardening | 2026-06-27 `17b5540` hardened physical Tailnet evidence recording/audit so accepted T0-T6 case evidence must be safe, present, and non-empty. | Run the physical Android phone + Tailnet runbook once hardware/network are available, then register passing `history/physical-tailnet-final-audit.json` for the acceptance audit. |

## How To Read

Start with the active plan root, then read roadmap, decisions, and the
specific topic file for the current task.
