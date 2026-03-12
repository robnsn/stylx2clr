"""
Write a macOS .clr (NSColorList) file from a list of colour dicts.

Requires PyObjC on macOS:
    pip3 install pyobjc-framework-Cocoa

The .clr format is an NSColorList archive understood by the macOS system
colour picker and apps such as Sketch, Keynote, and Pages.
"""


def write_clr(colors: list, output_path: str, palette_name: str = 'ArcGIS Palette') -> None:
    """
    Write colors to a .clr file at output_path.

    Args:
        colors: list of dicts with keys r, g, b, a (float 0.0-1.0) and name (str)
        output_path: absolute path for the output .clr file
        palette_name: name shown in the macOS colour picker panel
    """
    try:
        import AppKit  # part of pyobjc-framework-Cocoa
    except ImportError as exc:
        raise RuntimeError(
            'PyObjC is required to generate .clr files.\n'
            'Install it with:  pip3 install pyobjc-framework-Cocoa\n'
            '(macOS only — this matches the .clr format itself)'
        ) from exc

    color_list = AppKit.NSColorList.alloc().initWithName_(palette_name)

    for c in colors:
        # Quantize to 8-bit precision to match the hex roundtrip that occurs
        # when a user manually types a hex code into the macOS color picker.
        r = round(float(c['r']) * 255) / 255.0
        g = round(float(c['g']) * 255) / 255.0
        b = round(float(c['b']) * 255) / 255.0
        ns_color = AppKit.NSColor.colorWithDisplayP3Red_green_blue_alpha_(
            r, g, b, float(c['a']),
        )
        color_list.setColor_forKey_(ns_color, c['name'])

    ok = color_list.writeToFile_(output_path)
    if not ok:
        raise RuntimeError(
            f'NSColorList.writeToFile_ failed for path: '
            f'{"~/Library/Colors/" if output_path is None else output_path}'
        )
