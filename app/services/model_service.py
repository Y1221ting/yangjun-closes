"""模特图业务：透明五角度处理与读取。"""

from __future__ import annotations

import io
from datetime import datetime

from PIL import Image

from ..config import ANGLES, MODEL_DIR
from ..errors import ServiceError, ValidationError
from ..utils import logger

MODEL_WIDTH = 1200
MODEL_HEIGHT = 1600
MODEL_CONTENT_HEIGHT = 1500      # 人物内容高度（不含留白）
MODEL_BASELINE = 1540            # 脚底基线
MODEL_MIN_SIDE = 300
MODEL_MAX_UPSCALE = 2.0


def get_model() -> dict:
    """读取已安装的模特五角度信息。"""
    images: dict[str, dict] = {}
    mtimes: list[float] = []

    for angle in ANGLES:
        path = MODEL_DIR / f"{angle}.webp"
        if not path.is_file():
            continue
        mtimes.append(path.stat().st_mtime)
        images[angle] = {
            "path": f"model/{angle}.webp",
            "width": MODEL_WIDTH,
            "height": MODEL_HEIGHT,
            "scale": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
        }

    if not images:
        return {"images": {}, "count": 0, "updated_at": None}

    updated = datetime.fromtimestamp(max(mtimes)).strftime("%Y-%m-%d %H:%M:%S")
    return {"images": images, "count": len(images), "updated_at": updated}


def save_image(angle: str, raw: bytes) -> dict:
    """保存一个角度的模特图：校验透明背景，统一成 1200×1600 透明 WebP。"""
    if angle not in ANGLES:
        raise ValidationError("未知的模特角度")
    if not raw:
        raise ServiceError("模特图片内容为空")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillow 异常类型不统一
        raise ServiceError("模特图片无法识别，请上传透明 PNG") from exc

    if min(img.size) < MODEL_MIN_SIDE:
        raise ServiceError(
            f"图片太小（{img.size[0]}×{img.size[1]}），最短边至少 {MODEL_MIN_SIDE} 像素"
        )

    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None or alpha.getextrema() == (255, 255):
        raise ServiceError("模特图必须是透明背景的 PNG")

    content_height = max(1, bbox[3] - bbox[1])
    scale = min(MODEL_MAX_UPSCALE, MODEL_CONTENT_HEIGHT / content_height)
    scaled = rgba.resize(
        (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))),
        Image.Resampling.LANCZOS,
    )

    scaled_bbox = scaled.getchannel("A").getbbox()
    if scaled_bbox is None:
        raise ServiceError("模特图没有可见内容")

    # 按脚底中心水平对齐，脚底对齐同一条基线，旋转时不会左右/上下跳。
    feet_top = bbox[3] - max(1, int(content_height * 0.06))
    feet_box = alpha.crop((bbox[0], feet_top, bbox[2], bbox[3])).getbbox()
    if feet_box is not None:
        feet_center = bbox[0] + (feet_box[0] + feet_box[2]) / 2
    else:
        feet_center = (bbox[0] + bbox[2]) / 2
    x = round(MODEL_WIDTH / 2 - feet_center * scale)
    y = round(MODEL_BASELINE - scaled_bbox[3])

    canvas = Image.new("RGBA", (MODEL_WIDTH, MODEL_HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, (x, y))

    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        original_dir = MODEL_DIR / "original"
        original_dir.mkdir(parents=True, exist_ok=True)
        rgba.save(original_dir / f"{angle}.png", "PNG")
        canvas.save(MODEL_DIR / f"{angle}.webp", "WEBP", quality=90, method=4)
    except OSError as exc:
        logger.exception("保存模特图失败 angle=%s", angle)
        raise ServiceError("保存模特图失败，请重试") from exc

    logger.info("已保存模特图 angle=%s size=%sx%s", angle, MODEL_WIDTH, MODEL_HEIGHT)
    return {
        "angle": angle,
        "path": f"model/{angle}.webp",
        "width": MODEL_WIDTH,
        "height": MODEL_HEIGHT,
        "scale": 1.0,
        "offset_x": 0.0,
        "offset_y": 0.0,
    }
