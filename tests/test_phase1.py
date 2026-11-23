"""阶段 1 自检：数据库、衣服接口、图片处理。

用临时数据目录运行，不会污染真实衣柜。
用法：.venv/Scripts/python.exe tests/test_phase1.py
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

# 必须在导入 app 之前设置，config 在导入时读取这两个变量
_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-test-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import DATA_DIR, GARMENTS_DIR  # noqa: E402
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


def make_png(width: int = 600, height: int = 900, opaque: bool = False) -> bytes:
    """生成一张带透明边距的测试图；opaque=True 时不留透明区域。"""
    mode = "RGB" if opaque else "RGBA"
    background = (255, 255, 255) if opaque else (0, 0, 0, 0)
    image = Image.new(mode, (width, height), background)
    draw = ImageDraw.Draw(image)
    fill = (200, 180, 160) if opaque else (200, 180, 160, 255)
    draw.rectangle([100, 150, width - 100, height - 100], fill=fill)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        # 1. 字典接口
        status, payload = call("GET", f"{base}/api/meta")
        meta = payload.get("data", {})
        check(status == 200 and payload.get("ok"), "GET /api/meta 返回成功")
        check(len(meta.get("categories", [])) == 8, "类别数量为 8")
        check(meta.get("scenes") == ["日常", "社交", "休闲", "正式"], "内置场景标签正确")

        # 2. 新建衣服
        body = json.dumps(
            {
                "name": "测试白T",
                "category": "top",
                "color": "white",
                "seasons": ["spring", "summer"],
                "occasions": ["日常"],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        status, payload = call("POST", f"{base}/api/garments", body, "application/json")
        garment = payload.get("data", {})
        garment_id = garment.get("id")
        check(status == 200 and payload.get("ok"), "POST /api/garments 创建成功")
        check(bool(garment_id), "返回了衣服编号")

        # 3. 先传侧面应该被拒绝
        status, payload = call(
            "POST",
            f"{base}/api/garments/{garment_id}/images?angle=side",
            make_png(),
            "image/png",
        )
        check(status == 400 and "正面" in payload.get("error", ""), "未传正面时拒绝侧面图")

        # 4. 上传三张角度图
        for angle in ("front", "side", "back"):
            status, payload = call(
                "POST",
                f"{base}/api/garments/{garment_id}/images?angle={angle}",
                make_png(),
                "image/png",
            )
            check(status == 200 and payload.get("ok"), f"上传 {angle} 图成功")

        # 5. 处理后的文件与缩略图
        folder = GARMENTS_DIR / str(garment_id)
        for name in ("front.webp", "side.webp", "back.webp", "thumb.webp"):
            check((folder / name).is_file(), f"生成文件 {name}")
        check((folder / "original" / "front.png").is_file(), "保留原始正面图")

        # 6. 列表与详情
        status, payload = call("GET", f"{base}/api/garments")
        items = payload.get("data", [])
        check(len(items) == 1, "列表返回 1 件衣服")
        check(set(items[0].get("images", {})) == {"front", "side", "back"}, "详情包含三张图")
        check(bool(items[0].get("thumb")), "列表包含缩略图路径")

        status, payload = call("GET", f"{base}/api/garments/{garment_id}")
        check(payload.get("data", {}).get("name") == "测试白T", "详情名称正确")
        check(payload["data"]["seasons"] == ["spring", "summer"], "季节字段解析正确")

        # 7. 筛选与搜索
        status, payload = call("GET", f"{base}/api/garments?category=top")
        check(len(payload.get("data", [])) == 1, "按类别筛选到 1 件")
        status, payload = call("GET", f"{base}/api/garments?category=shoes")
        check(len(payload.get("data", [])) == 0, "按类别筛选到 0 件")
        status, payload = call("GET", f"{base}/api/garments?q=%E7%99%BDT")
        check(len(payload.get("data", [])) == 1, "按名称搜索命中")
        status, payload = call("GET", f"{base}/api/garments?season=winter")
        check(len(payload.get("data", [])) == 0, "按季节筛选冬季为 0")
        status, payload = call("GET", f"{base}/api/garments?season=summer")
        check(len(payload.get("data", [])) == 1, "按季节筛选夏季为 1")

        # 8. 无透明背景的图片应被拒绝
        status, payload = call(
            "POST",
            f"{base}/api/garments/{garment_id}/images?angle=front",
            make_png(opaque=True),
            "image/png",
        )
        check(status == 400 and "透明" in payload.get("error", ""), "拒绝无透明背景的图片")

        # 9. 参数校验
        status, payload = call(
            "POST",
            f"{base}/api/garments",
            json.dumps({"name": "", "category": "top"}, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        check(status == 400 and "名称" in payload.get("error", ""), "拒绝空名称")

        status, payload = call(
            "POST",
            f"{base}/api/garments",
            json.dumps({"name": "测试鞋", "category": "unknown"}, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        check(status == 400 and "类别" in payload.get("error", ""), "拒绝非法类别")

        # 10. 删除（软删除进回收站）
        status, payload = call("DELETE", f"{base}/api/garments/{garment_id}")
        check(status == 200 and payload.get("ok"), "删除衣服成功（移入回收站）")
        check(folder.exists(), "软删除后图片仍然保留")
        status, payload = call("GET", f"{base}/api/garments")
        check(len(payload.get("data", [])) == 0, "删除后列表为空")

        status, payload = call("DELETE", f"{base}/api/trash/garments/{garment_id}")
        check(status == 200, "彻底删除衣服")
        check(not folder.exists(), "彻底删除后图片目录已清理")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    print(f"临时数据目录：{_TEMP_ROOT}")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
