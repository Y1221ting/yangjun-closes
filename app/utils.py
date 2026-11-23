"""通用工具：日志、时间格式化、目录初始化。"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config import (
    DATA_DIR,
    EXPORTS_DIR,
    GARMENTS_DIR,
    LOG_DIR,
    MODEL_DIR,
    OUTFITS_DIR,
    TMP_DIR,
)

logger = logging.getLogger("wardrobe")

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """配置日志：同时输出到控制台和 logs/app.log。

    重复调用不会重复添加 handler。
    """
    if logger.handlers:
        return

    # Windows 控制台默认 GBK，中文日志会乱码，统一切换到 UTF-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def ensure_dirs() -> None:
    """创建运行所需的数据目录（幂等）。"""
    for directory in (
        DATA_DIR,
        GARMENTS_DIR,
        OUTFITS_DIR,
        MODEL_DIR,
        EXPORTS_DIR,
        TMP_DIR,
        LOG_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def now_str() -> str:
    """当前本地时间，格式 YYYY-MM-DD HH:MM:SS。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    """今天的日期，格式 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


def now_precise() -> str:
    """带微秒的时间，用作图片缓存版本号（同一秒内多次替换也能区分）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def clear_tmp() -> None:
    """清空临时目录（启动时调用）。"""
    if not TMP_DIR.exists():
        return
    for item in TMP_DIR.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil

                shutil.rmtree(item)
        except OSError:
            logger.warning("清理临时文件失败: %s", item)
