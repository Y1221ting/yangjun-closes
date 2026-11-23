"""搭配相关接口。"""

from __future__ import annotations

from ..config import ANGLE_LABELS
from ..errors import ValidationError
from ..router import Request
from ..services import outfit_service


def _outfit_id(req: Request) -> int:
    try:
        return int(req.params.get("id", ""))
    except ValueError as exc:
        raise ValidationError("搭配编号不正确") from exc


def list_outfits(req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": outfit_service.list_outfits(req.query)}


def create_outfit(req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": outfit_service.create_outfit(req.json())}


def get_outfit(req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": outfit_service.get_outfit(_outfit_id(req))}


def update_outfit(req: Request) -> tuple[int, dict]:
    data = outfit_service.update_outfit(_outfit_id(req), req.json())
    return 200, {"ok": True, "data": data}


def delete_outfit(req: Request) -> tuple[int, dict]:
    outfit_service.delete_outfit(_outfit_id(req))
    return 200, {"ok": True, "data": {"deleted": True}}


def upload_image(req: Request) -> tuple[int, dict]:
    angle = (req.query.get("angle") or "").strip()
    if angle not in ANGLE_LABELS:
        raise ValidationError("请指定图片角度（front / front45 / side / back135 / back）")
    data = outfit_service.save_image(_outfit_id(req), angle, req.body)
    return 200, {"ok": True, "data": data}


def adjust_image(req: Request) -> tuple[int, dict]:
    angle = (req.params.get("angle") or "").strip()
    if angle not in ANGLE_LABELS:
        raise ValidationError("未知的图片角度")
    data = outfit_service.adjust_image(_outfit_id(req), angle, req.json())
    return 200, {"ok": True, "data": data}


def save_items(req: Request) -> tuple[int, dict]:
    view = (req.query.get("view") or "flat").strip()
    payload = req.json()
    data = outfit_service.save_items(_outfit_id(req), view, payload.get("items", []))
    return 200, {"ok": True, "data": data}
