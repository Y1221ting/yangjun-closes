"""挂杆排序自检：同类别拖动排序、新衣服排在末尾、非法输入。

用法：.venv/Scripts/python.exe tests/test_phase8.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-p8-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def create(base: str, name: str, category: str = "top") -> int:
    body = json.dumps({"name": name, "category": category}, ensure_ascii=False)
    _, response = call(
        "POST", f"{base}/api/garments", body.encode("utf-8"), "application/json"
    )
    return response["data"]["id"]


def names(base: str, category: str = "top") -> list[str]:
    _, response = call("GET", f"{base}/api/garments?category={category}")
    return [item["name"] for item in response["data"]]


def reorder(base: str, ids: list):
    return call(
        "PUT",
        f"{base}/api/garments/order",
        json.dumps({"ids": ids}).encode("utf-8"),
        "application/json",
    )


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"

    try:
        first = create(base, "上衣一")
        second = create(base, "上衣二")
        third = create(base, "上衣三")
        outer = create(base, "外套一", "outer")

        check(
            names(base) == ["上衣一", "上衣二", "上衣三"],
            "初始顺序为导入顺序（新衣服排在末尾）",
        )
        check(names(base, "outer") == ["外套一"], "其他类别不受影响")

        # 1. 保存新顺序
        status, response = reorder(base, [first, third, second])
        check(status == 200 and response["data"]["reordered"] == 3, "保存排序成功")
        check(names(base) == ["上衣一", "上衣三", "上衣二"], "排序结果正确")

        # 2. 新衣服排在末尾（sort_order 递增）
        fourth = create(base, "上衣四")
        check(
            names(base) == ["上衣一", "上衣三", "上衣二", "上衣四"],
            "新衣服排在同类末尾",
        )

        # 3. 再排一次
        reorder(base, [fourth, second, first, third])
        check(
            names(base) == ["上衣四", "上衣二", "上衣一", "上衣三"],
            "再次排序结果正确",
        )

        # 4. 删除的衣服不参与排序
        call("DELETE", f"{base}/api/garments/{second}")
        reorder(base, [third, first, fourth])
        check(
            names(base) == ["上衣三", "上衣一", "上衣四"],
            "删除后排序正常",
        )

        # 5. 非法输入
        status, _ = reorder(base, [])
        check(status == 400, "拒绝空排序")
        status, _ = call(
            "PUT",
            f"{base}/api/garments/order",
            json.dumps({"ids": ["x"]}).encode("utf-8"),
            "application/json",
        )
        check(status == 400, "拒绝非数字编号")
        status, _ = call(
            "PUT",
            f"{base}/api/garments/order",
            json.dumps({"ids": [-1]}).encode("utf-8"),
            "application/json",
        )
        check(status == 400, "拒绝无效编号")

        # 6. 外套顺序不受上衣排序影响
        check(names(base, "outer") == ["外套一"], "外套顺序保持")

        call("DELETE", f"{base}/api/garments/{outer}")

    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{PASSED} 项通过，{FAILED} 项失败")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
