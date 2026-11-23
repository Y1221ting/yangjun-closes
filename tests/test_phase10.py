"""阶段 10 自检：衣帽柜格位、帽子类别、抽屉摆放方式。

用临时数据目录运行，不会污染真实衣柜。
用法：.venv/Scripts/python.exe tests/test_phase10.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p10-"))
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


def create(base: str, payload: dict) -> dict:
    status, response = post_json(base, "/api/garments", payload)
    check(status == 200, f"创建 {payload['name']}", str(response))
    return response["data"]


def get(base: str, garment_id: int) -> dict:
    _, response = call("GET", f"{base}/api/garments/{garment_id}")
    return response["data"]


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()
    init_db()

    conn = get_conn()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(garments)")
        }
    finally:
        conn.close()

    check(version == SCHEMA_VERSION == 8, "数据库版本为 v8", f"实际 {version}")
    check("cabinet_slot" in columns, "garments 新增 cabinet_slot 字段")

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        status, meta = call("GET", base + "/api/meta")
        data = meta["data"]
        values = [item["value"] for item in data["categories"]]
        styles = [item["value"] for item in data["display_styles"]]
        check(status == 200, "读取字典数据")
        check("hat" in values and len(values) == 8, "字典包含帽子类别")
        check("drawer" in styles and len(styles) == 4, "字典包含抽屉摆放方式")

        # 1. 鞋子格位：8 双填满基础格，第 9 双自动进入扩展格
        shoes = []
        for index in range(8):
            item = create(base, {
                "name": f"测试鞋 {index + 1}", "category": "shoes", "color": "black",
            })
            shoes.append(item)
            check(item["cabinet_slot"] == index, f"鞋子 {index + 1} 分配到格位 {index}")
        ninth = create(base, {
            "name": "测试鞋 9", "category": "shoes", "color": "brown",
        })
        check(ninth["cabinet_slot"] == 8, "第 9 双鞋分配到扩展格位 8")

        # 2. 帽子类别和格位
        hats = []
        for index in range(3):
            item = create(base, {
                "name": f"测试帽 {index + 1}", "category": "hat", "color": "beige",
            })
            hats.append(item)
            check(item["cabinet_slot"] == index, f"帽子 {index + 1} 分配到格位 {index}")
        check(hats[0]["category"] == "hat", "帽子类别保存正确")
        check(hats[0]["display_style"] == "hang", "非配饰类别使用默认摆放方式")

        # 3. 包格位：6 个基础格，第 7 个进入扩展格
        bags = []
        for index in range(6):
            item = create(base, {
                "name": f"测试包 {index + 1}", "category": "bag", "color": "brown",
            })
            bags.append(item)
            check(item["cabinet_slot"] == index, f"包 {index + 1} 分配到格位 {index}")
        seventh_bag = create(base, {
            "name": "测试包 7", "category": "bag", "color": "black",
        })
        check(seventh_bag["cabinet_slot"] == 6, "第 7 个包分配到扩展格位 6")

        # 4. 配饰抽屉格位
        drawer_one = create(base, {
            "name": "抽屉配饰 1", "category": "accessory", "color": "beige",
            "display_style": "drawer",
        })
        drawer_two = create(base, {
            "name": "抽屉配饰 2", "category": "accessory", "color": "pink",
            "display_style": "drawer",
        })
        check(drawer_one["cabinet_slot"] == 0, "第一个抽屉配饰分配到抽屉格 0")
        check(drawer_two["cabinet_slot"] == 1, "第二个抽屉配饰分配到抽屉格 1")

        hang = create(base, {
            "name": "挂杆配饰", "category": "accessory", "color": "white",
            "display_style": "hang",
        })
        top = create(base, {
            "name": "测试上衣", "category": "top", "color": "white",
        })
        check(hang["cabinet_slot"] is None, "挂杆配饰不占柜子格位")
        check(top["cabinet_slot"] is None, "上衣不占柜子格位")

        # 5. 修改摆放方式：抽屉 -> 挂杆，清空格位；挂杆 -> 抽屉，补第一个空格
        status, r = put_json(base, f"/api/garments/{drawer_one['id']}", {
            "name": "抽屉配饰 1", "category": "accessory", "color": "beige",
            "display_style": "hang",
        })
        check(status == 200 and r["data"]["cabinet_slot"] is None,
              "改成挂杆后释放抽屉格位")
        status, r = put_json(base, f"/api/garments/{hang['id']}", {
            "name": "挂杆配饰", "category": "accessory", "color": "white",
            "display_style": "drawer",
        })
        check(status == 200 and r["data"]["cabinet_slot"] == 0,
              "改成抽屉后补进第一个空格 0")

        # 6. 格位交换
        first = shoes[0]["id"]
        second = shoes[1]["id"]
        status, r = put_json(base, "/api/garments/cabinet-slots", {
            "items": [{"id": first, "slot": 1}, {"id": second, "slot": 0}],
        })
        check(status == 200 and r["data"]["updated"] == 2, "保存两件鞋子的交换")
        check(get(base, first)["cabinet_slot"] == 1, "第一双鞋移动到格位 1")
        check(get(base, second)["cabinet_slot"] == 0, "第二双鞋移动到格位 0")

        # 7. 冲突和重复格位被拒绝
        third = shoes[2]["id"]
        status, r = put_json(base, "/api/garments/cabinet-slots", {
            "items": [{"id": first, "slot": 2}],
        })
        check(status == 400 and "占用" in r.get("error", ""), "拒绝移到已占用的格子")
        status, r = put_json(base, "/api/garments/cabinet-slots", {
            "items": [
                {"id": first, "slot": 5},
                {"id": third, "slot": 5},
            ],
        })
        check(status == 400, "拒绝把两件物品放在同一个格子")

        # 8. 删除后新物品补第一个空格；恢复时若格位被占，自动重新分配
        victim = shoes[5]["id"]
        victim_slot = get(base, victim)["cabinet_slot"]
        status, _ = call("DELETE", f"{base}/api/garments/{victim}")
        check(status == 200, "移入回收站")
        newcomer = create(base, {
            "name": "新鞋补位", "category": "shoes", "color": "gray",
        })
        check(newcomer["cabinet_slot"] == victim_slot, "新鞋补进删除后的空格")
        status, r = call("POST", f"{base}/api/trash/garments/{victim}/restore")
        restored = r["data"]
        check(status == 200, "从回收站恢复")
        check(restored["cabinet_slot"] != victim_slot,
              "原格位被占后恢复时自动换格")
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
