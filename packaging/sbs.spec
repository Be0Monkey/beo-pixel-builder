# -*- mode: python ; coding: utf-8 -*-
# Paquet Windows « dossier » : dist/SpriteBuilderStudio/
#   SpriteBuilderStudio.exe          application (sans console)
#   SpriteBuilderStudio-console.exe  même programme avec console (pour --selftest / --version)
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "src" / "sbs" / "resources"), "sbs/resources")],
    hiddenimports=["sqlite3"],
    excludes=["tkinter", "pytest", "numpy.testing", "PIL.ImageTk",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SpriteBuilderStudio",
              console=False, debug=False, strip=False, upx=False)
exe_cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SpriteBuilderStudio-console",
              console=True, debug=False, strip=False, upx=False)

coll = COLLECT(exe_gui, exe_cli, a.binaries, a.datas, strip=False, upx=False, name="SpriteBuilderStudio")
