# 悬屏翻译（ScreenTranslator）

一个 Windows 桌面小工具：**框选屏幕上的任意区域，自动识别里面的外语文字并翻译，弹出一张半透明卡片——上半显示你框选的截图，下半显示译文**。

适合翻译那些不能复制粘贴的场景：软件弹窗、通知、游戏界面、图片里的文字等。

## 功能

- 置顶悬浮挂件：可拖到屏幕任意位置（含屏幕边缘），也可最小化到托盘
- 框选翻译：点挂件上的「框选翻译」按钮（或按全局快捷键 `Ctrl+Shift+T`），左键拖拽画框即翻译
- 截图 + 译文卡片：卡片上半显示框选截图（原生比例、原生大小，不缩放），下半显示译文，整体半透明、可拖拽移动
- 自动识别语言：英语 / 日语 / 韩语 / 俄语 等，无需手动选源语言
- 目标语言可选：默认中文，也可选英语、日语、韩语、俄语等 14 种
- 多卡片并存：可同时翻译多处，每张卡片右上角 ✕ 关闭（防误触）
- 自动复制：翻译结果可自动复制到剪贴板（可开关）

## 工作原理

```
框选区域 → 截图 → OCR 识别文字 → 自动识别语言 → 翻译 → 半透明卡片（截图 + 译文）
```

## 技术栈

| 模块 | 方案 |
|---|---|
| UI | Python + PySide6（Qt6） |
| 截图 | QScreen.grabWindow（支持高 DPI、多显示器） |
| OCR | RapidOCR（离线内嵌，无需联网、无需装语言包） |
| 翻译 | 有道 demo → 腾讯 transmart → MyMemory 三路免费回退（无需 API Key，国内可访问，自动识别语言） |
| 打包 | PyInstaller → Inno Setup 安装程序 |

> 说明：Google 翻译免费接口在国内不可达，故采用上述三个国内可访问的免费接口自动回退。

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# 2. 运行
.venv/Scripts/python.exe app.py
```

## 打包

```bash
# 生成应用图标（首次）
.venv/Scripts/python.exe gen_icon.py

# 打包成 exe（onedir，输出到 dist/ScreenTranslator/）
.venv/Scripts/python.exe -m PyInstaller app.spec --noconfirm

# 生成安装程序（需安装 Inno Setup 6）
ISCC.exe setup.iss   # 输出到 installer/
```

## 测试

```bash
.venv/Scripts/python.exe test_translate.py   # 翻译接口（四语识别）
.venv/Scripts/python.exe test_ocr.py         # OCR 识别
.venv/Scripts/python.exe test_capture.py     # 屏幕截图 + OCR
.venv/Scripts/python.exe test_integration.py # 遮罩 + 后台线程 + 全链路
```

## 目录结构

```
TranslatorWidget/
├── app.py                 # 程序入口
├── translator/
│   ├── config.py          # 配置 + 语言定义
│   ├── translate.py       # 翻译（三路免费回退 + 自动识别）
│   ├── ocr.py             # OCR 封装
│   ├── widget.py          # 悬浮挂件
│   ├── selector.py        # 框选覆盖层
│   ├── mask.py            # 截图 + 译文卡片
│   ├── manager.py         # 流程协调 + 后台线程
│   └── hotkey.py          # 全局快捷键
├── app.spec               # PyInstaller 配置
├── setup.iss              # Inno Setup 安装脚本
├── gen_icon.py            # 图标生成脚本
├── icon.ico               # 应用图标
├── test_*.py              # 测试脚本
└── requirements.txt
```

## 说明

- 翻译需要联网（免费接口，偶尔可能限流，已做多路回退 + 重试）
- OCR 离线：英语/中文最稳，日/韩/俄为「够用」级，后续可优化
