"""简单的文件日志，用于诊断游戏模式等难以看到 UI 反馈的场景。

日志文件：%LOCALAPPDATA%\\QuestionSolver\\debug.log
"""
import os
import time


def log(msg: str):
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        path = os.path.join(base, "QuestionSolver", "debug.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:  # noqa: BLE001
        pass
