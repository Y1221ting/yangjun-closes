"""SQLite 连接、建表与迁移。

约定：
- 每次操作独立连接，用完即关
- 开启外键约束，删除衣服时自动清理搭配条目
- 列表字段（seasons/occasions/scenes）以 JSON 字符串存储
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DB_PATH, cabinet_zone
from .utils import logger

SCHEMA_VERSION = 8

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS garments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    color         TEXT,
    seasons       TEXT,
    occasions     TEXT,
    brand         TEXT,
    price         REAL,
    purchase_date TEXT,
    notes         TEXT,
    wear_count    INTEGER NOT NULL DEFAULT 0,
    last_worn     TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT,
    deleted_at    TEXT,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    display_style TEXT    NOT NULL DEFAULT 'hang',
    cabinet_slot  INTEGER
);

CREATE TABLE IF NOT EXISTS garment_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    garment_id INTEGER NOT NULL,
    angle      TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    width      INTEGER,
    height     INTEGER,
    scale      REAL    NOT NULL DEFAULT 1.0,
    offset_x   REAL    NOT NULL DEFAULT 0,
    offset_y   REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (garment_id) REFERENCES garments(id) ON DELETE CASCADE,
    UNIQUE (garment_id, angle)
);

CREATE TABLE IF NOT EXISTS outfits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    scenes     TEXT,
    notes      TEXT,
    created_at TEXT    NOT NULL,
    updated_at TEXT,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS outfit_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    outfit_id  INTEGER NOT NULL,
    garment_id INTEGER NOT NULL,
    view       TEXT    NOT NULL,
    x          REAL    NOT NULL,
    y          REAL    NOT NULL,
    scale      REAL    NOT NULL DEFAULT 1.0,
    rotation   REAL    NOT NULL DEFAULT 0,
    z_index    INTEGER NOT NULL DEFAULT 0,
    locked     INTEGER NOT NULL DEFAULT 0,
    clip_top   REAL    NOT NULL DEFAULT 0,   -- 上边缘裁切（0~1）
    clip_bottom REAL   NOT NULL DEFAULT 1,   -- 下边缘裁切（0~1）
    FOREIGN KEY (outfit_id) REFERENCES outfits(id) ON DELETE CASCADE,
    FOREIGN KEY (garment_id) REFERENCES garments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS outfit_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    outfit_id  INTEGER NOT NULL,
    angle      TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    width      INTEGER,
    height     INTEGER,
    scale      REAL    NOT NULL DEFAULT 1.0,
    offset_x   REAL    NOT NULL DEFAULT 0,
    offset_y   REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (outfit_id) REFERENCES outfits(id) ON DELETE CASCADE,
    UNIQUE (outfit_id, angle)
);

CREATE TABLE IF NOT EXISTS scenes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    builtin    INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_garments_category ON garments(category);
CREATE INDEX IF NOT EXISTS idx_images_garment    ON garment_images(garment_id);
CREATE INDEX IF NOT EXISTS idx_items_outfit_view ON outfit_items(outfit_id, view);
CREATE INDEX IF NOT EXISTS idx_outfit_images      ON outfit_images(outfit_id);
"""

BUILTIN_SCENES = [
    ("日常", 1),
    ("社交", 2),
    ("休闲", 3),
    ("正式", 4),
]


def get_conn() -> sqlite3.Connection:
    """打开一个带外键约束的连接。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """事务上下文：正常退出提交，异常回滚，最后关闭连接。"""
    conn = get_conn()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _ensure_image_columns(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上角度微调字段。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(garment_images)")}
    additions = {
        "scale": "REAL NOT NULL DEFAULT 1.0",
        "offset_x": "REAL NOT NULL DEFAULT 0",
        "offset_y": "REAL NOT NULL DEFAULT 0",
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE garment_images ADD COLUMN {name} {ddl}")
            logger.info("数据库迁移：garment_images 新增字段 %s", name)


def _ensure_deleted_columns(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上软删除字段，并建立索引。"""
    for table in ("garments", "outfits"):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "deleted_at" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at TEXT")
            logger.info("数据库迁移：%s 新增字段 deleted_at", table)

    # 必须在字段补齐之后再建索引
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_garments_deleted ON garments(deleted_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outfits_deleted ON outfits(deleted_at)"
    )


def _ensure_sort_order(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上挂杆排序字段。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(garments)")}
    if "sort_order" not in columns:
        conn.execute(
            "ALTER TABLE garments ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("数据库迁移：garments 新增字段 sort_order")


def _ensure_display_style(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上配饰摆放方式字段。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(garments)")}
    if "display_style" not in columns:
        conn.execute(
            "ALTER TABLE garments ADD COLUMN display_style TEXT NOT NULL DEFAULT 'hang'"
        )
        logger.info("数据库迁移：garments 新增字段 display_style")


def _ensure_cabinet_slot(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上柜子格位，并按分区补齐缺失的格位。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(garments)")}
    if "cabinet_slot" not in columns:
        conn.execute("ALTER TABLE garments ADD COLUMN cabinet_slot INTEGER")
        logger.info("数据库迁移：garments 新增字段 cabinet_slot")

    used = {"shoes": set(), "bag": set(), "hat": set(), "drawer": set()}
    pending: list[tuple[int, str]] = []
    rows = conn.execute(
        "SELECT id, category, display_style, cabinet_slot FROM garments "
        "WHERE deleted_at IS NULL"
    ).fetchall()

    for row in rows:
        zone = cabinet_zone(row["category"], row["display_style"])
        slot = row["cabinet_slot"]
        if zone is None:
            if slot is not None:
                conn.execute(
                    "UPDATE garments SET cabinet_slot = NULL WHERE id = ?", (row["id"],)
                )
            continue
        if slot is not None and slot not in used[zone]:
            used[zone].add(slot)
        else:
            pending.append((row["id"], zone))

    for garment_id, zone in pending:
        slot = 0
        while slot in used[zone]:
            slot += 1
        used[zone].add(slot)
        conn.execute(
            "UPDATE garments SET cabinet_slot = ? WHERE id = ?", (slot, garment_id)
        )


def _ensure_item_columns(conn: sqlite3.Connection) -> None:
    """为老版本数据库补上画布单品的遮挡字段。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(outfit_items)")}
    additions = {
        "clip_top": "REAL NOT NULL DEFAULT 0",
        "clip_bottom": "REAL NOT NULL DEFAULT 1",
    }
    for name, ddl in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE outfit_items ADD COLUMN {name} {ddl}")
            logger.info("数据库迁移：outfit_items 新增字段 %s", name)


def init_db() -> None:
    """建表并写入初始场景标签（幂等）。"""
    conn = get_conn()
    try:
        with conn:
            conn.executescript(SCHEMA_SQL)
            _ensure_deleted_columns(conn)
            _ensure_image_columns(conn)
            _ensure_item_columns(conn)
            _ensure_sort_order(conn)
            _ensure_display_style(conn)
            _ensure_cabinet_slot(conn)
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < SCHEMA_VERSION:
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                logger.info("数据库结构已初始化到 v%s", SCHEMA_VERSION)

            for name, order in BUILTIN_SCENES:
                conn.execute(
                    "INSERT OR IGNORE INTO scenes (name, builtin, sort_order) VALUES (?, 1, ?)",
                    (name, order),
                )
    except sqlite3.Error:
        logger.exception("数据库初始化失败")
        raise
    finally:
        conn.close()
