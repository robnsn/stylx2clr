"""
Parse an ArcGIS .stylx file and extract colors from CIM symbol definitions.

.stylx files are SQLite databases. Each row in the Items table has a Content
column containing CIM (Cartographic Information Model) JSON that describes a
symbol. Colors are embedded at various depths inside those JSON trees.
"""

import json
import sqlite3
import colorsys
from collections import Counter

# CIM color model types we know how to convert
_CIM_COLOR_TYPES = frozenset({
    'CIMRGBColor',
    'CIMCMYKColor',
    'CIMHSVColor',
    'CIMHSLColor',
    'CIMGrayColor',
})

# Symbol-layer types → human-readable label used in the color name
_LAYER_LABELS = {
    'CIMSolidFill':       'Fill',
    'CIMGradientFill':    'Fill',
    'CIMHatchFill':       'Hatch',
    'CIMPictureFill':     'Picture Fill',
    'CIMSolidStroke':     'Stroke',
    'CIMGradientStroke':  'Stroke',
    'CIMPictureStroke':   'Picture Stroke',
    'CIMCharacterMarker': 'Marker',
    'CIMVectorMarker':    'Marker',
    'CIMPictureMarker':   'Marker',
    'CIMSimpleMarker':    'Marker',
}


def _cim_to_rgba(color_obj: dict):
    """
    Convert a CIM color dict to (r, g, b, a) in the 0.0–1.0 range.
    Returns None if the color type is unrecognised or values are missing.

    CIM encoding notes:
      CIMRGBColor  : values = [R 0-255, G 0-255, B 0-255, A 0-100]
      CIMGrayColor : values = [gray 0-100, A 0-100]
      CIMCMYKColor : values = [C 0-100, M 0-100, Y 0-100, K 0-100, A 0-100]
      CIMHSVColor  : values = [H 0-360, S 0-100, V 0-100, A 0-100]
      CIMHSLColor  : values = [H 0-360, S 0-100, L 0-100, A 0-100]
    """
    t = color_obj.get('type')
    v = color_obj.get('values')
    if not v:
        return None

    if t == 'CIMRGBColor' and len(v) >= 4:
        return (v[0] / 255.0, v[1] / 255.0, v[2] / 255.0, v[3] / 100.0)

    if t == 'CIMGrayColor' and len(v) >= 2:
        gray = v[0] / 100.0
        return (gray, gray, gray, v[1] / 100.0)

    if t == 'CIMCMYKColor' and len(v) >= 5:
        c, m, y, k, a = (x / 100.0 for x in v[:5])
        r = (1.0 - c) * (1.0 - k)
        g = (1.0 - m) * (1.0 - k)
        b = (1.0 - y) * (1.0 - k)
        return (r, g, b, a)

    if t == 'CIMHSVColor' and len(v) >= 4:
        h, s, vv, a = v[0] / 360.0, v[1] / 100.0, v[2] / 100.0, v[3] / 100.0
        r, g, b = colorsys.hsv_to_rgb(h, s, vv)
        return (r, g, b, a)

    if t == 'CIMHSLColor' and len(v) >= 4:
        h, s, l, a = v[0] / 360.0, v[1] / 100.0, v[2] / 100.0, v[3] / 100.0
        # colorsys.hls_to_rgb expects (h, l, s)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return (r, g, b, a)

    return None


def _walk(node, symbol_name: str, layer_label, results: list):
    """Recursively walk a CIM JSON node and collect color records."""
    if isinstance(node, list):
        for item in node:
            _walk(item, symbol_name, layer_label, results)
        return

    if not isinstance(node, dict):
        return

    obj_type = node.get('type', '')

    # Colour leaf — convert and record, then stop descending
    if obj_type in _CIM_COLOR_TYPES:
        rgba = _cim_to_rgba(node)
        if rgba is not None:
            r, g, b, a = rgba
            hex_color = '#{:02x}{:02x}{:02x}'.format(
                round(r * 255), round(g * 255), round(b * 255)
            )
            label = f'{symbol_name} – {layer_label}' if layer_label else symbol_name
            results.append({
                'name': label,
                'r': r,
                'g': g,
                'b': b,
                'a': a,
                'hex': hex_color,
            })
        return  # don't recurse into a colour node

    # Update context label if entering a known symbol-layer type
    new_label = _LAYER_LABELS.get(obj_type, layer_label)

    for value in node.values():
        _walk(value, symbol_name, new_label, results)


def _disambiguate_names(colors: list) -> None:
    """
    When multiple colors share the same name, append ' (1)', ' (2)', … to
    each occurrence so every swatch in the palette has a unique key.
    Mutates the dicts in-place.
    """
    counts = Counter(c['name'] for c in colors)
    seen: dict[str, int] = {}
    for c in colors:
        base = c['name']
        if counts[base] > 1:
            seen[base] = seen.get(base, 0) + 1
            c['name'] = f'{base} ({seen[base]})'


def parse_stylx(path: str) -> list:
    """
    Open a .stylx file and return a list of colour dicts.

    Each dict contains:
        name   – swatch label (symbol name + layer context)
        group  – category string from the Category column (or '' if absent)
        r, g, b, a  – float 0.0–1.0
        hex    – '#rrggbb' string for preview
    """
    results: list = []

    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    except sqlite3.OperationalError as exc:
        raise ValueError(f'Cannot open file: {exc}') from exc

    try:
        cur = conn.cursor()

        # Check whether the Items table has a Category column (most .stylx files do)
        try:
            cur.execute('PRAGMA table_info(Items)')
            has_category = any(row[1] == 'Category' for row in cur.fetchall())
        except sqlite3.OperationalError:
            has_category = False

        try:
            if has_category:
                cur.execute('SELECT Name, Category, Content FROM Items')
            else:
                cur.execute('SELECT Name, Content FROM Items')
        except sqlite3.OperationalError as exc:
            raise ValueError(
                f'Not a valid .stylx file (missing Items table): {exc}'
            ) from exc

        for row in cur.fetchall():
            if has_category:
                name, category, content = row
            else:
                name, content = row
                category = None

            if not content:
                continue
            try:
                data = json.loads(content.rstrip('\x00'))
            except (json.JSONDecodeError, TypeError):
                continue

            # Use Category if present, otherwise fall back to the symbol name
            # so colors from the same symbol are at least grouped together.
            group = (category or name or 'Unnamed').strip()
            item_colors: list = []
            _walk(data, name or 'Unnamed', None, item_colors)
            for c in item_colors:
                c['group'] = group
            results.extend(item_colors)

    finally:
        conn.close()

    _disambiguate_names(results)
    return results
