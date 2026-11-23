"""搭配业务逻辑：增删改查、画布布局保存。"""

from __future__ import annotations

import sqlite3

from ..config import ANGLE_LABELS
from ..db import get_conn
from ..errors import NotFoundError, ServiceError, ValidationError
from ..models import dump_list, row_to_dict, rows_to_dicts
from ..utils import logger, now_precise, now_str
from . import image_service

VIEWS = ("flat", "worn")
MAX_ITEMS = 60


def _validate_meta(data: dict) -> dict:
    """校验搭配名称与场景标签。"""
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("请填写搭配名称")
    if len(name) > 40:
        raise ValidationError("搭配名称最多 40 个字")

    scenes = [
        item.strip()
        for item in (data.get("scenes") or [])
        if isinstance(item, str) and item.strip()
    ][:8]
    notes = (data.get("notes") or "").strip() or None
    return {"name": name, "scenes": scenes, "notes": notes}


# ---------------------------------------------------------------- 查询


def _attach_images(conn: sqlite3.Connection, outfits: list[dict]) -> None:
    """批量补上整套上身图与封面。"""
    if not outfits:
        return
    ids = [item["id"] for item in outfits]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT outfit_id, angle, path, width, height, scale, offset_x, offset_y "
        f"FROM outfit_images WHERE outfit_id IN ({placeholders})",
        ids,
    ).fetchall()

    grouped: dict[int, dict] = {}
    for row in rows:
        grouped.setdefault(row["outfit_id"], {})[row["angle"]] = {
            "path": row["path"],
            "width": row["width"],
            "height": row["height"],
            "scale": row["scale"],
            "offset_x": row["offset_x"],
            "offset_y": row["offset_y"],
        }

    for outfit in outfits:
        outfit["images"] = grouped.get(outfit["id"], {})
        outfit["worn_cover"] = image_service.outfit_thumb_path(outfit["id"])


def list_outfits(filters: dict | None = None) -> list[dict]:
    """搭配列表，带画布布局（用于封面预览）、件数和类别。"""
    filters = filters or {}
    sql = "SELECT * FROM outfits WHERE deleted_at IS NULL"
    args: list[object] = []

    scene = (filters.get("scene") or "").strip()
    if scene:
        sql += " AND scenes LIKE ?"
        args.append(f'%"{scene}"%')

    keyword = (filters.get("q") or "").strip()
    if keyword:
        sql += " AND name LIKE ?"
        args.append(f"%{keyword}%")

    sql += " ORDER BY updated_at DESC, id DESC"

    conn = get_conn()
    try:
        outfits = rows_to_dicts(conn.execute(sql, args).fetchall())
        if not outfits:
            return []

        ids = [item["id"] for item in outfits]
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT oi.outfit_id, oi.garment_id, oi.x, oi.y, oi.scale, "
            f"       oi.rotation, oi.z_index, oi.clip_top, oi.clip_bottom, "
            f"       g.category, gi.path AS front_path "
            f"FROM outfit_items oi "
            f"JOIN garments g ON g.id = oi.garment_id "
            f"LEFT JOIN garment_images gi "
            f"  ON gi.garment_id = g.id AND gi.angle = 'front' "
            f"WHERE oi.outfit_id IN ({placeholders}) AND oi.view = 'flat' "
            f"  AND g.deleted_at IS NULL "
            f"ORDER BY oi.outfit_id, oi.z_index, oi.id",
            ids,
        ).fetchall()

        grouped: dict[int, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["outfit_id"], []).append(
                {
                    "garment_id": row["garment_id"],
                    "x": row["x"],
                    "y": row["y"],
                    "scale": row["scale"],
                    "rotation": row["rotation"],
                    "z_index": row["z_index"],
                    "clip_top": row["clip_top"],
                    "clip_bottom": row["clip_bottom"],
                    "category": row["category"],
                    "image": row["front_path"]
                    or f"garments/{row['garment_id']}/thumb.webp",
                }
            )

        for outfit in outfits:
            items = grouped.get(outfit["id"], [])
            outfit["items"] = items
            outfit["item_count"] = len(items)
            outfit["categories"] = sorted({item["category"] for item in items})

        _attach_images(conn, outfits)

        for outfit in outfits:
            items = outfit["items"]
            outfit["cover"] = outfit["worn_cover"] or (
                f"garments/{items[0]['garment_id']}/thumb.webp" if items else None
            )
        return outfits
    except sqlite3.Error as exc:
        logger.exception("查询搭配列表失败")
        raise ServiceError("读取搭配失败，请重试") from exc
    finally:
        conn.close()


def get_outfit(outfit_id: int) -> dict:
    """搭配详情，含平铺与上身两种视图的单品。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM outfits WHERE id = ? AND deleted_at IS NULL",
            (outfit_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("搭配不存在或已被删除")
        outfit = row_to_dict(row)

        items = conn.execute(
            "SELECT oi.*, g.name AS garment_name, g.category AS garment_category, "
            "gi.path AS front_path "
            "FROM outfit_items oi "
            "JOIN garments g ON g.id = oi.garment_id "
            "LEFT JOIN garment_images gi "
            "  ON gi.garment_id = g.id AND gi.angle = 'front' "
            "WHERE oi.outfit_id = ? AND g.deleted_at IS NULL "
            "ORDER BY oi.view, oi.z_index, oi.id",
            (outfit_id,),
        ).fetchall()

        grouped: dict[str, list[dict]] = {"flat": [], "worn": []}
        for item in items:
            data = dict(item)
            front = data.pop("front_path")
            data["garment"] = {
                "name": data.pop("garment_name"),
                "category": data.pop("garment_category"),
                "thumb": f"garments/{data['garment_id']}/thumb.webp",
                "image": front or f"garments/{data['garment_id']}/thumb.webp",
                "front": bool(front),
            }
            grouped.setdefault(data["view"], []).append(data)

        outfit["items"] = grouped
        _attach_images(conn, [outfit])
        return outfit
    except sqlite3.Error as exc:
        logger.exception("读取搭配失败 id=%s", outfit_id)
        raise ServiceError("读取搭配失败，请重试") from exc
    finally:
        conn.close()


# ---------------------------------------------------------------- 写入


def create_outfit(data: dict) -> dict:
    """新建搭配。"""
    meta = _validate_meta(data)
    now = now_str()

    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO outfits (name, scenes, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (meta["name"], dump_list(meta["scenes"]), meta["notes"], now, now),
            )
            outfit_id = cursor.lastrowid
    except sqlite3.Error as exc:
        logger.exception("创建搭配失败")
        raise ServiceError("新建搭配失败，请重试") from exc
    finally:
        conn.close()

    logger.info("已创建搭配 id=%s name=%s", outfit_id, meta["name"])
    return get_outfit(outfit_id)


def update_outfit(outfit_id: int, data: dict) -> dict:
    """修改搭配名称、场景与备注。"""
    meta = _validate_meta(data)

    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE outfits SET name = ?, scenes = ?, notes = ?, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NULL",
                (
                    meta["name"],
                    dump_list(meta["scenes"]),
                    meta["notes"],
                    now_precise(),
                    outfit_id,
                ),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("搭配不存在或已被删除")
    except sqlite3.Error as exc:
        logger.exception("更新搭配失败 id=%s", outfit_id)
        raise ServiceError("保存搭配失败，请重试") from exc
    finally:
        conn.close()

    return get_outfit(outfit_id)


def delete_outfit(outfit_id: int) -> None:
    """把搭配移入回收站（软删除，不删除图片和画布）。"""
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE outfits SET deleted_at = ?, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NULL",
                (now_str(), now_str(), outfit_id),
            )
            deleted = cursor.rowcount
    except sqlite3.Error as exc:
        logger.exception("移入回收站失败 id=%s", outfit_id)
        raise ServiceError("删除失败，请重试") from exc
    finally:
        conn.close()

    if not deleted:
        raise NotFoundError("搭配不存在或已被删除")

    logger.info("搭配已移入回收站 id=%s", outfit_id)


def list_trash_outfits() -> list[dict]:
    """回收站里的搭配。"""
    conn = get_conn()
    try:
        outfits = rows_to_dicts(
            conn.execute(
                "SELECT * FROM outfits WHERE deleted_at IS NOT NULL "
                "ORDER BY deleted_at DESC, id DESC"
            ).fetchall()
        )
        if not outfits:
            return []

        ids = [item["id"] for item in outfits]
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT oi.outfit_id, oi.garment_id, oi.clip_top, oi.clip_bottom, "
            f"       g.category, gi.path AS front_path "
            f"FROM outfit_items oi "
            f"JOIN garments g ON g.id = oi.garment_id "
            f"LEFT JOIN garment_images gi "
            f"  ON gi.garment_id = g.id AND gi.angle = 'front' "
            f"WHERE oi.outfit_id IN ({placeholders}) AND oi.view = 'flat' "
            f"ORDER BY oi.outfit_id, oi.z_index, oi.id",
            ids,
        ).fetchall()

        grouped: dict[int, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row["outfit_id"], []).append(
                {
                    "garment_id": row["garment_id"],
                    "category": row["category"],
                    "image": row["front_path"]
                    or f"garments/{row['garment_id']}/thumb.webp",
                }
            )

        for outfit in outfits:
            items = grouped.get(outfit["id"], [])
            outfit["items"] = items
            outfit["item_count"] = len(items)
            outfit["categories"] = sorted({item["category"] for item in items})

        _attach_images(conn, outfits)
        for outfit in outfits:
            items = outfit["items"]
            outfit["cover"] = outfit["worn_cover"] or (
                f"garments/{items[0]['garment_id']}/thumb.webp" if items else None
            )
        return outfits
    except sqlite3.Error as exc:
        logger.exception("读取回收站搭配失败")
        raise ServiceError("读取回收站失败，请重试") from exc
    finally:
        conn.close()


def restore_outfit(outfit_id: int) -> dict:
    """从回收站恢复搭配。"""
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE outfits SET deleted_at = NULL, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NOT NULL",
                (now_str(), outfit_id),
            )
            restored = cursor.rowcount
    except sqlite3.Error as exc:
        logger.exception("恢复搭配失败 id=%s", outfit_id)
        raise ServiceError("恢复失败，请重试") from exc
    finally:
        conn.close()

    if not restored:
        raise NotFoundError("回收站里没有这套搭配")

    logger.info("已恢复搭配 id=%s", outfit_id)
    return get_outfit(outfit_id)


def purge_outfit(outfit_id: int) -> None:
    """彻底删除回收站里的搭配（含上身图）。"""
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM outfits WHERE id = ? AND deleted_at IS NOT NULL",
                (outfit_id,),
            )
            deleted = cursor.rowcount
    except sqlite3.Error as exc:
        logger.exception("彻底删除搭配失败 id=%s", outfit_id)
        raise ServiceError("彻底删除失败，请重试") from exc
    finally:
        conn.close()

    if not deleted:
        raise NotFoundError("回收站里没有这套搭配")

    image_service.delete_outfit_dir(outfit_id)
    logger.info("已彻底删除搭配 id=%s", outfit_id)


def save_image(outfit_id: int, angle: str, raw: bytes) -> dict:
    """保存整套上身图的一个角度。"""
    if angle not in ANGLE_LABELS:
        raise ValidationError("未知的图片角度")
    get_outfit(outfit_id)

    processed = image_service.process_outfit_image(outfit_id, angle, raw)

    conn = get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO outfit_images (outfit_id, angle, path, width, height) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(outfit_id, angle) DO UPDATE SET "
                "path = excluded.path, width = excluded.width, height = excluded.height",
                (
                    outfit_id,
                    angle,
                    processed["path"],
                    processed["width"],
                    processed["height"],
                ),
            )
            conn.execute(
                "UPDATE outfits SET updated_at = ? WHERE id = ?",
                (now_precise(), outfit_id),
            )
    except sqlite3.Error as exc:
        logger.exception("保存上身图失败 id=%s angle=%s", outfit_id, angle)
        raise ServiceError("保存上身图失败，请重试") from exc
    finally:
        conn.close()

    if angle == "front":
        image_service.make_outfit_thumb(outfit_id)

    logger.info("已保存上身图 id=%s angle=%s", outfit_id, angle)
    return get_outfit(outfit_id)["images"][angle]


def adjust_image(outfit_id: int, angle: str, data: dict) -> dict:
    """保存某个上身角度的缩放与位置微调。"""
    if angle not in ANGLE_LABELS:
        raise ValidationError("未知的图片角度")
    try:
        scale = float(data.get("scale", 1.0))
        offset_x = float(data.get("offset_x", 0.0))
        offset_y = float(data.get("offset_y", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("微调参数格式不正确") from exc

    if not 0.5 <= scale <= 2.0:
        raise ValidationError("大小调整范围是 50% ~ 200%")
    if not -50 <= offset_x <= 50:
        raise ValidationError("水平调整范围是 -50% ~ 50%")
    if not -50 <= offset_y <= 50:
        raise ValidationError("垂直调整范围是 -50% ~ 50%")

    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE outfit_images SET scale = ?, offset_x = ?, offset_y = ? "
                "WHERE outfit_id = ? AND angle = ?",
                (scale, offset_x, offset_y, outfit_id, angle),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("这个角度还没有上身图，无法微调")
    except sqlite3.Error as exc:
        logger.exception("保存上身图微调失败 id=%s angle=%s", outfit_id, angle)
        raise ServiceError("保存微调失败，请重试") from exc
    finally:
        conn.close()

    return get_outfit(outfit_id)["images"][angle]


def _validate_items(raw_items: list) -> list[tuple]:
    """校验并整理画布条目。"""
    if not isinstance(raw_items, list):
        raise ValidationError("搭配数据格式不正确")
    if len(raw_items) > MAX_ITEMS:
        raise ValidationError(f"一套搭配最多 {MAX_ITEMS} 件")

    prepared = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValidationError("搭配数据格式不正确")
        try:
            garment_id = int(item.get("garment_id"))
            x = float(item.get("x"))
            y = float(item.get("y"))
            scale = float(item.get("scale", 1))
            rotation = float(item.get("rotation", 0))
            z_index = int(item.get("z_index", 0))
            locked = 1 if item.get("locked") else 0
            clip_top = float(item.get("clip_top", 0))
            clip_bottom = float(item.get("clip_bottom", 1))
        except (TypeError, ValueError) as exc:
            raise ValidationError("搭配数据格式不正确") from exc

        if garment_id <= 0:
            raise ValidationError("搭配里有无效的衣服")

        clip_top = min(1.0, max(0.0, clip_top))
        clip_bottom = min(1.0, max(0.0, clip_bottom))
        if clip_bottom < clip_top:
            clip_top, clip_bottom = clip_bottom, clip_top

        prepared.append(
            (
                garment_id,
                min(1.0, max(0.0, x)),
                min(1.0, max(0.0, y)),
                min(5.0, max(0.1, scale)),
                min(180.0, max(-180.0, rotation)),
                min(999, max(0, z_index)),
                locked,
                clip_top,
                clip_bottom,
            )
        )
    return prepared


def save_items(outfit_id: int, view: str, raw_items: list) -> dict:
    """整体替换某个视图的画布布局。"""
    if view not in VIEWS:
        raise ValidationError("未知的视图")
    prepared = _validate_items(raw_items)

    conn = get_conn()
    try:
        with conn:
            exists = conn.execute(
                "SELECT 1 FROM outfits WHERE id = ? AND deleted_at IS NULL",
                (outfit_id,),
            ).fetchone()
            if exists is None:
                raise NotFoundError("搭配不存在或已被删除")

            # 保留已移入回收站的衣服的布局，恢复衣服后可以还原
            conn.execute(
                "DELETE FROM outfit_items WHERE outfit_id = ? AND view = ? "
                "AND garment_id NOT IN "
                "(SELECT id FROM garments WHERE deleted_at IS NOT NULL)",
                (outfit_id, view),
            )
            conn.executemany(
                "INSERT INTO outfit_items "
                "(outfit_id, garment_id, view, x, y, scale, rotation, z_index, "
                " locked, clip_top, clip_bottom) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        outfit_id,
                        garment_id,
                        view,
                        x,
                        y,
                        scale,
                        rotation,
                        z_index,
                        locked,
                        clip_top,
                        clip_bottom,
                    )
                    for (
                        garment_id,
                        x,
                        y,
                        scale,
                        rotation,
                        z_index,
                        locked,
                        clip_top,
                        clip_bottom,
                    ) in prepared
                ],
            )
            conn.execute(
                "UPDATE outfits SET updated_at = ? WHERE id = ?",
                (now_precise(), outfit_id),
            )
    except sqlite3.IntegrityError as exc:
        raise ValidationError("有待删除的衣服，请刷新后重试") from exc
    except sqlite3.Error as exc:
        logger.exception("保存搭配布局失败 id=%s view=%s", outfit_id, view)
        raise ServiceError("保存搭配失败，请重试") from exc
    finally:
        conn.close()

    return get_outfit(outfit_id)
