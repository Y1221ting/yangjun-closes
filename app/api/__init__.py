"""接口注册：所有路由统一在这里挂载。"""

from __future__ import annotations

from ..config import APP_NAME, APP_VERSION
from ..router import Request, Router
from . import garments, media, meta, model, outfits, trash


def _health(_req: Request) -> tuple[int, dict]:
    return 200, {"ok": True, "data": {"name": APP_NAME, "version": APP_VERSION}}


def build_router() -> Router:
    """构建全部接口路由。"""
    router = Router()

    router.get("/api/health")(_health)
    router.get("/api/meta")(meta.get_meta)

    router.get("/api/garments")(garments.list_garments)
    router.post("/api/garments")(garments.create_garment)
    router.put("/api/garments/order")(garments.reorder_garments)
    router.put("/api/garments/cabinet-slots")(garments.save_cabinet_slots)
    router.get("/api/garments/counts")(garments.counts)
    router.get("/api/garments/{id}")(garments.get_garment)
    router.put("/api/garments/{id}")(garments.update_garment)
    router.delete("/api/garments/{id}")(garments.delete_garment)
    router.post("/api/garments/{id}/images")(garments.upload_image)
    router.put("/api/garments/{id}/images/{angle}")(garments.adjust_image)

    router.get("/api/model")(model.get_model)
    router.post("/api/model/images")(model.upload_image)

    router.post("/api/scenes")(meta.add_scene)

    router.get("/api/outfits")(outfits.list_outfits)
    router.post("/api/outfits")(outfits.create_outfit)
    router.get("/api/outfits/{id}")(outfits.get_outfit)
    router.put("/api/outfits/{id}")(outfits.update_outfit)
    router.delete("/api/outfits/{id}")(outfits.delete_outfit)
    router.put("/api/outfits/{id}/items")(outfits.save_items)
    router.post("/api/outfits/{id}/images")(outfits.upload_image)
    router.put("/api/outfits/{id}/images/{angle}")(outfits.adjust_image)

    router.post("/api/export")(media.export_png)
    router.post("/api/exports/open")(media.open_exports)

    router.get("/api/trash")(trash.overview)
    router.post("/api/trash/garments/{id}/restore")(trash.restore_garment)
    router.delete("/api/trash/garments/{id}")(trash.purge_garment)
    router.post("/api/trash/outfits/{id}/restore")(trash.restore_outfit)
    router.delete("/api/trash/outfits/{id}")(trash.purge_outfit)
    router.post("/api/backup")(trash.create_backup)

    return router
