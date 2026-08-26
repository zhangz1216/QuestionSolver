"""历史收藏夹：自动保存搜题记录，可浏览、删除。

存储：%LOCALAPPDATA%/QuestionSolver/data.db 的 history 表
截图：%LOCALAPPDATA%/QuestionSolver/history/<id>.png
"""
import os
import sqlite3
import time
import uuid
from pathlib import Path

from PySide6.QtGui import QImage

from .questionbank import DB_PATH, DATA_DIR

HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        engine TEXT DEFAULT '',
        model TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        created_at REAL NOT NULL
    )""")
    return conn


def add_record(question: str, answer: str, engine: str = "", model: str = "",
               image: QImage = None) -> int:
    """保存一条搜题记录。返回记录 id。截图自动存为 png。"""
    image_path = ""
    if image is not None and not image.isNull():
        filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
        image_path = str(HISTORY_DIR / filename)
        # 去掉 DPR 影响，按物理像素保存
        img = image
        if img.devicePixelRatio() != 1.0:
            img = image.copy()
            img.setDevicePixelRatio(1.0)
        img.save(image_path, "PNG")
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO history (question, answer, engine, model, image_path, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (question, answer, engine, model, image_path, time.time()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_records(limit: int = 200) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, question, answer, engine, model, image_path, created_at "
            "FROM history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "question": r[1], "answer": r[2], "engine": r[3],
                 "model": r[4], "image_path": r[5], "created_at": r[6]} for r in rows]
    finally:
        conn.close()


def delete_record(record_id: int):
    conn = _connect()
    try:
        row = conn.execute("SELECT image_path FROM history WHERE id=?", (record_id,)).fetchone()
        if row and row[0]:
            try:
                os.remove(row[0])
            except OSError:
                pass
        conn.execute("DELETE FROM history WHERE id=?", (record_id,))
        conn.commit()
    finally:
        conn.close()


def clear_all():
    conn = _connect()
    try:
        rows = conn.execute("SELECT image_path FROM history").fetchall()
        for (p,) in rows:
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass
        conn.execute("DELETE FROM history")
        conn.commit()
    finally:
        conn.close()
