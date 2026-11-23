"""阶段 4 自检：搭配增删改查、画布布局保存、级联清理。

用临时数据目录运行，不会污染真实衣物。
用法：.venv/Scripts/python.exe tests/test_phase4.py
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

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p4-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

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


def create_garment(base: str, name: str, category: str) -> int:
    body = json.dumps({"name": name, "category": category}, ensure_ascii=False)
    _, response = call(
        "POST", f"{base}/api/garments", body.encode("utf-8"), "application/json"
    )
    garment_id = response["data"]["id"]
    call(
        "POST", f"{base}/api/garments/{garment_id}/images?angle=front",
        make_png(), "image/png",
    )
    return garment_id


def save_layout(base: str, outfit_id: int, items: list) -> tuple[int, dict]:
    return call(
        "PUT",
        f"{base}/api/outfits/{outfit_id}/items?view=flat",
        json.dumps({"items": items}).encode("utf-8"),
        "application/json",
    )


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        top_id = create_garment(base, "白色上衣", "top")
        bottom_id = create_garment(base, "蓝色牛仔裤", "bottom")

        # 1. 新建搭配
        body = json.dumps({"name": "周末出门", "scenes": ["日常", "休闲"]}, ensure_ascii=False)
        status, response = call(
            "POST", f"{base}/api/outfits", body.encode("utf-8"), "application/json"
        )
        outfit = response["data"]
        outfit_id = outfit["id"]
        check(status == 200 and outfit["name"] == "周末出门", "新建搭配")
        check(outfit["scenes"] == ["日常", "休闲"], "场景标签保存正确")
        check(outfit["items"] == {"flat": [], "worn": []}, "新搭配画布为空")

        # 2. 保存画布布局
        items = [
            {"garment_id": top_id, "x": 0.5, "y": 0.34, "scale": 1.0,
             "rotation": 0, "z_index": 0, "clip_top": 0.15, "clip_bottom": 0.85},
            {"garment_id": bottom_id, "x": 0.5, "y": 0.66, "scale": 1.2,
             "rotation": 5, "z_index": 1},
        ]
        status, response = save_layout(base, outfit_id, items)
        check(status == 200, "保存画布布局")
        flat = response["data"]["items"]["flat"]
        check(len(flat) == 2, "画布包含两件单品")
        check(flat[0]["garment"]["name"] == "白色上衣", "单品带衣服名称")
        check(flat[0]["garment"]["image"].endswith("front.webp"), "单品带正面图路径")
        check(abs(flat[1]["rotation"] - 5) < 1e-6, "旋转角度保存正确")
        check(abs(flat[0]["clip_top"] - 0.15) < 1e-6, "上边缘裁切保存正确")
        check(abs(flat[0]["clip_bottom"] - 0.85) < 1e-6, "下边缘裁切保存正确")
        check(flat[1]["clip_top"] == 0.0 and flat[1]["clip_bottom"] == 1.0, "裁切默认值正确")

        # 3. 列表与封面
        status, response = call("GET", f"{base}/api/outfits")
        outfits = response["data"]
        check(len(outfits) == 1, "搭配列表返回 1 套")
        check(outfits[0]["item_count"] == 2, "搭配件数正确")
        check(outfits[0]["cover"].endswith("thumb.webp"), "搭配有封面")

        # 4. 修改名称与场景
        body = json.dumps({"name": "周末约会", "scenes": ["社交"]}, ensure_ascii=False)
        status, response = call(
            "PUT", f"{base}/api/outfits/{outfit_id}",
            body.encode("utf-8"), "application/json",
        )
        check(status == 200 and response["data"]["name"] == "周末约会", "修改搭配名称")
        check(response["data"]["scenes"] == ["社交"], "修改场景标签")

        # 5. 数值钳制
        status, response = save_layout(
            base, outfit_id,
            [{"garment_id": top_id, "x": 2, "y": -1, "scale": 99,
              "rotation": 999, "z_index": -5}],
        )
        item = response["data"]["items"]["flat"][0]
        check(item["x"] == 1.0 and item["y"] == 0.0, "坐标被钳制到 0~1")
        check(item["scale"] == 5.0, "缩放被钳制到上限")
        check(item["rotation"] == 180.0, "旋转被钳制到上限")
        check(item["z_index"] == 0, "层级被钳制到下限")

        # 上边缘大于下边缘时自动交换，保证裁切区间有效
        status, response = save_layout(
            base, outfit_id,
            [{"garment_id": top_id, "x": 0.5, "y": 0.5, "scale": 1,
              "rotation": 0, "z_index": 0, "clip_top": 2, "clip_bottom": -1}],
        )
        clipped = response["data"]["items"]["flat"][0]
        check(
            clipped["clip_top"] <= clipped["clip_bottom"],
            "裁切区间自动纠正",
            f"{clipped['clip_top']} / {clipped['clip_bottom']}",
        )

        # 6. 非法衣服
        status, response = save_layout(
            base, outfit_id,
            [{"garment_id": 99999, "x": 0.5, "y": 0.5, "scale": 1,
              "rotation": 0, "z_index": 0}],
        )
        check(status == 400, "拒绝不存在的衣服")

        # 7. 删除衣服后搭配条目级联清理
        save_layout(base, outfit_id, [
            {"garment_id": top_id, "x": 0.5, "y": 0.3, "scale": 1,
             "rotation": 0, "z_index": 0},
            {"garment_id": bottom_id, "x": 0.5, "y": 0.7, "scale": 1,
             "rotation": 0, "z_index": 1},
        ])
        call("DELETE", f"{base}/api/garments/{top_id}")
        status, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(len(response["data"]["items"]["flat"]) == 1, "删除衣服后搭配条目自动清理")

        # 8. 删除搭配
        status, response = call("DELETE", f"{base}/api/outfits/{outfit_id}")
        check(status == 200, "删除搭配")
        status, response = call("GET", f"{base}/api/outfits")
        check(len(response["data"]) == 0, "删除后搭配列表为空")
        status, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(status == 400, "已删除的搭配无法读取")

        # 9. 空名称校验
        status, response = call(
            "POST", f"{base}/api/outfits",
            json.dumps({"name": ""}).encode("utf-8"), "application/json",
        )
        check(status == 400 and "名称" in response.get("error", ""), "拒绝空搭配名称")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
