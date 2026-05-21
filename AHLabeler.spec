# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')

a = Analysis(
    ['player_gui.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=qt_datas + [('README.txt', '.')],
    hiddenimports=qt_hiddenimports + collect_submodules('cv2') + [
        'numpy',
        'pandas',
        'csv',
        'json',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AHLabeler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AHLabeler',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AHLabeler.app',
        icon=None,
        bundle_identifier='com.airhockey.ahlabeler',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.2',
        },
    )
