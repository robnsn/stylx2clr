"""
stylx2clr — local web app
Run with:  python3 app.py
Then open: http://localhost:5000
"""

import atexit
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from clr_writer import write_clr
from stylx_parser import parse_stylx

app = Flask(__name__)
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
    print('stylx2clr is running.')
    print('Open http://localhost:5000 in your browser.')
    print('Press Ctrl+C to stop.')
    app.run(host='127.0.0.1', port=5000, debug=False)
