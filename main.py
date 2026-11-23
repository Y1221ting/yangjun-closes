"""个人衣柜 · 启动入口。

流程：初始化日志与目录 → 启动本地 HTTP 服务 → 打开桌面窗口。
设置环境变量 WARDROBE_DEBUG=1 可开启开发者工具。
"""

from __future__ import annotations

import os
import sys

import webview

from app.config import (
    APP_NAME,
    APP_VERSION,
    HOST,
    WINDOW_HEIGHT,
    WINDOW_MIN_SIZE,
    WINDOW_WIDTH,
)
from app.db import init_db
from app.server import start_server
from app.services import backup_service
from app.utils import clear_tmp, ensure_dirs, logger, setup_logging


def main() -> int:
    """启动程序，返回进程退出码。"""
    setup_logging()
    ensure_dirs()
    clear_tmp()
    backup_service.backup_database()
    init_db()

    logger.info("========== %s v%s 启动 ==========", APP_NAME, APP_VERSION)
    logger.info("Python %s", sys.version.split()[0])

    httpd, port = start_server()
    url = f"http://{HOST}:{port}/"
    debug = bool(os.environ.get("WARDROBE_DEBUG"))

    try:
        webview.create_window(
            APP_NAME,
            url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=WINDOW_MIN_SIZE,
            background_color="#F6EFE1",
            text_select=False,
        )
        webview.start(debug=debug)
    except Exception:  # noqa: BLE001 - 启动失败必须写日志并给出退出码
        logger.exception("窗口启动失败")
        return 1
    finally:
        httpd.shutdown()
        logger.info("已退出")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
