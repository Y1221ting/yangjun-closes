"""数据安全自检：软删除、回收站恢复、彻底删除、备份。

用法：.venv/Scripts/python.exe tests/test_phase7.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p7-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import GARMENTS_DIR  # noqa: E402
from app.db import init_db  # noqa: E402
from app.server import start_server  # noqa: E402
from app.services import backup_service  # noqa: E402
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
        with urllib.request.urlopen(request, timeout=30) as response:
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


def create_outfit(base: str, garment_id: int) -> int:
    body = json.dumps({"name": "安全测试搭配", "scenes": ["日常"]}, ensure_ascii=False)
    _, response = call("POST", f"{base}/api/outfits", body.encode("utf-8"), "application/json")
    outfit_id = response["data"]["id"]
    items = {
        "items": [{
            "garment_id": garment_id, "x": 0.5, "y": 0.4,
            "scale": 1, "rotation": 0, "z_index": 0,
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
        garment_id = create_garment(base, "回收站测试衣服")
        outfit_id = create_outfit(base, garment_id)
        folder = GARMENTS_DIR / str(garment_id)
        check(folder.is_dir(), "导入后图片目录存在")

        # 1. 软删除衣服
        status, _ = call("DELETE", f"{base}/api/garments/{garment_id}")
        check(status == 200, "删除衣服返回成功")
        _, response = call("GET", f"{base}/api/garments")
        check(len(response["data"]) == 0, "衣柜列表不再显示已删除衣服")
        status, _ = call("GET", f"{base}/api/garments/{garment_id}")
        check(status == 400, "已删除衣服无法直接读取")
        check(folder.is_dir(), "软删除后图片目录仍然保留")

        _, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(len(response["data"]["items"]["flat"]) == 0, "搭配中暂时隐藏已删除衣服")

        _, response = call("GET", f"{base}/api/trash")
        check(
            [g["id"] for g in response["data"]["garments"]] == [garment_id],
            "回收站里有这件衣服",
        )

        # 2. 恢复衣服
        status, _ = call("POST", f"{base}/api/trash/garments/{garment_id}/restore")
        check(status == 200, "从回收站恢复衣服")
        _, response = call("GET", f"{base}/api/garments")
        check(len(response["data"]) == 1, "恢复后衣柜重新显示衣服")
        _, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(len(response["data"]["items"]["flat"]) == 1, "恢复后搭配里的单品回来")

        # 3. 软删除并恢复搭配
        call("DELETE", f"{base}/api/outfits/{outfit_id}")
        _, response = call("GET", f"{base}/api/outfits")
        check(len(response["data"]) == 0, "搭配列表不再显示已删除搭配")
        _, response = call("GET", f"{base}/api/trash")
        check(
            [o["id"] for o in response["data"]["outfits"]] == [outfit_id],
            "回收站里有这套搭配",
        )
        call("POST", f"{base}/api/trash/outfits/{outfit_id}/restore")
        _, response = call("GET", f"{base}/api/outfits")
        check(len(response["data"]) == 1, "恢复后搭配重新显示")

        # 4. 彻底删除衣服
        call("DELETE", f"{base}/api/garments/{garment_id}")
        status, _ = call("DELETE", f"{base}/api/trash/garments/{garment_id}")
        check(status == 200, "彻底删除衣服")
        check(not folder.exists(), "彻底删除后图片目录被清理")
        _, response = call("GET", f"{base}/api/trash")
        check(len(response["data"]["garments"]) == 0, "回收站里不再有这件衣服")
        _, response = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(len(response["data"]["items"]["flat"]) == 0, "彻底删除后搭配条目级联清理")

        # 5. 彻底删除搭配
        call("DELETE", f"{base}/api/outfits/{outfit_id}")
        status, _ = call("DELETE", f"{base}/api/trash/outfits/{outfit_id}")
        check(status == 200, "彻底删除搭配")
        status, _ = call("GET", f"{base}/api/outfits/{outfit_id}")
        check(status == 400, "彻底删除后搭配无法读取")

        # 6. 数据库启动备份
        second_id = create_garment(base, "备份测试衣服")
        db_backup = backup_service.backup_database()
        check(db_backup is not None and db_backup.is_file(), "启动时数据库备份成功")

        # 7. 完整备份
        status, response = call("POST", f"{base}/api/backup")
        check(status == 200, "完整备份接口成功")
        backup = response["data"]
        backup_file = backup_service.BACKUP_DIR / backup["name"]
        check(backup_file.is_file(), "备份 zip 已生成")
        with zipfile.ZipFile(backup_file) as archive:
            names = archive.namelist()
        check("wardrobe.db" in names, "备份包含数据库")
        check(
            any(name.startswith(f"garments/{second_id}/") for name in names),
            "备份包含衣服图片",
        )
        check(
            not any(name.startswith("backups/") for name in names),
            "备份不包含备份目录本身",
        )

        call("DELETE", f"{base}/api/garments/{second_id}")
        call("DELETE", f"{base}/api/trash/garments/{second_id}")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
