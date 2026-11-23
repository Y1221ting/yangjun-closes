"""阶段 9 自检：配饰摆放方式（挂杆 / 纸袋 / 平放）。

用临时数据目录运行，不会污染真实衣柜。
用法：.venv/Scripts/python.exe tests/test_phase9.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p9-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SCHEMA_VERSION, get_conn, init_db  # noqa: E402
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


def post_json(base: str, path: str, payload: dict):
    return call(
        "POST",
        base + path,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )


def put_json(base: str, path: str, payload: dict):
    return call(
        "PUT",
        base + path,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json",
    )


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()
    init_db()  # 迁移应可重复执行

    conn = get_conn()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(garments)")
        }
    finally:
        conn.close()

    check(version == SCHEMA_VERSION == 8, "数据库版本为 v8", f"实际 {version}")
    check("display_style" in columns, "garments 新增 display_style 字段")

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        status, meta = call("GET", base + "/api/meta")
        styles = meta["data"]["display_styles"]
        check(status == 200, "读取字典数据")
        check(
            [item["value"] for item in styles] == ["hang", "bag", "flat", "drawer"],
            "字典包含四种摆放方式",
        )
        check(
            [item["label"] for item in styles] == ["挂杆", "纸袋", "平放", "抽屉"],
            "摆放方式中文标签正确",
        )

        # 1. 不传摆放方式时默认挂杆
        status, r = post_json(base, "/api/garments", {
            "name": "测试围巾", "category": "accessory", "color": "beige",
        })
        scarf_id = r["data"]["id"]
        check(status == 200 and r["data"]["display_style"] == "hang",
              "配饰默认摆放在挂杆")

        # 2. 创建时指定纸袋
        status, r = post_json(base, "/api/garments", {
            "name": "测试手套", "category": "accessory", "color": "red",
            "display_style": "bag",
        })
        check(status == 200 and r["data"]["display_style"] == "bag",
              "创建时保存纸袋摆放")

        # 3. 创建时指定平放
        status, r = post_json(base, "/api/garments", {
            "name": "测试项链", "category": "accessory", "color": "yellow",
            "display_style": "flat",
        })
        check(status == 200 and r["data"]["display_style"] == "flat",
              "创建时保存平放摆放")

        # 4. 非法摆放方式被拒绝
        status, r = post_json(base, "/api/garments", {
            "name": "测试错误配饰", "category": "accessory",
            "display_style": "shelf",
        })
        check(status == 400 and "摆放方式" in r.get("error", ""),
              "拒绝非法摆放方式")

        # 5. 编辑时修改摆放方式
        status, r = put_json(base, f"/api/garments/{scarf_id}", {
            "name": "测试围巾", "category": "accessory", "color": "beige",
            "display_style": "flat",
        })
        check(status == 200 and r["data"]["display_style"] == "flat",
              "编辑时修改摆放方式")

        # 6. 列表和详情都返回摆放方式
        _, r = call("GET", base + "/api/garments")
        styles_by_name = {item["name"]: item["display_style"] for item in r["data"]}
        check(styles_by_name.get("测试围巾") == "flat", "列表返回摆放方式")
        check(styles_by_name.get("测试手套") == "bag", "列表保留不同摆放方式")
        _, r = call("GET", f"{base}/api/garments/{scarf_id}")
        check(r["data"]["display_style"] == "flat", "详情返回摆放方式")

        # 7. 非配饰类别也能正常保存，不影响原有功能
        status, r = post_json(base, "/api/garments", {
            "name": "测试上衣", "category": "top", "color": "white",
        })
        check(status == 200 and r["data"]["display_style"] == "hang",
              "非配饰类别使用默认值")
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
