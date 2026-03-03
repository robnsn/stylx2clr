"""
Background auto-updater for stylx2clr.

State machine (module-level, thread-safe):
  idle → checking → up_to_date
                  → available → downloading → ready → (install_and_relaunch exits)
                                            → error
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from version import __version__ as APP_VERSION

_VERSION_URL = 'https://raw.githubusercontent.com/robnsn/stylx2clr/main/version.txt'
_RELEASES_API = 'https://api.github.com/repos/robnsn/stylx2clr/releases/latest'

_lock = threading.Lock()
_state: dict = {
    # status: idle | checking | up_to_date | available | downloading | ready | error
    'status':     'idle',
    'current':    APP_VERSION,
    'latest':     None,
    'progress':   0.0,   # 0.0–1.0 during download
    'error':      None,
    'new_app_path': None,
    'is_frozen':  getattr(sys, 'frozen', False),
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


def _app_bundle_path() -> 'Path | None':
    """
    Return the .app bundle path when running as a PyInstaller-frozen app.
    sys.executable is at   MyApp.app/Contents/MacOS/MyApp
    so .parent.parent.parent gives  MyApp.app
    """
    if not getattr(sys, 'frozen', False):
        return None
    return Path(sys.executable).parent.parent.parent


# ── Public API ────────────────────────────────────────────────────────────────

def start_check() -> None:
    """Kick off a background version check. Call once at app startup."""
    _set(status='checking')
    threading.Thread(target=_check_worker, daemon=True).start()


def install_and_relaunch() -> None:
    """
    Write a shell script that swaps the old .app for the downloaded one,
    then exit this process. The script relaunches the new version.
    Only works when running as a frozen .app bundle.
    """
    st = get_state()
    new_app = st.get('new_app_path')
    old_app = _app_bundle_path()

    if not new_app or not old_app:
        raise RuntimeError(
            'Cannot auto-install: either the download is not complete '
            'or the app is not running as a frozen .app bundle.'
        )

    # Remove the quarantine attribute so macOS doesn't block the new build
    subprocess.run(
        ['xattr', '-dr', 'com.apple.quarantine', new_app],
        capture_output=True,
    )

    # Shell script runs after we exit: remove old app, copy new one, relaunch
    script = (
        '#!/bin/bash\n'
        'sleep 1\n'
        f'rm -rf {shlex.quote(str(old_app))}\n'
        f'cp -R {shlex.quote(new_app)} {shlex.quote(str(old_app))}\n'
        f'open {shlex.quote(str(old_app))}\n'
    )
    script_path = os.path.join(tempfile.gettempdir(), 'stylx2clr_install.sh')
    with open(script_path, 'w') as fh:
        fh.write(script)
    os.chmod(script_path, 0o755)

    # Launch as a completely detached process so it outlives us
    subprocess.Popen(['bash', script_path], close_fds=True, start_new_session=True)

    # Exit immediately; the install script will relaunch us
    os._exit(0)


# ── Workers (run in daemon threads) ───────────────────────────────────────────

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
        _set(status='available', latest=latest)
        # Only auto-download when running as a built .app — pointless for source runs
        if getattr(sys, 'frozen', False):
            threading.Thread(target=_download_worker, daemon=True).start()
    else:
        _set(status='up_to_date', latest=latest)


def _download_worker() -> None:
    _set(status='downloading', progress=0.0)
    try:
        # 1. Fetch the GitHub releases API to get the asset download URL
        req = urllib.request.Request(
            _RELEASES_API,
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'stylx2clr-updater',
            },
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            release = json.loads(r.read())

        asset_url = next(
            (a['browser_download_url'] for a in release.get('assets', [])
             if a['name'].lower().endswith('.zip')),
            None,
        )
        if not asset_url:
            raise RuntimeError(
                'The latest GitHub release has no .zip asset. '
                'Please upload stylx2clr.zip when creating the release.'
            )

        tmp = tempfile.mkdtemp(prefix='stylx2clr_update_')
        zip_path = os.path.join(tmp, 'update.zip')

        # 2. Stream the download, updating progress as we go
        req2 = urllib.request.Request(
            asset_url,
            headers={'User-Agent': 'stylx2clr-updater'},
        )
        with urllib.request.urlopen(req2, timeout=180) as r:
            total = int(r.headers.get('Content-Length') or 0)
            done = 0
            with open(zip_path, 'wb') as f:
                while chunk := r.read(65536):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        _set(progress=done / total)

        # 3. Extract and locate the .app inside the zip
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)

        new_app = next(
            (p for p in Path(tmp).iterdir() if p.suffix == '.app'),
            None,
        )
        if not new_app:
            raise RuntimeError('Downloaded zip contained no .app bundle.')

        _set(status='ready', progress=1.0, new_app_path=str(new_app))

    except Exception as exc:
        _set(status='error', error=str(exc))
