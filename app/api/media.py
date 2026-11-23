"""导出图片相关接口。"""

from __future__ import annotations

from ..router import Request
from ..services import export_service


def export_png(req: Request) -> tuple[int, dict]:
    name = req.query.get("name") or "搭配"
    data = export_service.save_png(name, req.body)
    return 200, {"ok": True, "data": data}


def open_exports(_req: Request) -> tuple[int, dict]:
    export_service.open_exports_folder()
    return 200, {"ok": True, "data": {"opened": True}}
