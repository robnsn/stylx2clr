# stylx2clr

Convert ArcGIS `.stylx` style files into macOS `.clr` color palette files.
Runs entirely on your machine — your files are never uploaded anywhere.

## Requirements

- macOS (the `.clr` format is macOS-specific)
- Python 3.9+

## Setup

```bash
# Install dependencies (Flask + PyObjC for .clr generation)
pip3 install -r requirements.txt
```

## Usage

```bash
python3 app.py
```

Then open **http://localhost:5000** in your browser.

1. Drop your `.stylx` file onto the page (or click to browse).
2. Review the colour swatches extracted from your symbol definitions.
3. Click **Download .clr Palette** to save the file.

### Installing the palette in macOS

Double-click the downloaded `.clr` file — macOS will install it automatically.
It then appears in the **Color Palettes** section of the system color picker
(accessible in any native app via **Format → Show Colors** or `⇧⌘C`).

Alternatively, copy the file manually to `~/Library/Colors/`.

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
