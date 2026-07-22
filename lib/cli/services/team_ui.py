"""Team UI HTTP server — serves the group-chat SPA and API endpoints.

Pattern: follows config_ui.py (ThreadingHTTPServer + token auth + idle timeout).
API: GET /api/state, GET /api/timeline, POST /api/send, POST /api/up, POST /api/down.
"""

from __future__ import annotations

import json
import os
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
            length = int(self.headers.get('Content-Length', '0') or '0')
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
        lc = _load_json(_member_lifecycle_path(root, name))
        provider = m.get('provider', '?')
        model = None
        if lc:
            model = lc.get('model')
        members.append({
            'name': name,
            'provider': provider,
            'model': model,
            'description': m.get('description'),
            'state': lc.get('lifecycle_state', 'unknown') if lc else 'missing',
            'status': lc.get('agent_lifecycle_status', 'unknown') if lc else 'missing',
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
    """Read events from team instance and member event logs.

    Returns incremental events since the cursor timestamp.
    """
    instance = _load_json(_team_state_path(root, team_name))
    if not instance:
        return {'events': [], 'cursor': cursor or ''}

    upped_at = instance.get('upped_at', '')
    member_names = {m.get('name', '') for m in instance.get('members', [])}

    events: list[dict] = []
    for name in member_names:
        if not name:
            continue
        events_path = root / '.ccb' / 'runtime' / 'agents' / name / 'events.jsonl'
        if not events_path.is_file():
            continue
        for line in _read_jsonl(events_path):
            ts = line.get('timestamp') or line.get('updated_at') or line.get('created_at') or ''
            if cursor and ts <= cursor:
                continue
            if upped_at and ts < upped_at:
                continue
            evt = line.get('event', '')
            body = line.get('body') or line.get('reply') or json.dumps(line, ensure_ascii=False)
            if isinstance(body, str) and len(body) > 2000:
                body = body[:2000] + '…'
            events.append({
                'type': 'system' if evt in ('add', 'remove', 'up', 'down') else 'message',
                'from': line.get('agent') or line.get('from_actor') or name,
                'from_provider': line.get('provider') or instance.get('members', [{}])[0].get('provider', '') if instance.get('members') else '',
                'body': str(body),
                'time': ts,
            })

    events.sort(key=lambda e: e.get('time', ''))
    new_cursor = events[-1]['time'] if events else cursor
    return {'events': events, 'cursor': new_cursor}


def _handle_send(root: Path, team_name: str, body: dict) -> dict:
    """Handle POST /api/send — submit a message via ccb ask."""
    to = str(body.get('to', '') or '').strip()
    msg = str(body.get('body', '') or '').strip()
    if not to or not msg:
        return {'status': 'error', 'error': 'to and body are required'}

    if to == '@all':
        return _broadcast(root, team_name, msg)

    # Single target: use ccb ask via subprocess
    return _ask_member(root, to, msg)


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


def _team_state_path(root: Path, team_name: str) -> Path:
    return root / '.ccb' / 'runtime' / 'teams' / team_name / 'state.json'


def _member_lifecycle_path(root: Path, agent_name: str) -> Path:
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
    """Find the ccb binary — use the running process path or PATH lookup."""
    # Try the current Python's parent script first
    if sys.argv and sys.argv[0]:
        candidate = Path(sys.argv[0]).resolve()
        if candidate.name == 'ccb' or candidate.name.startswith('ccb'):
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
