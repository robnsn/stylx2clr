"""
Background version-checker for stylx2clr.

State machine (module-level, thread-safe):
  idle → checking → up_to_date
                  → available   (download_url is set)
                  → error
"""

import json
import threading
import urllib.request
from pathlib import Path

from version import __version__ as APP_VERSION

_VERSION_URL  = 'https://raw.githubusercontent.com/robnsn/stylx2clr/main/version.txt'
_RELEASES_URL = 'https://github.com/robnsn/stylx2clr/releases/latest'

_PREFS_DIR  = Path.home() / 'Library' / 'Application Support' / 'stylx2clr'
_PREFS_FILE = _PREFS_DIR / 'prefs.json'

_lock = threading.Lock()
_state: dict = {
    # status: idle | checking | up_to_date | available | error
    'status':          'idle',
    'current':         APP_VERSION,
    'latest':          None,
    'download_url':    _RELEASES_URL,
    'error':           None,
    # incremented each time start_check() is called with user_initiated=True
    'user_check_epoch': 0,
}


def _set(**kw) -> None:
    with _lock:
        _state.update(kw)


def get_state() -> dict:
    with _lock:
        state = dict(_state)
    # Attach the persisted dismissed version outside the lock (disk I/O)
    state['dismissed_version'] = _read_dismissed()
    return state


def _parse_ver(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split('.') if x.isdigit())
    except Exception:
        return (0,)


# ── Prefs (dismissed version persisted to disk) ────────────────────────────────

def _read_prefs() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text())
    except Exception:
        return {}


def _write_prefs(data: dict) -> None:
    try:
        _PREFS_DIR.mkdir(parents=True, exist_ok=True)
        _PREFS_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _read_dismissed() -> str | None:
    return _read_prefs().get('dismissed_version')


def dismiss_version(version: str) -> None:
    """Persist the version the user has dismissed so it survives app restarts."""
    prefs = _read_prefs()
    prefs['dismissed_version'] = version
    _write_prefs(prefs)


# ── Public API ────────────────────────────────────────────────────────────────

def start_check(*, user_initiated: bool = False) -> None:
    """Kick off a background version check. Safe to call multiple times.

    Pass user_initiated=True when the check is triggered by an explicit user
    action (e.g. menu-bar "Check for Updates") so the frontend can bypass the
    dismiss state and always show the result.
    """
    with _lock:
        if user_initiated:
            _state['user_check_epoch'] += 1
        _state.update(status='checking', latest=None, error=None)
    threading.Thread(target=_check_worker, daemon=True).start()


# ── Worker (runs in a daemon thread) ─────────────────────────────────────────

def _check_worker() -> None:
    try:
        req = urllib.request.Request(
            _VERSION_URL,
            headers={'User-Agent': 'stylx2clr-updater'},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            latest = r.read().decode().strip()
    except Exception:
        # Network unavailable or transient error — silently give up
        _set(status='idle')
        return

    if _parse_ver(latest) > _parse_ver(APP_VERSION):
        _set(status='available', latest=latest, download_url=_RELEASES_URL)
    else:
        _set(status='up_to_date', latest=latest)
