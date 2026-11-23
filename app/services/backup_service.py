"""数据备份：启动时备份数据库，手动备份整个 data 目录。"""

from __future__ import annotations

import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR, DB_PATH
from ..errors import ServiceError
from ..utils import logger

BACKUP_DIR = DATA_DIR / "backups"
DB_BACKUP_KEEP = 7
FULL_BACKUP_KEEP = 5


def _prune(pattern: str, keep: int) -> None:
    """只保留最近的若干个备份文件。"""
    files = sorted(BACKUP_DIR.glob(pattern), key=lambda path: path.stat().st_mtime)
    for old in files[:-keep]:
        try:
            old.unlink()
        except OSError:
            logger.warning("清理旧备份失败: %s", old)


def _snapshot_database(target: Path) -> None:
    """用 SQLite 备份接口生成一致性快照（包含 WAL 中的数据）。"""
    source = sqlite3.connect(DB_PATH)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def backup_database() -> Path | None:
    """启动时备份数据库，返回备份文件路径。"""
    if not DB_PATH.is_file():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"wardrobe-{stamp}.db"

    try:
        _snapshot_database(target)
    except (sqlite3.Error, OSError):
        logger.exception("启动备份数据库失败")
        return None

    _prune("wardrobe-*.db", DB_BACKUP_KEEP)
    logger.info("已备份数据库 %s", target.name)
    return target


def create_backup() -> dict:
    """打包整个 data 目录（不含备份目录和临时目录）。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"wardrobe-backup-{stamp}.zip"
    snapshot = BACKUP_DIR / f".snapshot-{stamp}.db"

    try:
        if DB_PATH.is_file():
            _snapshot_database(snapshot)

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in DATA_DIR.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(DATA_DIR)
                if relative.parts and relative.parts[0] in ("backups", "tmp"):
                    continue
                if path.suffix in (".db-wal", ".db-shm"):
                    continue
                if relative.as_posix() == "wardrobe.db":
                    if snapshot.is_file():
                        archive.write(snapshot, "wardrobe.db")
                    continue
                archive.write(path, relative.as_posix())
    except (sqlite3.Error, OSError, zipfile.BadZipFile) as exc:
        logger.exception("创建数据备份失败")
        raise ServiceError("备份失败，请检查磁盘空间后重试") from exc
    finally:
        if snapshot.is_file():
            try:
                snapshot.unlink()
            except OSError:
                logger.warning("清理备份快照失败: %s", snapshot)

    _prune("wardrobe-backup-*.zip", FULL_BACKUP_KEEP)
    logger.info("已创建完整备份 %s", target.name)

    return {
        "name": target.name,
        "path": f"backups/{target.name}",
        "size": target.stat().st_size,
    }


def list_backups() -> list[dict]:
    """列出最近的备份文件。"""
    if not BACKUP_DIR.is_dir():
        return []
    items = []
    for path in sorted(
        BACKUP_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True
    ):
        if not path.is_file() or path.name.startswith("."):
            continue
        items.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
    return items[:10]
