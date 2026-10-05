# -*- mode: python ; coding: utf-8 -*-
"""Onefile windowed build of Furniture Time Tracker."""

import sys
from pathlib import Path

root = Path(SPECPATH)
excludes = ["pytest", "tkinter"]
if sys.platform == "win32":
    excludes.append("pynput")

a = Analysis(
    [str(root / "src" / "furniture_timer" / "__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="FurnitureTimer",
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
    icon=str(root / "assets" / "furniture_timer.ico"),
)
