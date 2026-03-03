# stylx2clr

Convert ArcGIS `.stylx` style files into macOS `.clr` color palette files.
Runs entirely on your machine — your files are never uploaded anywhere.

> **Note:** The `.clr` format is macOS-specific. Generating palette files
> requires macOS. Any platform can run the app to preview colours.

---

## Option A — Standalone binary (recommended for teams)

Download the pre-built `stylx2clr` binary from the Releases page, then:

```
# macOS
chmod +x stylx2clr
./stylx2clr
```

The app opens your browser automatically. Close the terminal window to quit.

---

## Option B — Run from source

### Requirements

- Python 3.9+
- macOS (for `.clr` generation; colour preview works on any OS)

### Setup

```bash
pip3 install -r requirements.txt
python3 app.py
```

---

## Building the binary yourself

You need a Mac to produce a binary that can generate `.clr` files.

```bash
pip3 install -r requirements-build.txt
pyinstaller stylx2clr.spec
```

The finished binary is at `dist/stylx2clr`. Zip it up and share it with your
team — no Python installation required on their machines.

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
