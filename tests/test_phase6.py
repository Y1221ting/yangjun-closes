"""阶段 6 自检：搭配上身图上传、统一画布、封面、微调与清理。

用法：.venv/Scripts/python.exe tests/test_phase6.py
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

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p6-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import OUTFITS_DIR  # noqa: E402
from app.db import init_db  # noqa: E402
from app.server import start_server  # noqa: E402
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


def call(method: str, url: str, data: bytes | None = None, ctype: str | None = None):
    request = urllib.request.Request(url, data=data, method=method)
    if ctype:
        request.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def make_photo(width: int = 600, height: int = 900) -> bytes:
    """模拟一张有背景的全身照（RGB，无透明通道）。"""
    image = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle([width // 3, height // 6, width * 2 // 3, height * 5 // 6],
                   fill=(205, 190, 170))
    draw.ellipse([width // 2 - 60, height // 8, width // 2 + 60, height // 8 + 120],
                 fill=(230, 210, 190))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def make_small() -> bytes:
    image = Image.new("RGB", (100, 100), (200, 200, 200))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def create_outfit(base: str) -> int:
    body = json.dumps({"name": "上身测试", "scenes": ["日常"]}, ensure_ascii=False)
    _, response = call("POST", f"{base}/api/outfits", body.encode("utf-8"), "application/json")
    return response["data"]["id"]


def upload(base: str, outfit_id: int, angle: str, raw: bytes):
    return call(
        "POST",
        f"{base}/api/outfits/{outfit_id}/images?angle={angle}",
        raw,
        "image/png",
    )


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        outfit_id = create_outfit(base)

        # 1. 上传正面
        status, response = upload(base, outfit_id, "front", make_photo())
        check(status == 200, "上传上身正面图")
        image = response["data"]
        check(image["path"].startswith(f"outfits/{outfit_id}/"), "图片路径正确")
        check(image["width"] == 1200 and image["height"] == 1600, "统一为 1200×1600 画布")
        check(
            (OUTFITS_DIR / str(outfit_id) / "front.webp").is_file(),
            "正面 WebP 已生成",
        )
        check(
            (OUTFITS_DIR / str(outfit_id) / "thumb.webp").is_file(),
            "搭配封面缩略图已生成",
        )
        check(
            (OUTFITS_DIR / str(outfit_id) / "original" / "front.png").is_file(),
            "原始图已备份",
        )

        # 2. 其他角度
        for angle in ("front45", "side", "back135", "back"):
            status, _ = upload(base, outfit_id, angle, make_photo())
            check(status == 200, f"上传 {angle} 成功")

        # 3. 详情与列表
        _, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        outfit = response["data"]
        check(
            set(outfit["images"]) == {"front", "front45", "side", "back135", "back"},
            "详情包含五个上身角度",
        )
        check(bool(outfit["worn_cover"]), "详情包含上身封面")

        _, response = call("GET", f"{base}/api/outfits")
        listed = response["data"][0]
        check(listed["cover"] == listed["worn_cover"], "列表封面优先使用上身图")

        # 4. 微调
        status, response = call(
            "PUT",
            f"{base}/api/outfits/{outfit_id}/images/side",
            json.dumps({"scale": 1.1, "offset_x": 2, "offset_y": -3}).encode("utf-8"),
            "application/json",
        )
        check(status == 200 and abs(response["data"]["scale"] - 1.1) < 1e-6, "上身图微调保存")

        _, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        side = response["data"]["images"]["side"]
        check(abs(side["offset_y"] + 3) < 1e-6, "微调写入数据库")

        # 5. 非法输入
        status, response = upload(base, outfit_id, "front", make_small())
        check(status == 400 and "太小" in response.get("error", ""), "拒绝过小的图片")
        status, response = upload(base, 99999, "front", make_photo())
        check(status == 400, "拒绝不存在的搭配")
        status, response = call(
            "PUT",
            f"{base}/api/outfits/{outfit_id}/images/nope",
            json.dumps({"scale": 1.0}).encode("utf-8"),
            "application/json",
        )
        check(status == 400, "拒绝未知角度")

        # 6. 删除搭配（软删除进回收站）
        folder = OUTFITS_DIR / str(outfit_id)
        status, _ = call("DELETE", f"{base}/api/outfits/{outfit_id}")
        check(status == 200, "删除搭配（移入回收站）")
        check(folder.exists(), "软删除后搭配图片仍然保留")

        status, _ = call("DELETE", f"{base}/api/trash/outfits/{outfit_id}")
        check(status == 200, "彻底删除搭配")
        check(not folder.exists(), "彻底删除后图片目录已清理")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
