"""
game_classes/api.py — Thin HTTP client for the CLI Arcade server API.

Configuration
-------------
Set the environment variable CLI_ARCADE_API_URL to the base URL of the server,
e.g.  CLI_ARCADE_API_URL=https://api.example.com

When the variable is not set (or empty), is_enabled() returns False and all
methods return None without making any network calls.  This preserves the
existing local-only behavior for users who do not have a server configured.

Score format (same as local highscores.json)
-------------------------------------------
{
    "score": {"player": "Alice", "value": 12345},
    "level": {"player": "Alice", "value": 10}
}
"""

import os
import warnings

try:
    import requests as _requests
    from requests import Session as _Session
    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None
    _Session = None
    _REQUESTS_AVAILABLE = False

# Timeout in seconds for all API calls.
_TIMEOUT = 5

# Shared session — reuses TCP connections across calls within a process.
_session = None


def _base_url():
    """Return the configured API base URL (stripped of trailing slash), or empty string."""
    return os.environ.get('CLI_ARCADE_API_URL', 'https://brocodetech.com').rstrip('/')


def is_enabled():
    """Return True when a server URL is configured and requests is available."""
    return _REQUESTS_AVAILABLE and bool(_base_url())


def _get_session():
    global _session
    if _session is None and _REQUESTS_AVAILABLE:
        _session = _Session()
    return _session


def get_scores(game=None):
    """
    Fetch high scores from the server.

    Parameters
    ----------
    game : str or None
        If provided, fetch scores for a single game (returns dict of metrics).
        If None, fetch all games (returns dict keyed by game name).

    Returns
    -------
    dict or None
        Parsed JSON response on success, None on failure or when disabled.
    """
    if not is_enabled():
        return None
    base = _base_url()
    url = f'{base}/api/apps/cli-arcade/scores'
    if game:
        url = f'{url}/{game}'
    try:
        session = _get_session()
        resp = session.get(url, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        warnings.warn(f'CLI Arcade API get_scores failed: {e}')
        return None


def save_scores(game, data):
    """
    Save/merge scores for a single game.

    Parameters
    ----------
    game : str
        The game slug (e.g. 'byte_bouncer').
    data : dict
        Score dict in the format ``{metric: {player, value}}``.

    Returns
    -------
    dict or None
        The merged score state returned by the server, or None on failure.
    """
    if not is_enabled():
        return None
    base = _base_url()
    url = f'{base}/api/apps/cli-arcade/scores/{game}'
    try:
        session = _get_session()
        resp = session.post(url, json=data, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        warnings.warn(f'CLI Arcade API save_scores failed: {e}')
        return None
