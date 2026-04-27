from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(SPECPATH).resolve().parent
hiddenimports = collect_submodules("pynput")
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")
shiboken6_datas, shiboken6_binaries, shiboken6_hiddenimports = collect_all("shiboken6")
hiddenimports += pyside6_hiddenimports + shiboken6_hiddenimports
binaries = pyside6_binaries + shiboken6_binaries
datas = pyside6_datas + shiboken6_datas

a = Analysis(
    [str(project_root / "src" / "crossping" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="CrossPing",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
