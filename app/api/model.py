"""模特接口：读取五角度、上传单个角度。"""

from __future__ import annotations

from ..config import ANGLES
from ..errors import ValidationError
from ..router import Request
from ..services import model_service


def get_model(_req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": model_service.get_model()}


def upload_image(req: Request) -> tuple[int, dict]:
    angle = (req.query.get("angle") or "").strip()
    if angle not in ANGLES:
        raise ValidationError("请指定模特角度（front / front45 / side / back135 / back）")
    data = model_service.save_image(angle, req.body)
    return 200, {"ok": True, "data": data}
