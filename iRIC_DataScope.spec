# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.splash import Splash

ROOT = Path.cwd()
APP_ENTRY = str(ROOT / "main.py")
SPLASH_PATH = str(ROOT / "iRIC_DataScope" / "assets" / "splash.png")

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

# Splash設定
splash = Splash(
    SPLASH_PATH,
    binaries=a.binaries,
    datas=a.datas,
    always_on_top=False,
    # text_pos=(10, 50),  # onefile解凍中のテキスト出したいなら
)

exe = EXE(
    pyz,
    a.scripts,

    splash,          # ← これを “引数として混ぜる”
    splash.binaries, # ← onefileならEXE側に入れる（重要）

    a.binaries,
    a.zipfiles,      # ← ここ、[]じゃなく a.zipfiles が一般的
    a.datas,
    [],
    name='iRIC_DataScope-v1.1.3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
