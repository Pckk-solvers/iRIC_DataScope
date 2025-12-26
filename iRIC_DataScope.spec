# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path.cwd()
APP_ENTRY = str(ROOT / "iRIC_DataScope" / "app.py")

datas = collect_data_files('matplotlib')
hiddenimports = [
    'logging.handlers',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'matplotlib.backends.backend_tkagg',
]


a = Analysis(
    [APP_ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='iRIC_DataScope-v1.1.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
