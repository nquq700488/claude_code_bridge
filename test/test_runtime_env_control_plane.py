from __future__ import annotations

from runtime_env.control_plane import control_plane_env


def test_control_plane_env_keeps_provider_api_env(monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.example.test/v1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'anthropic-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'gemini-key')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-3.1-pro-preview')
    monkeypatch.setenv('GOOGLE_GEMINI_BASE_URL', 'https://chatapi.onechats.ai')

    env = control_plane_env()

    assert env['OPENAI_API_KEY'] == 'openai-key'
    assert env['OPENAI_BASE_URL'] == 'https://api.example.test/v1'
    assert env['ANTHROPIC_API_KEY'] == 'anthropic-key'
    assert env['GEMINI_API_KEY'] == 'gemini-key'
    assert env['GEMINI_MODEL'] == 'gemini-3.1-pro-preview'
    assert env['GOOGLE_GEMINI_BASE_URL'] == 'https://chatapi.onechats.ai'


def test_control_plane_env_keeps_user_session_transport_for_cmd_shell(monkeypatch) -> None:
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-0')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/run/user/1000/bus')
    monkeypatch.setenv('XAUTHORITY', '/tmp/.Xauthority')
    monkeypatch.setenv('SSH_AUTH_SOCK', '/tmp/ssh-agent.sock')

    env = control_plane_env()

    assert env['DISPLAY'] == ':0'
    assert env['WAYLAND_DISPLAY'] == 'wayland-0'
    assert env['DBUS_SESSION_BUS_ADDRESS'] == 'unix:path=/run/user/1000/bus'
    assert env['XAUTHORITY'] == '/tmp/.Xauthority'
    assert env['SSH_AUTH_SOCK'] == '/tmp/ssh-agent.sock'
