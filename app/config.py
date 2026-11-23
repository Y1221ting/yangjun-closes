"""全局配置：路径、应用信息、业务枚举。

所有绝对路径只能在本文件里出现，其他模块统一从这里导入。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------- 路径

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """定位随程序打包的资源（web 目录等）。

    PyInstaller 单文件模式下资源被解压到临时目录 sys._MEIPASS；
    开发模式下就是项目根目录。
    """
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base / relative


def app_dir() -> Path:
    """定位数据目录：开发时在项目根目录，打包后在 exe 同级。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


WEB_DIR = resource_path("web")

# 数据目录允许用环境变量覆盖（测试和迁移时使用）
_data_override = os.environ.get("WARDROBE_DATA_DIR")
_log_override = os.environ.get("WARDROBE_LOG_DIR")
DATA_DIR = Path(_data_override).expanduser() if _data_override else app_dir() / "data"
LOG_DIR = Path(_log_override).expanduser() if _log_override else app_dir() / "logs"
DB_PATH = DATA_DIR / "wardrobe.db"

GARMENTS_DIR = DATA_DIR / "garments"
OUTFITS_DIR = DATA_DIR / "outfits"
MODEL_DIR = DATA_DIR / "model"
EXPORTS_DIR = DATA_DIR / "exports"
TMP_DIR = DATA_DIR / "tmp"

# ---------------------------------------------------------------- 应用信息

APP_NAME = "yt的衣柜"
APP_VERSION = "0.7.0"

HOST = "127.0.0.1"          # 只监听本机，外部无法访问
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 860
WINDOW_MIN_SIZE = (1024, 700)

# 单张图片上传上限（20MB）
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# ---------------------------------------------------------------- 业务枚举

# 类别：值用于数据库存储，标签用于界面显示
CATEGORIES = [
    ("top", "上衣"),
    ("outer", "外套"),
    ("bottom", "下装"),
    ("dress", "连衣裙"),
    ("shoes", "鞋"),
    ("bag", "包"),
    ("hat", "帽子"),
    ("accessory", "配饰"),
]

CATEGORY_LABELS = dict(CATEGORIES)

COLORS = [
    ("black", "黑色"),
    ("white", "白色"),
    ("gray", "灰色"),
    ("beige", "米色"),
    ("brown", "棕色"),
    ("red", "红色"),
    ("pink", "粉色"),
    ("orange", "橙色"),
    ("yellow", "黄色"),
    ("green", "绿色"),
    ("blue", "蓝色"),
    ("purple", "紫色"),
    ("denim", "牛仔蓝"),
    ("other", "其他"),
]

COLOR_LABELS = dict(COLORS)

SEASONS = [
    ("spring", "春"),
    ("summer", "夏"),
    ("autumn", "秋"),
    ("winter", "冬"),
]

SEASON_LABELS = dict(SEASONS)

# 配饰在首页的摆放方式：挂杆 / 纸袋 / 平放 / 抽屉
DISPLAY_STYLES = [
    ("hang", "挂杆"),
    ("bag", "纸袋"),
    ("flat", "平放"),
    ("drawer", "抽屉"),
]

DISPLAY_STYLE_LABELS = dict(DISPLAY_STYLES)

# 衣帽柜分区：鞋、包、帽子和抽屉各有一组格位
CABINET_ZONE_CATEGORIES = {"shoes", "bag", "hat"}


def cabinet_zone(category: str, display_style: str | None) -> str | None:
    """返回物品所在的柜子分区；不进柜子的物品返回 None。"""
    if category in CABINET_ZONE_CATEGORIES:
        return category
    if category == "accessory" and display_style == "drawer":
        return "drawer"
    return None

# 角度图顺序：从左到右对应拖动时的帧序列
ANGLES = ["front", "front45", "side", "back135", "back"]
ANGLE_LABELS = {
    "front": "正面",
    "front45": "左前 45°",
    "side": "侧面",
    "back135": "左后 135°",
    "back": "背面",
}

# 画布逻辑尺寸（3:4 竖版）
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 1600
