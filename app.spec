# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成 onedir 目录（后续用 Inno Setup 打成安装程序）。"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# RapidOCR 模型/config + onnxruntime 动态库，全部收集
for pkg in ("rapidocr_onnxruntime", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# 题库解析依赖：pymupdf（PDF）、docx（Word）、jieba（分词词库）
for pkg in ("pymupdf", "docx", "jieba"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2",
              "IPython", "jedi", "pytest", "pandas", "scipy"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuestionSolver",
    icon="icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
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
    upx=False,
    upx_exclude=[],
    name="QuestionSolver",
)
