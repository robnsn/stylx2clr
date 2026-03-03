# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for stylx2clr — produces a macOS .app bundle.
#
# Build:
#   pyinstaller stylx2clr.spec
#
# Then package as DMG:
#   hdiutil create -volname "stylx2clr" -srcfolder dist/stylx2clr.app -ov -format UDZO dist/stylx2clr.dmg

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
        'webview',
        'webview.menu',
        'webview.platforms.cocoa',
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
        'CFBundleShortVersionString': '1.1.5',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
    },
)
