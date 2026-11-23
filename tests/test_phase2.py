"""阶段 2 自检：多维度筛选、编辑信息、替换角度图。

用临时数据目录运行，不会污染真实衣柜。
用法：.venv/Scripts/python.exe tests/test_phase2.py
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

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p2-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import GARMENTS_DIR  # noqa: E402
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


def create(base: str, payload: dict) -> int:
    _, response = call(
        "POST",
        f"{base}/api/garments",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )
    return response["data"]["id"]


def names(response: dict) -> list[str]:
    return sorted(item["name"] for item in response.get("data", []))


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        a_id = create(base, {
            "name": "白色衬衫", "category": "top", "color": "white",
            "seasons": ["summer"], "occasions": ["日常"],
        })
        b_id = create(base, {
            "name": "黑色外套", "category": "outer", "color": "black",
            "seasons": ["winter"], "occasions": ["正式"],
        })

        for angle in ("front", "side", "back"):
            call("POST", f"{base}/api/garments/{a_id}/images?angle={angle}",
                 make_png(), "image/png")
        call("POST", f"{base}/api/garments/{b_id}/images?angle=front",
             make_png(), "image/png")

        # 1. 单条件筛选
        _, r = call("GET", f"{base}/api/garments?color=white")
        check(names(r) == ["白色衬衫"], "按颜色筛选")
        _, r = call("GET", f"{base}/api/garments?season=winter")
        check(names(r) == ["黑色外套"], "按季节筛选")
        _, r = call("GET", f"{base}/api/garments?scene=%E6%AD%A3%E5%BC%8F")
        check(names(r) == ["黑色外套"], "按场合筛选")
        _, r = call("GET", f"{base}/api/garments?category=outer")
        check(names(r) == ["黑色外套"], "按类别筛选")

        # 2. 组合筛选
        _, r = call("GET", f"{base}/api/garments?color=white&season=winter")
        check(len(r["data"]) == 0, "组合筛选无交集时返回空")
        _, r = call("GET", f"{base}/api/garments?color=black&season=winter")
        check(names(r) == ["黑色外套"], "组合筛选有交集时命中")

        # 3. 编辑信息
        updated = {
            "name": "白色衬衫改", "category": "top", "color": "beige",
            "seasons": ["spring"], "occasions": ["社交"],
        }
        status, r = call(
            "PUT", f"{base}/api/garments/{a_id}",
            json.dumps(updated, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        check(status == 200 and r["data"]["name"] == "白色衬衫改", "更新名称")
        check(r["data"]["color"] == "beige", "更新颜色")
        check(r["data"]["seasons"] == ["spring"], "更新季节")
        check(r["data"]["occasions"] == ["社交"], "更新场合")

        _, r = call("GET", f"{base}/api/garments?color=white")
        check(len(r["data"]) == 0, "改色后旧颜色筛选不到")
        _, r = call("GET", f"{base}/api/garments?color=beige")
        check(names(r) == ["白色衬衫改"], "改色后新颜色能筛选到")

        # 4. 替换正面图
        _, before = call("GET", f"{base}/api/garments/{a_id}")
        before_width = before["data"]["images"]["front"]["width"]
        before_updated = before["data"]["updated_at"]

        status, r = call(
            "POST", f"{base}/api/garments/{a_id}/images?angle=front",
            make_png(400, 1000), "image/png",
        )
        check(status == 200, "替换正面图成功")
        check(r["data"]["width"] != before_width, "替换后宽度发生变化")

        _, after = call("GET", f"{base}/api/garments/{a_id}")
        check(after["data"]["images"]["front"]["width"] == r["data"]["width"], "详情返回新尺寸")
        check((GARMENTS_DIR / str(a_id) / "thumb.webp").is_file(), "缩略图已重新生成")
        check(after["data"]["updated_at"] != before_updated, "替换图片后版本号变化")

        # 5. 不同尺寸的侧面图自动对齐到正面高度
        c_id = create(base, {"name": "对齐测试", "category": "top"})
        call("POST", f"{base}/api/garments/{c_id}/images?angle=front",
             make_png(600, 900), "image/png")
        status, side_resp = call(
            "POST", f"{base}/api/garments/{c_id}/images?angle=side",
            make_png(400, 600), "image/png",
        )
        _, c_detail = call("GET", f"{base}/api/garments/{c_id}")
        front_h = c_detail["data"]["images"]["front"]["height"]
        side_h = c_detail["data"]["images"]["side"]["height"]
        check(front_h == side_h, "侧面自动对齐正面高度", f"{front_h} vs {side_h}")
        check(side_resp["data"]["warnings"] == [], "对齐成功时没有警告")
        call("DELETE", f"{base}/api/garments/{c_id}")

        # 6. 五角度上传
        d_id = create(base, {"name": "五角度测试", "category": "top"})
        for angle in ("front", "front45", "side", "back135", "back"):
            status, _ = call(
                "POST", f"{base}/api/garments/{d_id}/images?angle={angle}",
                make_png(), "image/png",
            )
            check(status == 200, f"上传 {angle} 角度成功")
        _, r = call("GET", f"{base}/api/garments/{d_id}")
        check(
            set(r["data"]["images"]) == {"front", "front45", "side", "back135", "back"},
            "详情包含五个角度",
        )

        # 7. 角度微调
        status, r = call(
            "PUT", f"{base}/api/garments/{d_id}/images/side",
            json.dumps({"scale": 1.15, "offset_x": 3, "offset_y": -5}).encode("utf-8"),
            "application/json",
        )
        check(status == 200 and abs(r["data"]["scale"] - 1.15) < 1e-6, "保存角度微调")

        _, r = call("GET", f"{base}/api/garments/{d_id}")
        side = r["data"]["images"]["side"]
        check(abs(side["offset_y"] + 5) < 1e-6, "微调写入数据库")
        check(abs(side["offset_x"] - 3) < 1e-6, "微调水平偏移正确")

        status, r = call(
            "PUT", f"{base}/api/garments/{d_id}/images/side",
            json.dumps({"scale": 5}).encode("utf-8"),
            "application/json",
        )
        check(status == 400, "拒绝超出范围的大小")

        status, r = call(
            "PUT", f"{base}/api/garments/{d_id}/images/front",
            json.dumps({"scale": 1.0}).encode("utf-8"),
            "application/json",
        )
        check(status == 200, "正面也可以微调")

        call("DELETE", f"{base}/api/garments/{d_id}")

        # 8. 没有图片时不能微调
        e_id = create(base, {"name": "空衣物", "category": "top"})
        status, r = call(
            "PUT", f"{base}/api/garments/{e_id}/images/front",
            json.dumps({"scale": 1.0}).encode("utf-8"),
            "application/json",
        )
        check(status == 400 and "图片" in r.get("error", ""), "没有图片时拒绝微调")
        call("DELETE", f"{base}/api/garments/{e_id}")

        # 9. 非法编辑
        status, r = call(
            "PUT", f"{base}/api/garments/{a_id}",
            json.dumps({"name": "", "category": "top"}, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        check(status == 400 and "名称" in r.get("error", ""), "拒绝空名称的编辑")

        # 10. 删除后筛选
        call("DELETE", f"{base}/api/garments/{b_id}")
        _, r = call("GET", f"{base}/api/garments?season=winter")
        check(len(r["data"]) == 0, "删除后对应季节筛选为空")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
