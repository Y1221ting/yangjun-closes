"""导出搭配图片：保存 PNG、打开导出目录。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime

from ..config import EXPORTS_DIR
from ..errors import ServiceError, ValidationError
from ..utils import logger

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')
MAX_EXPORT_BYTES = 30 * 1024 * 1024


def save_png(name: str, raw: bytes) -> dict:
    """保存前端合成的 PNG，返回文件名和大小。"""
    if not raw:
        raise ValidationError("导出内容为空")
    if len(raw) > MAX_EXPORT_BYTES:
        raise ValidationError("导出的图片太大")
    if not raw.startswith(PNG_SIGNATURE):
        raise ValidationError("导出内容不是 PNG 图片")

    safe_name = UNSAFE_CHARS.sub("_", (name or "搭配").strip())[:40] or "搭配"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"{safe_name}_{timestamp}.png"

    try:
        path.write_bytes(raw)
    except OSError as exc:
        logger.exception("保存导出图片失败")
        raise ServiceError("保存导出图片失败，请重试") from exc

    logger.info("已导出搭配图片 %s（%s 字节）", path, len(raw))
    return {
        "path": f"exports/{path.name}",
        "name": path.name,
        "size": len(raw),
    }


def open_exports_folder() -> None:
    """在资源管理器中打开导出目录。"""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(EXPORTS_DIR))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(EXPORTS_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(EXPORTS_DIR)])
    except OSError as exc:
        logger.exception("打开导出目录失败")
        raise ServiceError("无法打开导出文件夹，请手动打开 data/exports") from exc
