# 悬屏搜题

框选屏幕上的任意题目，AI 自动解答（答案 + 完整解题步骤）。支持把教材/试卷/题库导入软件，让 AI 结合资料作答。

基于「悬屏翻译」框架改造：保留了悬浮挂件、框选、OCR 识别，把翻译引擎替换为 AI 搜题引擎。

## 功能

- 全局快捷键（Ctrl+Shift+T）或挂件按钮，框选任意区域的题目
- 自动 OCR 识别题目文字 → AI 解答，返回答案 + 解题步骤 + 知识点提示
- 双引擎省钱策略：
  - 免费引擎（默认）：智谱 GLM-4-Flash 或硅基流动，简单题 0 成本
  - DeepSeek：更准，带题库学习或点「深度重搜」时使用（按量付费，本身很便宜）
- 题库管理：导入 PDF / Word / TXT / 图片（扫描版 PDF 自动转图片识别），AI 搜题时自动检索最相关的资料片段（纯本地计算，不花钱）；也可指定只看某一份资料
- 结果小卡片 + 一键放大完整面板，文字可部分选中复制
- 「识别不准？改题重搜」：OCR 把公式识别错时，直接修改题目文本重新搜
- 历史收藏夹：自动保存搜题记录（含截图），可翻看、删除
- 全屏应用内框选（游戏/全屏网课）：可切回桌面显示结果，或选择截全屏模式不打断

## 快速开始（开发运行）

```bash
# 1. 创建虚拟环境并安装依赖
uv venv .venv
uv pip install --python ./.venv/Scripts/python.exe -r requirements.txt

# 2. 运行
./.venv/Scripts/python.exe app.py
```

首次使用：点挂件上的 ⚙ 打开设置，填入 API Key：

| 引擎 | 获取方式 | 成本 |
|---|---|---|
| 免费引擎 | 智谱开放平台 open.bigmodel.cn 或硅基流动 cloud.siliconflow.cn 免费注册 | 0 元 |
| DeepSeek | platform.deepseek.com 充值 | 按量，极便宜 |

设置里点「探测免费引擎可用性」可自动选择可用的免费平台。

## 测试引擎连通性（不用开界面）

```bash
./.venv/Scripts/python.exe test_engine.py
# 或指定参数：
./.venv/Scripts/python.exe test_engine.py --provider deepseek --key sk-xxxx
```

## 打包

```bash
# PyInstaller 生成 onedir
./.venv/Scripts/pyinstaller.exe app.spec

# Inno Setup 打安装包（安装 Inno Setup 6 后）
ISCC.exe setup.iss
```

## 数据存储

- 配置（API Key、引擎选择）：注册表 `HKCU\Software\QuestionSolver`
- 题库与历史记录：`%LOCALAPPDATA%\QuestionSolver\data.db`（SQLite）
- 历史截图：`%LOCALAPPDATA%\QuestionSolver\history\`
- 调试日志：`%LOCALAPPDATA%\QuestionSolver\debug.log`

题目和题库文本仅发送给你配置的 AI 服务（DeepSeek/免费平台），无其他上传。

## 注意事项

- 搜题需要联网（调用 AI 服务）
- AI 解答仅供参考，理科公式题若 OCR 识别不准，用「改题重搜」修正
- DeepSeek 深度思考（reasoner）模式更准但更慢，用于难题
