"""图片处理：裁剪透明边、统一比例、转 WebP、生成缩略图。

单张处理流程：
1. 解码并确认带透明通道
2. 取 alpha 通道边界框，去掉四周透明空白
3. 统一高度（正面 1200px，侧面/背面与正面对齐）
4. 最长边不超过 1600px
5. 保存为 WebP（保留透明），原始 PNG 备份到 original/
"""

from __future__ import annotations

import io
import shutil

from PIL import Image

from ..config import (
    ANGLES,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    GARMENTS_DIR,
    OUTFITS_DIR,
)
from ..errors import ServiceError
from ..utils import logger

MIN_SIDE = 200              # 原图最短边下限
REFERENCE_HEIGHT = 1200     # 正面图统一高度
MAX_SIDE = 1600             # 处理后的最长边上限
MAX_UPSCALE = 2.0           # 正面图最多放大 2 倍（避免过度模糊）
MAX_UPSCALE_SIDE = 4.0      # 侧面/背面优先保证与正面等高，允许放大更多
THUMB_SIZE = 400


def _decode(raw: bytes) -> Image.Image:
    """把上传内容解码成带透明通道的 RGBA 图。"""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillow 抛出的异常类型不统一
        raise ServiceError("图片无法识别，请上传 PNG 格式的图片") from exc

    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if not has_alpha:
        raise ServiceError("这张图没有透明背景，请先用 AI 工具抠图后再上传")

    rgba = img.convert("RGBA")
    lowest = rgba.getchannel("A").getextrema()[0]
    if lowest == 255:
        raise ServiceError("这张图没有透明背景，请先用 AI 工具抠图后再上传")
    return rgba


def _crop_alpha(img: Image.Image) -> Image.Image:
    """裁掉四周完全透明的区域。"""
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        raise ServiceError("这张图的内容是空的，请重新导出后再上传")
    return img.crop(bbox)


def _fit_height(
    img: Image.Image, target_height: int, max_upscale: float = MAX_UPSCALE
) -> Image.Image:
    """等比缩放到目标高度，并限制最长边。"""
    width, height = img.size
    scale = target_height / height
    scale = min(scale, max_upscale)
    if abs(scale - 1) > 1e-3:
        img = img.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )

    width, height = img.size
    longest = max(width, height)
    if longest > MAX_SIDE:
        ratio = MAX_SIDE / longest
        img = img.resize(
            (max(1, round(width * ratio)), max(1, round(height * ratio))),
            Image.Resampling.LANCZOS,
        )
    return img


def process_image(
    garment_id: int,
    angle: str,
    raw: bytes,
    reference_height: int | None = None,
) -> dict:
    """处理并保存一张角度图，返回路径、尺寸和提示信息。"""
    if angle not in ANGLES:
        raise ServiceError("未知的图片角度")
    if not raw:
        raise ServiceError("图片内容为空")

    img = _decode(raw)
    if min(img.size) < MIN_SIDE:
        raise ServiceError(
            f"图片太小（{img.size[0]}×{img.size[1]}），最短边至少 {MIN_SIDE} 像素"
        )

    img = _crop_alpha(img)

    warnings: list[str] = []

    if angle == "front":
        img = _fit_height(img, REFERENCE_HEIGHT, MAX_UPSCALE)
    else:
        # 侧面/背面必须与正面等高，否则旋转时会对不齐；宁可放大稍糊
        target = reference_height or REFERENCE_HEIGHT
        img = _fit_height(img, target, MAX_UPSCALE_SIDE)
        if reference_height:
            diff = abs(img.size[1] - reference_height) / reference_height
            if diff > 0.02:
                warnings.append(
                    "侧面/背面图分辨率偏低，已尽量放大对齐，旋转时可能略有模糊"
                )

    folder = GARMENTS_DIR / str(garment_id)
    original_dir = folder / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    (original_dir / f"{angle}.png").write_bytes(raw)

    # method=4 比 method=6 快十几倍，体积只大 1% 左右
    output = folder / f"{angle}.webp"
    img.save(output, "WEBP", quality=90, method=4)

    return {
        "path": f"garments/{garment_id}/{angle}.webp",
        "width": img.size[0],
        "height": img.size[1],
        "warnings": warnings,
    }


def make_thumb(garment_id: int) -> dict | None:
    """用正面图生成衣柜缩略图。"""
    front = GARMENTS_DIR / str(garment_id) / "front.webp"
    if not front.is_file():
        return None
    with Image.open(front) as source:
        img = source.convert("RGBA")
        img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        output = GARMENTS_DIR / str(garment_id) / "thumb.webp"
        img.save(output, "WEBP", quality=85, method=4)
        return {
            "path": f"garments/{garment_id}/thumb.webp",
            "width": img.size[0],
            "height": img.size[1],
        }


def front_height(garment_id: int) -> int | None:
    """读取已处理正面图的高度，作为侧面/背面的对齐基准。"""
    front = GARMENTS_DIR / str(garment_id) / "front.webp"
    if not front.is_file():
        return None
    with Image.open(front) as img:
        return img.size[1]


def thumb_path(garment_id: int) -> str | None:
    """缩略图的相对路径（不存在时返回 None）。"""
    if (GARMENTS_DIR / str(garment_id) / "thumb.webp").is_file():
        return f"garments/{garment_id}/thumb.webp"
    return None


def delete_garment_dir(garment_id: int) -> None:
    """删除某件衣服的全部图片（失败只记日志，不阻断删除流程）。"""
    folder = GARMENTS_DIR / str(garment_id)
    if not folder.exists():
        return
    try:
        shutil.rmtree(folder)
    except OSError:
        logger.exception("删除衣服图片目录失败: %s", folder)


# ---------------------------------------------------------------- 搭配上身图

OUTFIT_MIN_SIDE = 300
OUTFIT_MAX_UPSCALE = 2.0
OUTFIT_THUMB_SIZE = 400


def process_outfit_image(outfit_id: int, angle: str, raw: bytes) -> dict:
    """把整套上身图统一到 1200×1600 的白底画布，便于多角度旋转。"""
    if angle not in ANGLES:
        raise ServiceError("未知的图片角度")
    if not raw:
        raise ServiceError("图片内容为空")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001 - Pillow 异常类型不统一
        raise ServiceError("图片无法识别，请上传 JPG 或 PNG") from exc

    if min(img.size) < OUTFIT_MIN_SIDE:
        raise ServiceError(
            f"图片太小（{img.size[0]}×{img.size[1]}），最短边至少 {OUTFIT_MIN_SIDE} 像素"
        )

    rgba = img.convert("RGBA")
    # 透明背景统一铺白；有背景的图保持原样
    flattened = Image.new("RGB", rgba.size, (255, 255, 255))
    flattened.paste(rgba, mask=rgba.getchannel("A"))

    scale = min(CANVAS_WIDTH / flattened.width, CANVAS_HEIGHT / flattened.height)
    scale = min(scale, OUTFIT_MAX_UPSCALE)
    if abs(scale - 1) > 1e-3:
        flattened = flattened.resize(
            (max(1, round(flattened.width * scale)), max(1, round(flattened.height * scale))),
            Image.Resampling.LANCZOS,
        )

    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (255, 255, 255))
    canvas.paste(
        flattened,
        (
            (CANVAS_WIDTH - flattened.width) // 2,
            (CANVAS_HEIGHT - flattened.height) // 2,
        ),
    )

    folder = OUTFITS_DIR / str(outfit_id)
    original_dir = folder / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    rgba.save(original_dir / f"{angle}.png", "PNG")

    output = folder / f"{angle}.webp"
    canvas.save(output, "WEBP", quality=90, method=4)

    return {
        "path": f"outfits/{outfit_id}/{angle}.webp",
        "width": canvas.width,
        "height": canvas.height,
    }


def make_outfit_thumb(outfit_id: int) -> dict | None:
    """用上身正面图生成搭配封面。"""
    front = OUTFITS_DIR / str(outfit_id) / "front.webp"
    if not front.is_file():
        return None
    with Image.open(front) as source:
        img = source.convert("RGB")
        img.thumbnail((OUTFIT_THUMB_SIZE, OUTFIT_THUMB_SIZE), Image.Resampling.LANCZOS)
        output = OUTFITS_DIR / str(outfit_id) / "thumb.webp"
        img.save(output, "WEBP", quality=85, method=4)
        return {
            "path": f"outfits/{outfit_id}/thumb.webp",
            "width": img.size[0],
            "height": img.size[1],
        }


def outfit_thumb_path(outfit_id: int) -> str | None:
    if (OUTFITS_DIR / str(outfit_id) / "thumb.webp").is_file():
        return f"outfits/{outfit_id}/thumb.webp"
    return None


def delete_outfit_dir(outfit_id: int) -> None:
    folder = OUTFITS_DIR / str(outfit_id)
    if not folder.exists():
        return
    try:
        shutil.rmtree(folder)
    except OSError:
        logger.exception("删除搭配图片目录失败: %s", folder)
