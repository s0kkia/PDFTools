# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.api import Splash

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("PDFTools.ico", ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pdftools/runtime/splash_hook.py"],
    excludes=[],
    noarchive=False,
    optimize=0,
)

splash = Splash(
    "build_assets/splash.png",
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(240, 275),
    text_size=16,
    text_color="#e8eaf0",
    text_font="Segoe UI",
    text_default="Ну потерпи ещё чуточку…",
    always_on_top=True,
    center="active",
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    [],
    name="PDFTools",
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
