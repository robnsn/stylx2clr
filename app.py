"""
stylx2clr — local web app
Run with:  python3 app.py  (or double-click the standalone binary)
Then open: http://localhost:5000  (browser opens automatically)
"""

import atexit
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

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

    return jsonify({
        'token': token,
        'palette_name': palette_name,
        'count': len(colors),
        'colors': colors,
    })


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
    """Generate and serve the .clr file for a previously uploaded .stylx."""
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

    return send_file(
        clr_path,
        as_attachment=True,
        download_name=f'{palette_name}.clr',
        mimetype='application/octet-stream',
    )


if __name__ == '__main__':
    import socket
    import threading
    import webbrowser

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
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f'stylx2clr  →  {url}')
    print('Close this window (or press Ctrl+C) to quit.')
    app.run(host='127.0.0.1', port=port, debug=False)
