from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import math
import re


_PROTOCOL_LINE_RE = re.compile(r'^\s*CCB_(?:REQ_ID|BEGIN|DONE):.*$', re.MULTILINE)
_TERMINAL_OBSERVER_STATUSES = frozenset({'completed', 'cancelled', 'failed', 'incomplete'})


def display_text(value: object) -> str:
    text = str(value or '')
    if not text:
        return ''
    text = _PROTOCOL_LINE_RE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def render_mapping(payload: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(f'{key}: {value}' for key, value in payload.items())


def render_composer_unavailable_action(agent_name: object) -> str:
    agent = str(agent_name or '<agent>')
    return (
        f'composer_unavailable_action: inspect with `ccb screen {agent}` and resolve the provider '
        'prompt manually; the job remains queued and normal dispatch resumes when the composer is usable'
    )


def render_composer_unavailable(wait: object, *, agent_name: object) -> tuple[str, ...]:
    if not isinstance(wait, Mapping):
        return ()
    reason = wait.get('composer_unavailable_reason')
    elapsed = wait.get('composer_unavailable_elapsed_seconds')
    threshold = wait.get('composer_unavailable_threshold_seconds')
    if reason not in {'composer_missing', 'composer_layout_unknown'}:
        return ()
    if not _finite_number(elapsed) or not _finite_number(threshold):
        return ()
    attention = wait.get('composer_unavailable_attention') is True
    lines = (
        'composer_unavailable: '
        f'agent={agent_name} job={wait.get("job_id")} reason={reason} '
        f'elapsed_seconds={float(elapsed):.1f} threshold_seconds={float(threshold):.1f} '
        f'attention={str(attention).lower()}',
    )
    return (*lines, render_composer_unavailable_action(agent_name)) if attention else lines


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def render_observer_notice(
    *,
    view: str,
    terminal: bool,
    authority: str = 'supplementary_snapshot',
) -> tuple[str, ...]:
    lines = [
        f'observer_view: {view}',
        f'observer_authority: {authority}',
        f'observer_terminal: {str(bool(terminal)).lower()}',
    ]
    if terminal:
        lines.append(
            'observer_notice: weak observer surface; terminal snapshot shown; use ccb trace <id> for authoritative lineage'
        )
    else:
        lines.append(
            'observer_notice: weak observer surface; non-terminal state may change; use ccb trace <id> for lineage when needed'
        )
    return tuple(lines)


def observer_status_is_terminal(status: object) -> bool:
    normalized = str(status or '').strip().lower()
    return normalized in _TERMINAL_OBSERVER_STATUSES


def render_tmux_cleanup_summaries(items: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for item in items:
        socket_name = cleanup_field(getattr(item, 'socket_name', None), default='<default>')
        owned = cleanup_csv(getattr(item, 'owned_panes', ()) or ())
        active = cleanup_csv(getattr(item, 'active_panes', ()) or ())
        orphaned = cleanup_csv(getattr(item, 'orphaned_panes', ()) or ())
        killed = cleanup_csv(getattr(item, 'killed_panes', ()) or ())
        lines.append(
            'tmux_cleanup: '
            f'socket={socket_name} owned={owned} active={active} orphaned={orphaned} killed={killed}'
        )
    return tuple(lines)


def render_worktree_alerts(items: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for item in items:
        branch_name = cleanup_field(getattr(item, 'branch_name', None), default='<none>')
        workspace_path = cleanup_field(getattr(item, 'workspace_path', None), default='<none>')
        lines.append(
            'worktree_warning: '
            f'agent={getattr(item, "agent_name", "")} '
            f'reason={getattr(item, "reason", "")} '
            f'branch={branch_name} '
            f'dirty={_tri_state(getattr(item, "dirty", None))} '
            f'merged_into_head={_tri_state(getattr(item, "merged", None))} '
            f'registered={_tri_state(getattr(item, "registered", None))} '
            f'exists={_tri_state(getattr(item, "exists", None))} '
            f'path={workspace_path}'
        )
    return tuple(lines)


def render_worktree_retirements(items: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for item in items:
        branch_name = cleanup_field(getattr(item, 'branch_name', None), default='<none>')
        workspace_path = cleanup_field(getattr(item, 'workspace_path', None), default='<none>')
        lines.append(
            'worktree_retired: '
            f'agent={getattr(item, "agent_name", "")} '
            f'reason={getattr(item, "reason", "")} '
            f'branch={branch_name} '
            f'removed_agent_state={_tri_state(getattr(item, "removed_agent_state", None))} '
            f'path={workspace_path}'
        )
    return tuple(lines)


def cleanup_csv(items: Iterable[object]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    return ','.join(values) if values else '-'


def cleanup_field(value: object, *, default: str) -> str:
    text = str(value or '').strip()
    return text or default


def _tri_state(value: object) -> str:
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    return 'unknown'


def write_lines(out, lines: Iterable[str]) -> None:
    for line in lines:
        print(line, file=out)


__all__ = [
    'display_text',
    'observer_status_is_terminal',
    'render_composer_unavailable_action',
    'render_observer_notice',
    'render_mapping',
    'render_tmux_cleanup_summaries',
    'render_worktree_alerts',
    'render_worktree_retirements',
    'write_lines',
]
