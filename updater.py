"""
Background version-checker for stylx2clr.

State machine (module-level, thread-safe):
  idle → checking → up_to_date
                  → available   (download_url is set)
                  → error
"""

import threading
import urllib.request

from version import __version__ as APP_VERSION

_VERSION_URL  = 'https://raw.githubusercontent.com/robnsn/stylx2clr/main/version.txt'
_RELEASES_URL = 'https://github.com/robnsn/stylx2clr/releases/latest'

_lock = threading.Lock()
_state: dict = {
    'status':       'idle',
    'current':      APP_VERSION,
    'latest':       None,
    'download_url': _RELEASES_URL,
    'error':        None,
}


def _set(**kw) -> None:
    with _lock:
        _state.update(kw)


def get_state() -> dict:
    with _lock:
        return dict(_state)


def _parse_ver(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split('.') if x.isdigit())
    except Exception:
        return (0,)


def start_check() -> None:
    """Kick off a background version check. Called once on app startup."""
    with _lock:
        _state.update(status='checking', latest=None, error=None)
    threading.Thread(target=_check_worker, daemon=True).start()


def _check_worker() -> None:
    try:
        req = urllib.request.Request(
            _VERSION_URL,
            headers={'User-Agent': 'stylx2clr-updater'},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            latest = r.read().decode().strip()
    except Exception:
        _set(status='idle')
        return

    if _parse_ver(latest) > _parse_ver(APP_VERSION):
        _set(status='available', latest=latest, download_url=_RELEASES_URL)
    else:
        _set(status='up_to_date', latest=latest)
