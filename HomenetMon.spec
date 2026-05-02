# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

# customtkinter ships JSON theme files and images that must travel with the app
datas = collect_data_files('customtkinter')

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'matplotlib.backends.backend_tkagg',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
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
    name='HomenetMon',
    debug=False,
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
    name='HomenetMon',
)

app = BUNDLE(
    coll,
    name='HomenetMon.app',
    icon=None,
    bundle_identifier='com.homenetmon.app',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleName': 'HomenetMon',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,   # respects dark/light mode
        'LSMinimumSystemVersion': '12.0',
    },
)
