"""衣服业务逻辑：增删改查、图片关联、筛选。"""

from __future__ import annotations

import sqlite3

from ..config import (
    CATEGORY_LABELS,
    COLOR_LABELS,
    DISPLAY_STYLE_LABELS,
    SEASON_LABELS,
    cabinet_zone,
)
from ..db import get_conn
from ..errors import NotFoundError, ServiceError, ValidationError
from ..models import dump_list, row_to_dict, rows_to_dicts
from ..utils import logger, now_precise, now_str
from . import image_service


# ---------------------------------------------------------------- 校验


def _validate_meta(data: dict) -> dict:
    """校验并整理衣服信息。"""
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("请填写衣服名称")
    if len(name) > 60:
        raise ValidationError("名称太长了，最多 60 个字")

    category = data.get("category")
    if category not in CATEGORY_LABELS:
        raise ValidationError("请选择衣服类别")

    color = data.get("color") or None
    if color and color not in COLOR_LABELS:
        raise ValidationError("颜色不在可选范围内")

    # 配饰的摆放方式：挂杆 / 纸袋 / 平放 / 抽屉，其他类别保持默认值
    display_style = data.get("display_style") or "hang"
    if display_style not in DISPLAY_STYLE_LABELS:
        raise ValidationError("摆放方式不在可选范围内")
    if category != "accessory":
        display_style = "hang"

    seasons = [item for item in (data.get("seasons") or []) if item in SEASON_LABELS]
    occasions = [
        item.strip()
        for item in (data.get("occasions") or [])
        if isinstance(item, str) and item.strip()
    ][:10]

    return {
        "name": name,
        "category": category,
        "color": color,
        "display_style": display_style,
        "seasons": seasons,
        "occasions": occasions,
        "brand": (data.get("brand") or "").strip() or None,
        "price": data.get("price"),
        "purchase_date": data.get("purchase_date") or None,
        "notes": (data.get("notes") or "").strip() or None,
    }


def _zone_where(zone: str) -> tuple[str, tuple]:
    """返回某个柜子分区的 SQL 条件和参数。"""
    if zone == "drawer":
        return "category = 'accessory' AND display_style = 'drawer'", ()
    return "category = ?", (zone,)


def _zone_used_slots(
    conn: sqlite3.Connection, zone: str, exclude_id: int | None = None
) -> set[int]:
    """读取某个分区已经被占用的格位。"""
    where, args = _zone_where(zone)
    sql = f"SELECT cabinet_slot FROM garments WHERE deleted_at IS NULL AND {where}"
    params = list(args)
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    return {
        row["cabinet_slot"]
        for row in conn.execute(sql, params).fetchall()
        if row["cabinet_slot"] is not None
    }


def _assign_cabinet_slot(
    conn: sqlite3.Connection,
    garment_id: int,
    category: str,
    display_style: str,
    force_new: bool = False,
) -> None:
    """给物品分配柜子格位：优先保留原格位，否则放进本区第一个空格。"""
    zone = cabinet_zone(category, display_style)
    row = conn.execute(
        "SELECT cabinet_slot FROM garments WHERE id = ?", (garment_id,)
    ).fetchone()
    current = row["cabinet_slot"] if row else None

    if zone is None:
        if current is not None:
            conn.execute(
                "UPDATE garments SET cabinet_slot = NULL WHERE id = ?", (garment_id,)
            )
        return

    used = _zone_used_slots(conn, zone, exclude_id=garment_id)
    if not force_new and current is not None and current not in used:
        return

    slot = 0
    while slot in used:
        slot += 1
    conn.execute(
        "UPDATE garments SET cabinet_slot = ? WHERE id = ?", (slot, garment_id)
    )


def _attach_images(conn: sqlite3.Connection, garments: list[dict]) -> None:
    """批量补上 images 和 thumb 字段，避免逐条查询。"""
    if not garments:
        return
    ids = [item["id"] for item in garments]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT garment_id, angle, path, width, height, scale, offset_x, offset_y "
        f"FROM garment_images WHERE garment_id IN ({placeholders})",
        ids,
    ).fetchall()

    grouped: dict[int, dict] = {}
    for row in rows:
        grouped.setdefault(row["garment_id"], {})[row["angle"]] = {
            "path": row["path"],
            "width": row["width"],
            "height": row["height"],
            "scale": row["scale"],
            "offset_x": row["offset_x"],
            "offset_y": row["offset_y"],
        }

    for item in garments:
        item["images"] = grouped.get(item["id"], {})
        item["thumb"] = image_service.thumb_path(item["id"])


# ---------------------------------------------------------------- 查询


def list_garments(filters: dict) -> list[dict]:
    """按筛选条件查询衣服列表。"""
    sql = "SELECT * FROM garments WHERE deleted_at IS NULL"
    args: list[object] = []

    category = (filters.get("category") or "").strip()
    if category:
        sql += " AND category = ?"
        args.append(category)

    color = (filters.get("color") or "").strip()
    if color:
        sql += " AND color = ?"
        args.append(color)

    season = (filters.get("season") or "").strip()
    if season:
        sql += " AND seasons LIKE ?"
        args.append(f'%"{season}"%')

    scene = (filters.get("scene") or "").strip()
    if scene:
        sql += " AND occasions LIKE ?"
        args.append(f'%"{scene}"%')

    keyword = (filters.get("q") or "").strip()
    if keyword:
        sql += " AND name LIKE ?"
        args.append(f"%{keyword}%")

    sql += " ORDER BY sort_order ASC, created_at DESC, id DESC"

    conn = get_conn()
    try:
        garments = rows_to_dicts(conn.execute(sql, args).fetchall())
        _attach_images(conn, garments)
        return garments
    except sqlite3.Error as exc:
        logger.exception("查询衣服列表失败")
        raise ServiceError("读取衣柜失败，请重试") from exc
    finally:
        conn.close()


def category_counts() -> dict:
    """按类别统计未删除的衣服数量，给侧栏「衣橱目录」显示角标。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM garments "
            "WHERE deleted_at IS NULL GROUP BY category"
        ).fetchall()
    except sqlite3.Error as exc:
        logger.exception("统计衣服数量失败")
        raise ServiceError("读取衣服数量失败，请重试") from exc
    finally:
        conn.close()

    counts = {row["category"]: row["count"] for row in rows}
    return {"total": sum(counts.values()), "categories": counts}


def get_garment(garment_id: int) -> dict:
    """读取单件衣服，包含三张角度图信息。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM garments WHERE id = ? AND deleted_at IS NULL",
            (garment_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("衣服不存在或已被删除")
        garment = row_to_dict(row)
        _attach_images(conn, [garment])
        return garment
    except sqlite3.Error as exc:
        logger.exception("读取衣服失败 id=%s", garment_id)
        raise ServiceError("读取衣服失败，请重试") from exc
    finally:
        conn.close()


# ---------------------------------------------------------------- 写入


def create_garment(data: dict) -> dict:
    """新建一件衣服（先只保存信息，图片随后上传）。"""
    meta = _validate_meta(data)
    now = now_str()

    conn = get_conn()
    try:
        with conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order "
                "FROM garments WHERE category = ? AND deleted_at IS NULL",
                (meta["category"],),
            ).fetchone()
            sort_order = row["next_order"] if row else 0

            cursor = conn.execute(
                "INSERT INTO garments "
                "(name, category, color, display_style, seasons, occasions, brand, "
                "price, purchase_date, notes, created_at, updated_at, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    meta["name"],
                    meta["category"],
                    meta["color"],
                    meta["display_style"],
                    dump_list(meta["seasons"]),
                    dump_list(meta["occasions"]),
                    meta["brand"],
                    meta["price"],
                    meta["purchase_date"],
                    meta["notes"],
                    now,
                    now,
                    sort_order,
                ),
            )
            garment_id = cursor.lastrowid
            _assign_cabinet_slot(
                conn, garment_id, meta["category"], meta["display_style"]
            )
    except sqlite3.Error as exc:
        logger.exception("创建衣服失败")
        raise ServiceError("保存衣服失败，请重试") from exc
    finally:
        conn.close()

    logger.info("已创建衣服 id=%s name=%s", garment_id, meta["name"])
    return get_garment(garment_id)


def update_garment(garment_id: int, data: dict) -> dict:
    """更新衣服信息。"""
    meta = _validate_meta(data)

    conn = get_conn()
    try:
        with conn:
            old = conn.execute(
                "SELECT category, display_style FROM garments "
                "WHERE id = ? AND deleted_at IS NULL",
                (garment_id,),
            ).fetchone()
            if old is None:
                raise NotFoundError("衣服不存在或已被删除")
            old_zone = cabinet_zone(old["category"], old["display_style"])

            conn.execute(
                "UPDATE garments SET name = ?, category = ?, color = ?, "
                "display_style = ?, seasons = ?, occasions = ?, brand = ?, price = ?, "
                "purchase_date = ?, notes = ?, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NULL",
                (
                    meta["name"],
                    meta["category"],
                    meta["color"],
                    meta["display_style"],
                    dump_list(meta["seasons"]),
                    dump_list(meta["occasions"]),
                    meta["brand"],
                    meta["price"],
                    meta["purchase_date"],
                    meta["notes"],
                    now_str(),
                    garment_id,
                ),
            )
            new_zone = cabinet_zone(meta["category"], meta["display_style"])
            _assign_cabinet_slot(
                conn,
                garment_id,
                meta["category"],
                meta["display_style"],
                force_new=(old_zone != new_zone),
            )
    except sqlite3.Error as exc:
        logger.exception("更新衣服失败 id=%s", garment_id)
        raise ServiceError("保存修改失败，请重试") from exc
    finally:
        conn.close()

    return get_garment(garment_id)


def reorder_garments(ids: list) -> int:
    """按给定顺序保存挂杆排序（通常是一个类别内的衣服）。"""
    if not isinstance(ids, list) or not ids:
        raise ValidationError("排序数据为空")
    if len(ids) > 500:
        raise ValidationError("一次最多排序 500 件衣服")

    prepared = []
    for index, raw in enumerate(ids):
        try:
            garment_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError("排序数据格式不正确") from exc
        if garment_id <= 0:
            raise ValidationError("排序数据格式不正确")
        prepared.append((index, garment_id))

    conn = get_conn()
    try:
        with conn:
            for index, garment_id in prepared:
                conn.execute(
                    "UPDATE garments SET sort_order = ? "
                    "WHERE id = ? AND deleted_at IS NULL",
                    (index, garment_id),
                )
    except sqlite3.Error as exc:
        logger.exception("保存衣服排序失败")
        raise ServiceError("保存顺序失败，请重试") from exc
    finally:
        conn.close()

    logger.info("已保存衣服排序，共 %s 件", len(prepared))
    return len(prepared)


def save_cabinet_slots(items: list) -> int:
    """保存柜子格位（同一分区内拖动或交换）。"""
    if not isinstance(items, list) or not items:
        raise ValidationError("格位数据为空")
    if len(items) > 200:
        raise ValidationError("一次最多调整 200 件物品")

    prepared = []
    for entry in items:
        if not isinstance(entry, dict):
            raise ValidationError("格位数据格式不正确")
        try:
            garment_id = int(entry.get("id"))
            slot = int(entry.get("slot"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("格位数据格式不正确") from exc
        if garment_id <= 0 or slot < 0 or slot > 999:
            raise ValidationError("格位数据格式不正确")
        prepared.append((garment_id, slot))

    conn = get_conn()
    try:
        with conn:
            records: dict[int, tuple[str, int]] = {}
            for garment_id, slot in prepared:
                row = conn.execute(
                    "SELECT id, category, display_style FROM garments "
                    "WHERE id = ? AND deleted_at IS NULL",
                    (garment_id,),
                ).fetchone()
                if row is None:
                    raise NotFoundError("衣服不存在或已被删除")
                zone = cabinet_zone(row["category"], row["display_style"])
                if zone is None:
                    raise ValidationError("这件物品不在柜子里")
                records[garment_id] = (zone, slot)

            submitted = set(records)
            seen = set()
            for garment_id, (zone, slot) in records.items():
                key = (zone, slot)
                if key in seen:
                    raise ValidationError("同一分区内不能把两件物品放在同一个格子")
                seen.add(key)

                where, args = _zone_where(zone)
                occupant = conn.execute(
                    f"SELECT id FROM garments WHERE deleted_at IS NULL "
                    f"AND cabinet_slot = ? AND id != ? AND {where}",
                    (slot, garment_id, *args),
                ).fetchone()
                if occupant is not None and occupant["id"] not in submitted:
                    raise ValidationError("目标格子已经被占用")

            for garment_id, (_zone, slot) in records.items():
                conn.execute(
                    "UPDATE garments SET cabinet_slot = ? WHERE id = ?",
                    (slot, garment_id),
                )
    except sqlite3.Error as exc:
        logger.exception("保存柜子格位失败")
        raise ServiceError("保存柜子位置失败，请重试") from exc
    finally:
        conn.close()

    logger.info("已保存柜子格位，共 %s 件", len(prepared))
    return len(prepared)


def save_image(garment_id: int, angle: str, raw: bytes) -> dict:
    """处理并保存一张角度图。侧面/背面必须先有正面图作为对齐基准。"""
    get_garment(garment_id)

    reference = None
    if angle != "front":
        reference = image_service.front_height(garment_id)
        if reference is None:
            raise ServiceError("请先上传正面图，再上传侧面或背面")

    processed = image_service.process_image(garment_id, angle, raw, reference)

    conn = get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO garment_images (garment_id, angle, path, width, height) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(garment_id, angle) DO UPDATE SET "
                "path = excluded.path, width = excluded.width, height = excluded.height",
                (
                    garment_id,
                    angle,
                    processed["path"],
                    processed["width"],
                    processed["height"],
                ),
            )
            # 更新时间戳，前端用它做图片缓存版本号
            conn.execute(
                "UPDATE garments SET updated_at = ? WHERE id = ?",
                (now_precise(), garment_id),
            )
    except sqlite3.Error as exc:
        logger.exception("保存衣服图片记录失败 id=%s angle=%s", garment_id, angle)
        raise ServiceError("保存图片失败，请重试") from exc
    finally:
        conn.close()

    if angle == "front":
        image_service.make_thumb(garment_id)

    logger.info("已保存图片 id=%s angle=%s size=%sx%s", garment_id, angle,
                processed["width"], processed["height"])
    return processed


def adjust_image(garment_id: int, angle: str, data: dict) -> dict:
    """保存某个角度的缩放与位置微调。"""
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
                "UPDATE garment_images SET scale = ?, offset_x = ?, offset_y = ? "
                "WHERE garment_id = ? AND angle = ?",
                (scale, offset_x, offset_y, garment_id, angle),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("这个角度还没有图片，无法微调")
    except sqlite3.Error as exc:
        logger.exception("保存角度微调失败 id=%s angle=%s", garment_id, angle)
        raise ServiceError("保存微调失败，请重试") from exc
    finally:
        conn.close()

    return get_garment(garment_id)["images"][angle]


def delete_garment(garment_id: int) -> None:
    """把衣服移入回收站（软删除，不删除图片）。"""
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE garments SET deleted_at = ?, updated_at = ? "
                "WHERE id = ? AND deleted_at IS NULL",
                (now_str(), now_str(), garment_id),
            )
            deleted = cursor.rowcount
    except sqlite3.Error as exc:
        logger.exception("移入回收站失败 id=%s", garment_id)
        raise ServiceError("删除失败，请重试") from exc
    finally:
        conn.close()

    if not deleted:
        raise NotFoundError("衣服不存在或已被删除")

    logger.info("衣服已移入回收站 id=%s", garment_id)


def list_trash_garments() -> list[dict]:
    """回收站里的衣服。"""
    conn = get_conn()
    try:
        garments = rows_to_dicts(
            conn.execute(
                "SELECT * FROM garments WHERE deleted_at IS NOT NULL "
                "ORDER BY deleted_at DESC, id DESC"
            ).fetchall()
        )
        _attach_images(conn, garments)
        return garments
    except sqlite3.Error as exc:
        logger.exception("读取回收站衣服失败")
        raise ServiceError("读取回收站失败，请重试") from exc
    finally:
        conn.close()


def restore_garment(garment_id: int) -> dict:
    """从回收站恢复衣服。"""
    conn = get_conn()
    try:
        with conn:
            row = conn.execute(
                "SELECT category, display_style FROM garments "
                "WHERE id = ? AND deleted_at IS NOT NULL",
                (garment_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("回收站里没有这件衣服")
            conn.execute(
                "UPDATE garments SET deleted_at = NULL, updated_at = ? WHERE id = ?",
                (now_str(), garment_id),
            )
            _assign_cabinet_slot(
                conn,
                garment_id,
                row["category"],
                row["display_style"],
            )
            restored = 1
    except sqlite3.Error as exc:
        logger.exception("恢复衣服失败 id=%s", garment_id)
        raise ServiceError("恢复失败，请重试") from exc
    finally:
        conn.close()

    if not restored:
        raise NotFoundError("回收站里没有这件衣服")

    logger.info("已恢复衣服 id=%s", garment_id)
    return get_garment(garment_id)


def purge_garment(garment_id: int) -> None:
    """彻底删除回收站里的衣服（含图片文件）。"""
    conn = get_conn()
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM garments WHERE id = ? AND deleted_at IS NOT NULL",
                (garment_id,),
            )
            deleted = cursor.rowcount
    except sqlite3.Error as exc:
        logger.exception("彻底删除衣服失败 id=%s", garment_id)
        raise ServiceError("彻底删除失败，请重试") from exc
    finally:
        conn.close()

    if not deleted:
        raise NotFoundError("回收站里没有这件衣服")

    image_service.delete_garment_dir(garment_id)
    logger.info("已彻底删除衣服 id=%s", garment_id)
