"""阶段 5/6 自检：搭配筛选、封面数据、导出 PNG。

用法：.venv/Scripts/python.exe tests/test_phase5.py
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

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p5-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import EXPORTS_DIR  # noqa: E402
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


def make_png(width: int = 600, height: int = 900) -> bytes:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle([100, 150, width - 100, height - 100], fill=(200, 190, 175, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def create_garment(base: str, name: str) -> int:
    body = json.dumps({"name": name, "category": "top"}, ensure_ascii=False)
    _, response = call("POST", f"{base}/api/garments", body.encode("utf-8"), "application/json")
    garment_id = response["data"]["id"]
    call(
        "POST", f"{base}/api/garments/{garment_id}/images?angle=front",
        make_png(), "image/png",
    )
    return garment_id


def create_outfit(base: str, name: str, scenes: list, garment_id: int) -> int:
    body = json.dumps({"name": name, "scenes": scenes}, ensure_ascii=False)
    _, response = call("POST", f"{base}/api/outfits", body.encode("utf-8"), "application/json")
    outfit_id = response["data"]["id"]
    items = {
        "items": [{
            "garment_id": garment_id,
            "x": 0.5, "y": 0.4, "scale": 1.1, "rotation": 5, "z_index": 0,
        }]
    }
    call(
        "PUT", f"{base}/api/outfits/{outfit_id}/items?view=flat",
        json.dumps(items).encode("utf-8"), "application/json",
    )
    return outfit_id


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        first = create_garment(base, "日常上衣")
        second = create_garment(base, "正式上衣")
        daily_id = create_outfit(base, "周末出门", ["日常", "休闲"], first)
        formal_id = create_outfit(base, "面试正装", ["正式"], second)

        # 1. 列表带画布布局
        _, response = call("GET", f"{base}/api/outfits")
        outfits = response["data"]
        check(len(outfits) == 2, "搭配列表返回 2 套")
        sample = outfits[0]
        check(len(sample["items"]) == 1, "列表包含画布单品")
        check("image" in sample["items"][0], "单品带封面图片路径")
        check(abs(sample["items"][0]["x"] - 0.5) < 1e-6, "单品位置正确")

        # 2. 场景筛选
        _, response = call("GET", f"{base}/api/outfits?scene=%E6%97%A5%E5%B8%B8")
        check([o["name"] for o in response["data"]] == ["周末出门"], "按场景筛选日常")
        _, response = call("GET", f"{base}/api/outfits?scene=%E6%AD%A3%E5%BC%8F")
        check([o["name"] for o in response["data"]] == ["面试正装"], "按场景筛选正式")

        # 3. 名称搜索
        _, response = call("GET", f"{base}/api/outfits?q=%E9%9D%A2%E8%AF%95")
        check([o["name"] for o in response["data"]] == ["面试正装"], "按名称搜索面试")
        _, response = call("GET", f"{base}/api/outfits?q=%E4%B8%8D%E5%AD%98%E5%9C%A8")
        check(len(response["data"]) == 0, "搜索不存在的名称返回空")

        # 4. 组合筛选
        _, response = call(
            "GET", f"{base}/api/outfits?scene=%E6%AD%A3%E5%BC%8F&q=%E5%91%A8%E6%9C%AB"
        )
        check(len(response["data"]) == 0, "场景与关键词组合无交集")

        # 5. 导出 PNG
        status, response = call(
            "POST", f"{base}/api/export?name=%E5%91%A8%E6%9C%AB%E5%87%BA%E9%97%A8",
            make_png(1200, 1600), "image/png",
        )
        check(status == 200, "导出接口返回成功")
        exported = response["data"]
        check(exported["name"].startswith("周末出门_"), "导出文件名包含搭配名")
        check((EXPORTS_DIR / exported["name"]).is_file(), "导出文件已写入磁盘")
        check(exported["size"] > 0, "导出文件大小正常")

        # 6. 非法导出
        status, response = call(
            "POST", f"{base}/api/export?name=test", b"not a png", "application/octet-stream"
        )
        check(status == 400, "拒绝非 PNG 内容")
        status, response = call("POST", f"{base}/api/export?name=test", b"", "image/png")
        check(status == 400, "拒绝空内容")

        # 7. 删除搭配后筛选
        call("DELETE", f"{base}/api/outfits/{daily_id}")
        _, response = call("GET", f"{base}/api/outfits?scene=%E6%97%A5%E5%B8%B8")
        check(len(response["data"]) == 0, "删除后场景筛选为空")

        call("DELETE", f"{base}/api/outfits/{formal_id}")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
