"""
stylx2clr — local web app
Run with:  python3 app.py  (or double-click the standalone binary)
"""

import atexit
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import updater as _updater
from flask import Flask, jsonify, render_template, request

from clr_writer import write_clr
from stylx_parser import parse_stylx

# When frozen by PyInstaller, data files live under sys._MEIPASS
_BASE_DIR = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(_BASE_DIR, 'templates'))
app.config['MAX_CONTENT_LENGTH'] = 256 * 1024 * 1024  # 256 MB upload limit

# Temp directory shared across the session; cleaned up on exit
_TEMP_DIR = tempfile.mkdtemp(prefix='stylx2clr_')
atexit.register(shutil.rmtree, _TEMP_DIR, ignore_errors=True)

# token → (stylx_path, palette_name)
_uploads: dict[str, tuple[str, str]] = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """
    Accept a .stylx file, parse its colours, and return a JSON preview.
    Also stores the file temporarily so /download/<token> can generate the .clr.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file in request.'}), 400

    f = request.files['file']
    if not f.filename or not f.filename.lower().endswith('.stylx'):
        return jsonify({'error': 'Please upload a .stylx file.'}), 400

    token = str(uuid.uuid4())
    stylx_path = os.path.join(_TEMP_DIR, f'{token}.stylx')
    f.save(stylx_path)

    try:
        colors = parse_stylx(stylx_path)
    except ValueError as exc:
        os.unlink(stylx_path)
        return jsonify({'error': str(exc)}), 422

    palette_name = Path(f.filename).stem
    _uploads[token] = (stylx_path, palette_name)

    # Group colors by their Category (preserving order of first appearance)
    seen: list = []
    buckets: dict = {}
    for color in colors:
        g = color.get('group') or ''
        if g not in buckets:
            buckets[g] = []
            seen.append(g)
        buckets[g].append(color)

    if len(seen) == 1 and seen[0] == '':
        # No Category column — present everything as one unlabelled group
        groups = [{'name': palette_name, 'colors': buckets['']}]
    else:
        groups = [{'name': g or 'Other', 'colors': buckets[g]} for g in seen]

    return jsonify({
        'token': token,
        'palette_name': palette_name,
        'count': len(colors),
        'groups': groups,
    })


# ── Update routes ─────────────────────────────────────────────────────────────

@app.route('/update/status')
def update_status():
    """Return the current state of the background updater."""
    return jsonify(_updater.get_state())


@app.route('/update/install', methods=['POST'])
def update_install():
    """Swap in the downloaded update and exit so the install script can relaunch."""
    try:
        _updater.install_and_relaunch()  # does not return — calls os._exit(0)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    return jsonify({'ok': True})  # unreachable, but satisfies type checkers


# ── Debug / download ──────────────────────────────────────────────────────────

@app.route('/debug/<token>')
def debug(token):
    """Return diagnostic info about the raw .stylx content to help troubleshoot parsing."""
    import sqlite3, json

    if token not in _uploads:
        return jsonify({'error': 'Token not found. Re-upload the file first.'}), 404

    stylx_path, _ = _uploads[token]
    result = {}

    try:
        conn = sqlite3.connect(f'file:{stylx_path}?mode=ro', uri=True)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        result['tables'] = [r[0] for r in cur.fetchall()]

        try:
            cur.execute('PRAGMA table_info(Items)')
            result['items_columns'] = [r[1] for r in cur.fetchall()]
        except Exception as e:
            result['items_columns_error'] = str(e)

        try:
            cur.execute('SELECT COUNT(*) FROM Items')
            result['row_count'] = cur.fetchone()[0]
        except Exception:
            result['row_count'] = 'unknown'

        try:
            cur.execute('SELECT Name, Content FROM Items LIMIT 1')
            row = cur.fetchone()
            if row:
                name, content = row
                result['sample_name'] = name
                result['sample_content_snippet'] = (content or '')[:500]
                try:
                    data = json.loads(content)
                    result['sample_top_level_keys'] = list(data.keys()) if isinstance(data, dict) else f'type={type(data).__name__}'
                    types_found = []
                    def collect_types(node):
                        if isinstance(node, dict):
                            if 'type' in node:
                                types_found.append(node['type'])
                            for v in node.values():
                                collect_types(v)
                        elif isinstance(node, list):
                            for item in node:
                                collect_types(item)
                    collect_types(data)
                    result['all_type_values_in_first_row'] = sorted(set(types_found))
                except Exception as e:
                    result['json_parse_error'] = str(e)
        except Exception as e:
            result['sample_error'] = str(e)

        conn.close()
    except Exception as e:
        result['db_error'] = str(e)

    return jsonify(result)


@app.route('/download/<token>')
def download(token):
    """
    Generate the .clr file, save it to ~/Downloads, and reveal it in Finder.
    Returns JSON instead of a file stream — pywebview's WebKit does not support
    blob-URL downloads, so we handle the save on the Python side.
    """
    if token not in _uploads:
        return jsonify({'error': 'Session not found. Please re-upload the file.'}), 404

    stylx_path, palette_name = _uploads[token]

    if not os.path.exists(stylx_path):
        return jsonify({'error': 'Temp file is gone. Please re-upload.'}), 404

    clr_path = stylx_path.replace('.stylx', '.clr')

    try:
        colors = parse_stylx(stylx_path)
        write_clr(colors, clr_path, palette_name=palette_name)
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 500
    except Exception as exc:
        return jsonify({'error': f'Conversion failed: {exc}'}), 500

    colors_dir = Path.home() / 'Library' / 'Colors'
    colors_dir.mkdir(parents=True, exist_ok=True)
    save_path = colors_dir / f'{palette_name}.clr'

    # Avoid clobbering an existing file
    counter = 1
    while save_path.exists():
        save_path = colors_dir / f'{palette_name} ({counter}).clr'
        counter += 1

    try:
        shutil.copy2(clr_path, str(save_path))
        return jsonify({'filename': save_path.name, 'saved_to': str(save_path)})
    except Exception as exc:
        return jsonify({'error': f'Failed to save file: {exc}'}), 500


if __name__ == '__main__':
    import socket
    import threading
    import time
    import webview

    def _free_port(start: int = 5000) -> int:
        """Return the first free TCP port at or after start."""
        for port in range(start, start + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except OSError:
                    continue
        return start

    port = _free_port()
    url = f'http://localhost:{port}'

    # Flask runs in a daemon thread — dies automatically when the window closes
    threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    time.sleep(0.5)  # let Flask start before the window tries to load

    # Kick off the background update check now that Flask is ready to serve /update/status
    _updater.start_check()

    webview.create_window('stylx2clr', url, width=960, height=700, min_size=(600, 500))
    webview.start()  # blocks until the window is closed, then the process exits
