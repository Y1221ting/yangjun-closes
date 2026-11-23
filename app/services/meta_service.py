"""字典数据：场景标签。"""

from __future__ import annotations

import sqlite3

from ..db import get_conn
from ..errors import ServiceError
from ..utils import logger


def list_scenes() -> list[str]:
    """返回全部场景标签，按排序值排列。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT name FROM scenes ORDER BY sort_order, id"
        ).fetchall()
        return [row["name"] for row in rows]
    except sqlite3.Error as exc:
        logger.exception("读取场景标签失败")
        raise ServiceError("读取场景标签失败，请重试") from exc
    finally:
        conn.close()


def add_scene(name: str) -> list[str]:
    """新增自定义场景标签（已存在则忽略）。"""
    text = (name or "").strip()
    if not text:
        raise ServiceError("场景名称不能为空")
    if len(text) > 12:
        raise ServiceError("场景名称最多 12 个字")

    conn = get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO scenes (name, builtin, sort_order) VALUES (?, 0, 99)",
                (text,),
            )
    except sqlite3.Error as exc:
        logger.exception("新增场景标签失败")
        raise ServiceError("新增场景失败，请重试") from exc
    finally:
        conn.close()

    return list_scenes()
