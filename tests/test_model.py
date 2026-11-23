"""模特图自检：透明五角度处理、尺寸、读取与接口。

用临时数据目录运行，不会污染真实衣柜。
用法：.venv/Scripts/python.exe tests/test_model.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-model-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import ANGLES, MODEL_DIR  # noqa: E402
from app.db import init_db  # noqa: E402
from app.errors import ServiceError, ValidationError  # noqa: E402
from app.server import start_server  # noqa: E402
from app.services import model_service  # noqa: E402
from app.utils import ensure_dirs, setup_logging  # noqa: E402

PASSED = 0
FAILED = 0


def check(condition: bool, label: str, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {label}")
    else:
        FAILED += 1
        print(f"[FAIL] {label} {detail}")


def model_png() -> bytes:
    image = Image.new("RGBA", (800, 1200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([300, 80, 500, 280], fill=(235, 220, 205, 255),
                 outline=(120, 90, 70, 255), width=3)
    draw.rounded_rectangle([250, 260, 550, 900], radius=60,
                           fill=(190, 195, 200, 255),
                           outline=(120, 90, 70, 255), width=3)
    draw.rounded_rectangle([300, 880, 390, 1140], radius=30,
                           fill=(180, 185, 190, 255))
    draw.rounded_rectangle([410, 880, 500, 1140], radius=30,
                           fill=(180, 185, 190, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def opaque_png() -> bytes:
    image = Image.new("RGB", (800, 1200), (220, 220, 220))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def call(method: str, url: str, data: bytes | None = None, ctype: str | None = None):
    request = urllib.request.Request(url, data=data, method=method)
    if ctype:
        request.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    empty = model_service.get_model()
    check(empty["count"] == 0 and not empty["images"], "初始没有模特图")

    raw = model_png()
    for angle in ANGLES:
        result = model_service.save_image(angle, raw)
        check(result["path"] == f"model/{angle}.webp", f"保存 {angle} 路径正确")

    model = model_service.get_model()
    check(model["count"] == 5, "读取到五个角度")
    check(model["updated_at"] is not None, "返回更新时间")

    for angle in ANGLES:
        path = MODEL_DIR / f"{angle}.webp"
        check(path.is_file(), f"{angle} 文件存在")
        image = Image.open(path)
        check(image.size == (1200, 1600), f"{angle} 尺寸 1200×1600",
              str(image.size))
        check(image.mode == "RGBA", f"{angle} 保留透明通道", image.mode)
        alpha = image.convert("RGBA").getchannel("A")
        check(alpha.getextrema()[0] == 0, f"{angle} 背景透明")
        bbox = alpha.getbbox()
        check(bbox is not None and abs(bbox[3] - 1540) <= 2,
              f"{angle} 脚底基线对齐", str(bbox))
        check(bbox is not None and abs((bbox[3] - bbox[1]) - 1500) <= 12,
              f"{angle} 人物高度约 1500", str(bbox))

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"
    try:
        status, response = call("GET", base + "/api/model")
        check(status == 200 and response["data"]["count"] == 5,
              "接口返回五个角度")
        status, response = call(
            "POST", base + "/api/model/images?angle=front", raw, "image/png"
        )
        check(status == 200 and response["data"]["angle"] == "front",
              "接口可上传单个角度")
    finally:
        httpd.shutdown()
        httpd.server_close()

    try:
        model_service.save_image("unknown", raw)
        check(False, "拒绝未知角度")
    except ValidationError:
        check(True, "拒绝未知角度")
    except Exception as exc:  # noqa: BLE001
        check(False, "拒绝未知角度", repr(exc))

    try:
        model_service.save_image("front", opaque_png())
        check(False, "拒绝不透明图片")
    except ServiceError:
        check(True, "拒绝不透明图片")
    except Exception as exc:  # noqa: BLE001
        check(False, "拒绝不透明图片", repr(exc))

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
