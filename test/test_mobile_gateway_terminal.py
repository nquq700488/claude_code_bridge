from __future__ import annotations

from types import SimpleNamespace

from mobile_gateway.terminal import (
    TerminalAttachTarget,
    TerminalGeometry,
    _send_tmux_terminal_bytes,
    _send_tmux_terminal_literal,
)


def _target() -> TerminalAttachTarget:
    return TerminalAttachTarget(
        terminal_id='term-test',
        socket_path='/tmp/ccb-test/tmux.sock',
        session_name='ccb-test',
        pane_id='%42',
        geometry=TerminalGeometry(),
        target_summary={'project_id': 'proj-test', 'agent': 'lead', 'pane_id': '%42'},
    )


def test_terminal_literal_input_targets_pane(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('mobile_gateway.terminal.subprocess.run', fake_run)

    _send_tmux_terminal_literal(_target(), 'hello')

    assert calls == [
        ['tmux', '-S', '/tmp/ccb-test/tmux.sock', 'send-keys', '-t', '%42', '-l', 'hello']
    ]


def test_terminal_control_bytes_target_pane(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('mobile_gateway.terminal.subprocess.run', fake_run)
    target = _target()

    _send_tmux_terminal_bytes(target, b'\r')
    _send_tmux_terminal_bytes(target, b'\t')
    _send_tmux_terminal_bytes(target, b'\x1b')

    assert calls == [
        ['tmux', '-S', '/tmp/ccb-test/tmux.sock', 'send-keys', '-t', '%42', 'Enter'],
        ['tmux', '-S', '/tmp/ccb-test/tmux.sock', 'send-keys', '-t', '%42', 'Tab'],
        ['tmux', '-S', '/tmp/ccb-test/tmux.sock', 'send-keys', '-t', '%42', 'Escape'],
    ]


def test_terminal_decoded_bytes_fall_back_to_literal_pane_input(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('mobile_gateway.terminal.subprocess.run', fake_run)

    _send_tmux_terminal_bytes(_target(), '你好'.encode('utf-8'))

    assert calls == [
        ['tmux', '-S', '/tmp/ccb-test/tmux.sock', 'send-keys', '-t', '%42', '-l', '你好']
    ]
