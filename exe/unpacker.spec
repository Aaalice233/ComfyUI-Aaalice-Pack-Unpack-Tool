# -*- mode: python ; coding: utf-8 -*-
"""
ComfyUI Workflow Unpacker - PyInstaller Specification File
用于打包 unpacker_gui.py 为独立 EXE 文件
"""

import sys
from pathlib import Path

# 获取项目根目录
root_dir = Path(SPECPATH).parent
src_dir = root_dir / 'src'

block_cipher = None

a = Analysis(
    ['run_dev.py'],
    pathex=[str(src_dir), str(root_dir)],
    binaries=[],
    datas=[
        # 包含 src 目录中的所有文件
        (str(src_dir / 'comfy_pack'), 'comfy_pack'),
        # 确保图标文件被包含
        (str(root_dir / 'icon.ico'), '.'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'comfy_pack.unpacker_core',
        'comfy_pack.unpacker_gui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'torch',
        'torchvision',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='comfy-pack-unpack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root_dir / 'icon.ico'),
)