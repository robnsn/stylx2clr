# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for stylx2clr — produces a macOS .app bundle.
#
# Build:
#   pyinstaller stylx2clr.spec
#
# Output:  dist/stylx2clr.app
# Distribute:  zip -r stylx2clr.zip dist/stylx2clr.app && share the zip

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
    ],
    hiddenimports=[
        'flask',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stylx2clr',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stylx2clr',
)

app = BUNDLE(
    coll,
    name='stylx2clr.app',
    icon=None,              # drop a stylx2clr.icns here to add a custom icon
    bundle_identifier='com.yourorg.stylx2clr',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    },
)
