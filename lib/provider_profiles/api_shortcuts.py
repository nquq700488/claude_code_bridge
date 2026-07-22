from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from provider_custom.wiring import CustomProviderWiring, custom_provider_names, custom_provider_wiring


_PROVIDER_API_SHORTCUT_ENV = {
    'codex': {
        'key': 'OPENAI_API_KEY',
        'url': 'OPENAI_BASE_URL',
    },
    'claude': {
        'key': 'ANTHROPIC_API_KEY',
        'url': 'ANTHROPIC_BASE_URL',
    },
    'gemini': {
        'key': 'GEMINI_API_KEY',
        'url': 'GOOGLE_GEMINI_BASE_URL',
    },
    'kimi': {
        'key': 'MOONSHOT_API_KEY',
        'url': 'MOONSHOT_BASE_URL',
    },
    'mmx': {
        'key': 'MINIMAX_API_KEY',
        'url': 'MINIMAX_BASE_URL',
    },
    'deepseek': {
        'key': 'DEEPCODE_API_KEY',
        'url': 'DEEPCODE_BASE_URL',
    },
}


def provider_api_shortcut_env(provider: str, *, key: str | None = None, url: str | None = None) -> dict[str, str]:
    normalized_provider = str(provider or '').strip().lower()
    wiring = custom_provider_wiring(normalized_provider)
    if wiring is not None:
        return _custom_api_shortcut_env(wiring, key=key, url=url)
    mapping = _PROVIDER_API_SHORTCUT_ENV.get(normalized_provider)
    if mapping is None:
        supported = ', '.join(supported_provider_api_shortcuts())
        raise ValueError(f'api shortcut is supported only for providers: {supported}')
    env: dict[str, str] = {}
    if str(key or '').strip():
        env[mapping['key']] = str(key).strip()
    if str(url or '').strip():
        env[mapping['url']] = _normalized_shortcut_url(normalized_provider, str(url).strip())
    return env


def _custom_api_shortcut_env(
    wiring: CustomProviderWiring,
    *,
    key: str | None,
    url: str | None,
) -> dict[str, str]:
    if key and not wiring.key_env:
        raise ValueError(f'custom provider {wiring.provider} does not declare key_env wiring')
    if url and not wiring.url_env:
        raise ValueError(f'custom provider {wiring.provider} does not declare url_env wiring')
    env: dict[str, str] = {}
    if key and wiring.key_env:
        env[wiring.key_env] = str(key)
    if url and wiring.url_env:
        env[wiring.url_env] = str(url)
    return env


def _normalized_shortcut_url(provider: str, url: str) -> str:
    if provider != 'codex':
        return url
    try:
        parsed = urlsplit(url)
    except Exception:
        return url
    if not parsed.scheme or not parsed.netloc:
        return url
    path = parsed.path or ''
    if path in {'', '/'}:
        path = '/v1'
    elif path == '/v1/':
        path = '/v1'
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def supported_provider_api_shortcuts() -> tuple[str, ...]:
    names = set(_PROVIDER_API_SHORTCUT_ENV)
    for name in custom_provider_names():
        wiring = custom_provider_wiring(name)
        if wiring is not None and (wiring.key_env or wiring.url_env):
            names.add(name)
    return tuple(sorted(names))


__all__ = ['provider_api_shortcut_env', 'supported_provider_api_shortcuts']
