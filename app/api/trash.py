"""回收站与数据备份接口。"""

from __future__ import annotations

from ..errors import ValidationError
from ..router import Request
from ..services import backup_service, garment_service, outfit_service


def _item_id(req: Request) -> int:
    try:
        return int(req.params.get("id", ""))
    except ValueError as exc:
        raise ValidationError("编号不正确") from exc


def overview(_req: Request) -> tuple[int, dict]:
    return 200, {
        "ok": True,
        "data": {
            "garments": garment_service.list_trash_garments(),
            "outfits": outfit_service.list_trash_outfits(),
            "backups": backup_service.list_backups(),
        },
    }


def restore_garment(req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": garment_service.restore_garment(_item_id(req))}


def purge_garment(req: Request) -> tuple[int, dict]:
    garment_service.purge_garment(_item_id(req))
    return 200, {"ok": True, "data": {"purged": True}}


def restore_outfit(req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": outfit_service.restore_outfit(_item_id(req))}


def purge_outfit(req: Request) -> tuple[int, dict]:
    outfit_service.purge_outfit(_item_id(req))
    return 200, {"ok": True, "data": {"purged": True}}


def create_backup(_req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": backup_service.create_backup()}
