"""Team UI HTTP server — serves the group-chat SPA and API endpoints.

Pattern: follows config_ui.py (ThreadingHTTPServer + token auth + idle timeout).
API: GET /api/state, GET /api/timeline, POST /api/send, POST /api/up, POST /api/down.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .team_ui_assets import TEAM_UI_HTML

# markdown-it-py for server-side Markdown rendering
_md: object = None


def _render_body_html(text: str) -> str:
    """Render message body text to HTML using markdown-it-py.

    Handles CCB artifact format (strips file-path/SHA256 header, keeps content
    preview). Auto-detects JSON blocks and fenced code. Strips CCB reply
    guidance boilerplate from ask messages.
    """
    global _md
    if not text:
        return ''
    # Strip CCB artifact header (large-reply artifact reference)
    text = _strip_artifact_header(text)
    # Strip CCB reply guidance prefix (auto-added by ccb ask)
    text = _strip_ccb_guidance(text)
    if _md is None:
        try:
            from markdown_it import MarkdownIt
            _md = MarkdownIt('commonmark', {'html': False, 'linkify': True, 'typographer': True})
        except ImportError:
            _md = False
    if _md:
        # Add ```json fences around bare JSON objects at text start
        stripped = text.strip()
        if stripped.startswith('{') and not stripped.startswith('```'):
            text = '```json\n' + text + '\n```'
        return (_md.render(text) if callable(getattr(_md, 'render', None)) else text)
    return _escape_html(text)


def _strip_ccb_guidance(text: str) -> str:
    """Strip CCB guidance boilerplate auto-added by ccb ask.

    Handles multi-line and inline guidance formats.
    """
    # Remove everything from "CCB reply guidance:" to end of text
    idx = text.find('CCB reply guidance:')
    if idx >= 0:
        text = text[:idx].rstrip()
    return text


def _strip_artifact_header(text: str) -> str:
    """Strip CCB artifact reference header: 'Full text: /path/...\\nBytes: N\\nSHA256: ...\\n\\nPreview:\\n'"""
    pattern = (
        r'^.*?larger than \d+ [KMG]iB and was stored as an artifact\.\n'
        r'Full text: .+\.txt\n'
        r'Bytes: \d+\n'
        r'SHA256: [a-f0-9]{64}\n+'
        r'Preview:\n'
    )
    m = re.match(pattern, text)
    if m:
        text = text[m.end():]
    return text


def _escape_html(text: str) -> str:
    """Fallback HTML escaping when markdown-it is unavailable."""
    return (text
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('\n', '<br>'))

DEFAULT_IDLE_TIMEOUT_S = 1800.0  # 30 min
DEFAULT_PORT = 0  # OS-assigned


class TeamUiHandle:
    """Returned by prepare_team_ui; holds server reference for lifecycle control."""

    def __init__(self, *, url: str, summary: dict, server: ThreadingHTTPServer,
                 last_activity: list[float], idle_timeout_s: float):
        self.url = url
        self.summary = summary
        self._server = server
        self._last_activity = last_activity
        self._idle_timeout_s = idle_timeout_s

    def serve_forever(self) -> None:
        self._last_activity[0] = time.monotonic()
        self._server.timeout = min(1.0, max(0.05, self._idle_timeout_s))
        while time.monotonic() - self._last_activity[0] < self._idle_timeout_s:
            self._server.handle_request()

    def close(self) -> None:
        self._server.server_close()


def prepare_team_ui(context, command, *, token=None, idle_timeout_s=DEFAULT_IDLE_TIMEOUT_S):
    """Create and return a TeamUiHandle for the given team.

    The caller should call handle.serve_forever() to run the server loop.
    """
    root = _project_root(context)
    team_name = str(getattr(command, 'team_name', '') or '').strip()
    if not team_name:
        raise ValueError('team name is required')

    # Validate team exists
    from agents.config_loader import load_project_config

    config = load_project_config(root, include_loop_overlays=False).config
    if team_name not in config.teams:
        raise ValueError(f'team {team_name!r} not defined in config')

    team = config.teams[team_name]
    access_token = token or secrets.token_urlsafe(24)
    last_activity = [time.monotonic()]
    page = TEAM_UI_HTML.encode('utf-8')
    team_name_bytes = team_name.encode('utf-8')

    # Capture context data for request handlers
    handler_data = {
        'root': root,
        'team_name': team_name,
        'team_name_bytes': team_name_bytes,
        'page': page,
        'token': access_token,
        'last_activity': last_activity,
        'command': command,
    }

    handler = _make_handler(handler_data)
    port = int(getattr(command, 'port', 0) or 0)
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    server.daemon_threads = True
    host, bound_port = server.server_address[:2]
    url = f'http://{host}:{bound_port}/?token={access_token}'

    return TeamUiHandle(
        url=url,
        summary={
            'team_ui_status': 'serving',
            'url': url,
            'team': team_name,
            'topology': team.topology,
            'port': bound_port,
        },
        server=server,
        last_activity=last_activity,
        idle_timeout_s=max(0.05, float(idle_timeout_s)),
    )


# ── request handler ──────────────────────────────────────────────────


def _make_handler(data: dict):
    """Build a request handler class with closure over shared data."""

    class TeamUiRequestHandler(BaseHTTPRequestHandler):
        server_version = 'CCBTeamUI/1'

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if not self._authorized(parsed):
                self._send(HTTPStatus.FORBIDDEN, b'forbidden\n', 'text/plain; charset=utf-8')
                return
            data['last_activity'][0] = time.monotonic()

            if parsed.path in {'/', '/index.html'}:
                self._send(HTTPStatus.OK, data['page'], 'text/html; charset=utf-8')
                return

            if parsed.path == '/api/state':
                payload = _build_state_payload(data['root'], data['team_name'])
                self._send_json(HTTPStatus.OK, payload)
                return

            if parsed.path == '/api/timeline':
                cursor = parse_qs(parsed.query).get('since', [''])[0]
                payload = _build_timeline_payload(data['root'], data['team_name'], cursor)
                self._send_json(HTTPStatus.OK, payload)
                return

            self._send(HTTPStatus.NOT_FOUND, b'not found\n', 'text/plain; charset=utf-8')

        def do_POST(self):  # noqa: N802
            parsed = urlparse(self.path)
            if not self._authorized(parsed):
                self._send(HTTPStatus.FORBIDDEN, b'forbidden\n', 'text/plain; charset=utf-8')
                return
            data['last_activity'][0] = time.monotonic()

            try:
                body = self._read_json_body()
            except Exception:
                self._send_json(HTTPStatus.BAD_REQUEST, {'status': 'error', 'error': 'invalid JSON'})
                return

            if parsed.path == '/api/send':
                payload = _handle_send(data['root'], data['team_name'], body)
                self._send_json(HTTPStatus.OK, payload)
                return

            if parsed.path == '/api/up':
                payload = _handle_team_action(data['root'], data['team_name'], 'up', data['command'])
                self._send_json(HTTPStatus.OK, payload)
                return

            if parsed.path == '/api/down':
                payload = _handle_team_action(data['root'], data['team_name'], 'down', data['command'])
                self._send_json(HTTPStatus.OK, payload)
                return

            self._send(HTTPStatus.NOT_FOUND, b'not found\n', 'text/plain; charset=utf-8')

        def log_message(self, fmt, *args):
            pass  # Suppress access logs

        def _authorized(self, parsed) -> bool:
            token = parse_qs(parsed.query).get('token', [''])[0]
            return token == data['token']

        def _send(self, status, content, content_type):
            body = content if isinstance(content, bytes) else str(content).encode('utf-8')
            self.send_response(int(status))
            self.send_header('Content-Type', str(content_type))
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
            self._send(status, body, 'application/json; charset=utf-8')

        def _read_json_body(self):
            try:
                length = int(self.headers.get('Content-Length', '0') or '0')
            except (ValueError, TypeError):
                length = 0
            if length < 0 or length > 65536:  # 0-64 KiB
                raise ValueError('invalid Content-Length')
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw) if raw else {}

    return TeamUiRequestHandler


# ── API handlers ──────────────────────────────────────────────────────


def _build_state_payload(root: Path, team_name: str) -> dict:
    """Read team instance state + member lifecycle states from disk."""
    instance = _load_json(_team_state_path(root, team_name))
    if not instance:
        return {'team': team_name, 'status': 'not_up', 'topology': '?', 'members': []}

    members = []
    for m in instance.get('members', []):
        name = m.get('name', '')
        provider = m.get('provider', '?')
        # Check for real agent data (any jobs/events file) or lifecycle state
        has_data = _find_agent_file(root, name, 'jobs.jsonl').is_file() or \
                   _find_agent_file(root, name, 'events.jsonl').is_file()
        lc = _load_json(_member_lifecycle_path(root, name))
        state = lc.get('lifecycle_state', 'visible') if lc else ('visible' if has_data else 'missing')
        model = lc.get('model') if lc else None
        members.append({
            'name': name,
            'provider': provider,
            'model': model,
            'description': m.get('description'),
            'state': state,
            'status': lc.get('agent_lifecycle_status', 'active') if lc else ('active' if has_data else 'missing'),
        })

    # Try to get topology from config
    topology = instance.get('topology', '?')
    try:
        from agents.config_loader import load_project_config
        config = load_project_config(root, include_loop_overlays=False).config
        if team_name in config.teams:
            topology = config.teams[team_name].topology
    except Exception:
        pass

    return {
        'team': team_name,
        'topology': topology,
        'status': instance.get('status', 'running'),
        'members': members,
    }


def _build_timeline_payload(root: Path, team_name: str, cursor: str) -> dict:
    """Build timeline events from mailbox jobs and events for each team member.

    Reads .ccb/runtime/agents/<name>/jobs.jsonl for ask/reply records,
    and .ccb/runtime/agents/<name>/events.jsonl for completion replies.
    Returns incremental events since the cursor timestamp.
    """
    instance = _load_json(_team_state_path(root, team_name))
    if not instance:
        return {'events': [], 'cursor': cursor or ''}

    upped_at = instance.get('upped_at', '')
    members = instance.get('members', [])

    # Phase 1: collect latest JobRecord per job_id across ALL members
    jobs_by_id: dict[str, dict] = {}
    for m in members:
        name = m.get('name', '')
        if not name or '..' in name or '/' in name or '\\' in name:
            continue
        jobs_path = _find_agent_file(root, name, 'jobs.jsonl')
        if not jobs_path.is_file():
            continue
        for record in _read_jsonl(jobs_path):
            jid = record.get('job_id', '')
            rec_ts = record.get('updated_at') or record.get('created_at', '')
            if not jid or not rec_ts:
                continue
            if cursor and rec_ts <= cursor:
                continue
            if upped_at and rec_ts < upped_at:
                continue
            prev = jobs_by_id.get(jid)
            prev_ts = (prev.get('updated_at') or prev.get('created_at', '')) if prev else ''
            if prev is None or rec_ts >= prev_ts:
                jobs_by_id[jid] = record

    # Phase 2: collect completion_terminal replies from events.jsonl
    replies_by_job: dict[str, str] = {}
    for m in members:
        name = m.get('name', '')
        if not name or '..' in name or '/' in name or '\\' in name:
            continue
        events_path = _find_agent_file(root, name, 'events.jsonl')
        if not events_path.is_file():
            continue
        for line in _read_jsonl(events_path):
            evt_type = line.get('type') or line.get('event') or ''
            if evt_type != 'completion_terminal':
                continue
            jid = line.get('job_id', '')
            if not jid:
                continue
            ts = line.get('created_at') or line.get('timestamp') or ''
            if not ts:
                continue
            if cursor and ts <= cursor:
                continue
            if upped_at and ts < upped_at:
                continue
            payload = line.get('payload') or {}
            if not isinstance(payload, dict):
                continue
            # UI-generated ask markers — consumed by send response, not timeline
            if payload.get('_ui_ask'):
                continue
            # Real agent reply
            reply = payload.get('reply', '')
            if reply and jid not in replies_by_job:
                replies_by_job[jid] = reply

    # Phase 3: build timeline — only reply events from job records.
    # Ask events are shown by the frontend immediately from the send response.
    events: list[dict] = []
    for jid, job in sorted(jobs_by_id.items()):
        agent_name = job.get('agent_name', '')
        provider = ''
        for m in members:
            if m.get('name') == agent_name:
                provider = m.get('provider', '')
                break
        request = job.get('request') or {}
        request_body = request.get('body', '') if isinstance(request, dict) else ''
        from_actor = request.get('from_actor', '') if isinstance(request, dict) else ''
        is_human = from_actor in ('human', 'user')

        # Reply from events.jsonl or terminal_decision
        reply = replies_by_job.get(jid, '')
        if not reply:
            term = job.get('terminal_decision') or {}
            reply = term.get('reply', '') if isinstance(term, dict) else ''
        if reply:
            term = job.get('terminal_decision') or {}
            reply_ts = (term.get('finished_at') or job.get('updated_at') or job.get('created_at', '')) if isinstance(term, dict) else job.get('created_at', '')

            body_text = str(reply)[:2000]
            events.append({
                'type': 'reply',
                'from': agent_name,
                'from_provider': provider,
                'to': 'You' if is_human else (from_actor or ''),
                'body': body_text,
                'body_html': _render_body_html(body_text),
                'time': reply_ts,
                'job_id': jid,
                'reply_to': str(request_body)[:120] if request_body else '',
            })

    events.sort(key=lambda e: e.get('time', ''))
    new_cursor = events[-1]['time'] if events else (cursor or '')
    return {'events': events, 'cursor': new_cursor}


def _handle_send(root: Path, team_name: str, body: dict) -> dict:
    """Handle POST /api/send — submit a message.

    Tries ccb ask via subprocess first; falls back to writing a local job record
    for demo/offline use.
    """
    to = str(body.get('to', '') or '').strip()
    msg = str(body.get('body', '') or '').strip()
    if not to or not msg:
        return {'status': 'error', 'error': 'to and body are required'}

    # Validate target is a member of this team instance
    instance = _load_json(_team_state_path(root, team_name))
    if not instance:
        return {'status': 'error', 'error': 'team not up'}
    member_names = {m.get('name', '') for m in instance.get('members', [])}

    if to == '@all':
        targets = [n for n in member_names if n]
    elif to not in member_names:
        return {'status': 'error', 'error': 'target is not a member of this team'}
    else:
        targets = [to]

    job_ids = []
    for target in targets:
        jid = _submit_or_record(root, team_name, target, msg, instance)
        if jid:
            job_ids.append(jid)

    # Return the ask as an event for immediate frontend display
    ask_event = {
        'type': 'ask',
        'from': 'You',
        'from_provider': 'human',
        'to': to if to != '@all' else 'all',
        'body': msg,
        'body_html': _render_body_html(msg),
        'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }

    return {'status': 'sent', 'job_ids': job_ids, 'targets': targets, 'ask_event': ask_event}


def _submit_or_record(root, team_name, target, msg, instance):
    """Send via ccb ask. Returns the ask bubble for immediate frontend display.

    The real agent reply will be picked up by polling events.jsonl.
    """
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    provider = ''
    for m in instance.get('members', []):
        if m.get('name') == target:
            provider = m.get('provider', '')
            break

    # Let ccb ask handle the real job
    try:
        result = _ask_member(root, target, msg)
        if result.get('status') == 'sent':
            return result.get('job_id', 'unknown')
    except Exception:
        pass
    return 'queued'


def _broadcast(root: Path, team_name: str, msg: str) -> dict:
    """Send to all team members."""
    instance = _load_json(_team_state_path(root, team_name))
    if not instance:
        return {'status': 'error', 'error': 'team not up'}

    results = []
    for m in instance.get('members', []):
        name = m.get('name', '')
        if name:
            r = _ask_member(root, name, msg)
            results.append({'to': name, **r})
    return {'status': 'sent', 'results': results}


def _ask_member(root: Path, to: str, msg: str) -> dict:
    """Send a message to a team member via ccb ask subprocess."""
    try:
        ccb_bin = _find_ccb()
        result = subprocess.run(
            [ccb_bin, 'ask', '--silence', to, msg],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Extract job_id from output if present
        job_id = ''
        for line in result.stdout.splitlines():
            if 'job=' in line:
                job_id = line.split('job=')[-1].split()[0].strip()
                break
        if result.returncode != 0:
            return {'status': 'error', 'error': result.stderr.strip() or 'ask failed'}
        return {'status': 'sent', 'job_id': job_id}
    except FileNotFoundError:
        return {'status': 'error', 'error': 'ccb not found in PATH'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'ccb ask timed out'}
    except Exception as exc:
        return {'status': 'error', 'error': str(exc)}


def _handle_team_action(root: Path, team_name: str, action: str, command) -> dict:
    """Handle POST /api/up and /api/down — delegate to team_lifecycle."""
    from cli.services.team_lifecycle import team_down, team_up

    class _Cmd:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Ctx:
        def __init__(self, r):
            self.project_root = r
            self.project = type('_P', (), {'project_root': r})()

    ctx = _Ctx(root)
    cmd = _Cmd(action=action, team_name=team_name, unload=False)
    try:
        if action == 'up':
            result = team_up(ctx, cmd)
        else:
            result = team_down(ctx, cmd)
        return {'status': 'ok', 'action': action, 'result': result}
    except Exception as exc:
        return {'status': 'error', 'action': action, 'error': str(exc)}


# ── helpers ───────────────────────────────────────────────────────────


def _project_root(context) -> Path:
    direct = getattr(context, 'project_root', None)
    if direct is not None:
        return Path(direct)
    paths = getattr(context, 'paths', None)
    if paths is not None and getattr(paths, 'project_root', None) is not None:
        return Path(paths.project_root)
    return Path(context.project.project_root)


def _validate_name_safe(name: str, label: str) -> None:
    """Raise ValueError if name contains path traversal sequences."""
    if '..' in name or '/' in name or '\\' in name:
        raise ValueError(f'{label} contains forbidden path characters: {name!r}')


def _team_state_path(root: Path, team_name: str) -> Path:
    _validate_name_safe(team_name, 'team name')
    return root / '.ccb' / 'runtime' / 'teams' / team_name / 'state.json'


def _find_agent_file(root: Path, agent_name: str, filename: str) -> Path:
    """Find data file — check both .ccb/agents/<name>/ (real) and runtime/ (dynamic)."""
    primary = root / '.ccb' / 'agents' / agent_name / filename
    if primary.is_file():
        return primary
    return root / '.ccb' / 'runtime' / 'agents' / agent_name / filename


def _member_lifecycle_path(root: Path, agent_name: str) -> Path:
    _validate_name_safe(agent_name, 'agent name')
    return root / '.ccb' / 'runtime' / 'agents' / agent_name / 'lifecycle.json'


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return list of parsed dicts."""
    records = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    records.append(obj)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return records


def _find_ccb() -> str:
    """Find the ccb binary."""
    # Prefer ~/.local/bin/ccb (global install from sync-local)
    candidate = Path.home() / '.local' / 'bin' / 'ccb'
    if candidate.is_file():
        return str(candidate)
    # Fall back to PATH
    return 'ccb'


def open_team_ui_url(url: str) -> bool:
    try:
        return webbrowser.open(url)
    except Exception:
        return False


__all__ = [
    'TeamUiHandle',
    'open_team_ui_url',
    'prepare_team_ui',
]
