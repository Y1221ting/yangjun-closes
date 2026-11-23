"""字典数据接口：类别、颜色、季节、场景、角度。"""

from __future__ import annotations

from ..config import (
    ANGLE_LABELS,
    ANGLES,
    APP_NAME,
    APP_VERSION,
    CATEGORIES,
    COLORS,
    DISPLAY_STYLES,
    SEASONS,
)
from ..router import Request
from ..services import meta_service


def _options(pairs: list[tuple[str, str]]) -> list[dict]:
    return [{"value": value, "label": label} for value, label in pairs]


def get_meta(_req: Request) -> tuple[int, dict]:
    return 200, {
        "ok": True,
        "data": {
            "app": {"name": APP_NAME, "version": APP_VERSION},
            "categories": _options(CATEGORIES),
            "colors": _options(COLORS),
            "seasons": _options(SEASONS),
            "display_styles": _options(DISPLAY_STYLES),
            "angles": [{"value": value, "label": ANGLE_LABELS[value]} for value in ANGLES],
            "scenes": meta_service.list_scenes(),
        },
    }


def add_scene(req: Request) -> tuple[int, dict]:
    payload = req.json()
    scenes = meta_service.add_scene(payload.get("name", ""))
    return 200, {"ok": True, "data": {"scenes": scenes}}
