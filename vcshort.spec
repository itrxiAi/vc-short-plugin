# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 把 vcshort 打包成单文件可执行程序。

用法：
    pip install pyinstaller
    pyinstaller vcshort.spec --clean

产物在 dist/vcshort，复制到 bin/vcshort 即可。
"""

block_cipher = None
from PyInstaller.utils.hooks import collect_all

# opencv 和 numpy 是二进制扩展，PyInstaller 静态分析发现不了它们的运行时依赖，
# 必须用 collect_all 强制收集全部文件
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')

a = Analysis(
    ['src/vcshort/__main__.py'],
    pathex=['src'],
    binaries=numpy_binaries + cv2_binaries,
    datas=numpy_datas + cv2_datas,
    hiddenimports=[
        'ruamel.yaml',
        'ruamel.yaml.comments',
        'imageio_ffmpeg',
    ] + numpy_hiddenimports + cv2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='vcshort',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
