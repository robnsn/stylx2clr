# stylx2clr

Convert ArcGIS `.stylx` style files into macOS `.clr` color palette files.
Runs entirely on your machine — your files are never uploaded anywhere.

> **Note:** The `.clr` format is macOS-specific. Generating palette files
> requires macOS. Any platform can run the app to preview colours.

---

## Option A — Standalone app (recommended for teams)

Download `stylx2clr.dmg` from the Releases page, open it, and double-click
`stylx2clr.app`. The app opens in its own window — no browser tab.

To quit: **⌘Q** or right-click the Dock icon → **Quit**.

---

## Option B — Run from source

### Requirements

- Python 3.9+
- macOS (for `.clr` generation; colour preview works on any OS)

### Setup

```bash
pip3 install -r requirements.txt
python3 app.py
# Opens in its own window via pywebview
```

---

## Building the binary yourself

You need a Mac to build (and to use — the `.clr` format is macOS-specific).

```bash
git pull

# Create a throw-away virtual environment (avoids PATH / permission issues)
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements-build.txt
pyinstaller stylx2clr.spec

# Package as a DMG (hdiutil is built into macOS — no extra tools needed)
hdiutil create -volname "stylx2clr" \
  -srcfolder dist/stylx2clr.app \
  -ov -format UDZO \
  dist/stylx2clr.dmg

deactivate
```

Share `dist/stylx2clr.dmg`. Recipients open the DMG, double-click the app —
no Python, no browser, no setup required. The app opens in its own window.

**Tip:** To add a custom Dock icon, place a `stylx2clr.icns` file next to
`app.py` before building and set `icon='stylx2clr.icns'` in the spec.

---

## Usage

1. Drop your `.stylx` file onto the page (or click to browse).
2. Review the colour swatches extracted from your symbol definitions.
3. Click **Download .clr Palette** to save the file.

### Installing the palette in macOS

Double-click the downloaded `.clr` file — macOS will install it automatically.
It then appears in the **Color Palettes** section of the system color picker
(accessible in any native app via **Format → Show Colors** or `⇧⌘C`).

Alternatively, copy the file manually to `~/Library/Colors/`.

---

## What gets extracted

The converter reads every symbol in the `.stylx` file and extracts colours
from all symbol layers it finds:

| CIM layer type | Label in palette |
|---|---|
| `CIMSolidFill`, `CIMGradientFill` | Fill |
| `CIMSolidStroke`, `CIMGradientStroke` | Stroke |
| `CIMHatchFill` | Hatch |
| `CIMCharacterMarker`, `CIMVectorMarker`, `CIMPictureMarker` | Marker |

Supported CIM colour models: RGB, CMYK, HSV, HSL, Grayscale.

When a symbol has multiple colours with the same label, they are numbered
`(1)`, `(2)`, … to keep every swatch name unique.
