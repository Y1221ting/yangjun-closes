"""用无头浏览器验证前端能否正常渲染。

会启动一个临时数据目录的服务，用 Edge / Chrome 的 --dump-dom 抓取渲染后的 HTML。
用法：.venv/Scripts/python.exe tests/test_ui_render.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

_TEMP_ROOT = Path(tempfile.mkdtemp(prefix="wardrobe-ui-"))
os.environ["WARDROBE_DATA_DIR"] = str(_TEMP_ROOT / "data")
os.environ["WARDROBE_LOG_DIR"] = str(_TEMP_ROOT / "logs")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app.config import ANGLES  # noqa: E402
from app.db import init_db  # noqa: E402
from app.server import start_server  # noqa: E402
from app.services import model_service  # noqa: E402
from app.utils import ensure_dirs, setup_logging  # noqa: E402

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str | None:
    for path in BROWSERS:
        if Path(path).is_file():
            return path
    return None


def dump_dom(browser: str, url: str, profile: Path) -> str:
    result = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=6000",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        timeout=90,
    )
    return result.stdout.decode("utf-8", "replace")


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
    draw.rounded_rectangle([150, 150, width - 150, height - 100], radius=40,
                           fill=(210, 195, 175, 255))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def main() -> int:
    setup_logging()
    ensure_dirs()
    init_db()

    browser = find_browser()
    if not browser:
        print("SKIP：没有找到 Edge 或 Chrome，跳过渲染测试")
        return 0

    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"
    profile = _TEMP_ROOT / "browser-profile"
    failures = 0

    try:
        # 1. 空衣柜
        html = dump_dom(browser, base + "/", profile)
        checks = [
            ("yt的衣柜", "页面标题"),
            ("衣柜还是空的", "空状态文案"),
            ("添加衣服", "添加按钮"),
            ('id="welcome"', "启动欢迎页"),
            ("welcome__art", "欢迎页花体图"),
            ("正在打开你的衣柜", "欢迎页文案"),
            ("点击任意处跳过", "欢迎页跳过提示"),
        ]
        for text, label in checks:
            ok = text in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{text}")

        # 2. 造一件衣服，再渲染
        body = json.dumps(
            {"name": "UI 测试白T", "category": "top", "color": "white"},
            ensure_ascii=False,
        ).encode("utf-8")
        _, payload = call("POST", base + "/api/garments", body, "application/json")
        garment_id = payload["data"]["id"]
        for angle in ("front", "side", "back"):
            call("POST", f"{base}/api/garments/{garment_id}/images?angle={angle}",
                 make_png(), "image/png")

        html = dump_dom(browser, base + "/", profile)
        for text, label in [
            ("UI 测试白T", "衣服名称出现在卡片里"),
            ("thumb.webp", "缩略图被引用"),
            ("1 件衣服", "数量显示正确"),
        ]:
            ok = text in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{text}")

        # 2.1 挂杆视图
        rack_count = html.count('class="rack-item"')
        ok = rack_count == 1
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 挂杆渲染 1 件衣服（实际 {rack_count}）")

        for needle, label in [
            ('class="rack-bar"', "挂杆横杆"),
            ('class="rack-item__hanger"', "衣架"),
            ('class="rack-item__side"', "侧面挂图"),
            ('class="rack-item__front"', "正面展开图"),
        ]:
            ok = needle in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 2.0 侧栏导览与筛选弹层
        for needle, label in [
            ('class="sidebar__logo"', "侧栏花体招牌"),
            ('id="sidebar-catalog"', "侧栏衣橱目录容器"),
            ('id="btn-filter-toggle"', "顶部筛选按钮"),
            ('id="filter-pop"', "筛选弹层"),
            ('class="filter-toggle__count"', "筛选数量角标"),
        ]:
            ok = needle in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{needle}")

        catalog_count = html.count('class="catalog-item__name"')
        ok = catalog_count == 9
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 侧栏目录 9 个类别（实际 {catalog_count}）")

        status, counts_resp = call("GET", base + "/api/garments/counts")
        counts_data = counts_resp.get("data", {})
        ok = (
            status == 200
            and counts_data.get("total") == 1
            and counts_data.get("categories", {}).get("top") == 1
        )
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 分类数量接口：{counts_data}")

        # 2.2 衣帽柜：顶柜、鞋格、帽格、包格
        for shoe_name, shoe_color in [
            ("UI 测试运动鞋", "black"),
            ("UI 测试短靴", "brown"),
        ]:
            shoe_body = json.dumps(
                {"name": shoe_name, "category": "shoes", "color": shoe_color},
                ensure_ascii=False,
            ).encode("utf-8")
            _, shoe_resp = call("POST", base + "/api/garments", shoe_body,
                                "application/json")
            shoe_id = shoe_resp["data"]["id"]
            call("POST", f"{base}/api/garments/{shoe_id}/images?angle=front",
                 make_png(), "image/png")

        bag_body = json.dumps(
            {"name": "UI 测试托特包", "category": "bag", "color": "brown"},
            ensure_ascii=False,
        ).encode("utf-8")
        _, bag_resp = call("POST", base + "/api/garments", bag_body,
                           "application/json")
        bag_id = bag_resp["data"]["id"]
        call("POST", f"{base}/api/garments/{bag_id}/images?angle=front",
             make_png(), "image/png")

        for hat_name, hat_color in [
            ("UI 测试贝雷帽", "beige"),
            ("UI 测试棒球帽", "black"),
        ]:
            hat_body = json.dumps(
                {"name": hat_name, "category": "hat", "color": hat_color},
                ensure_ascii=False,
            ).encode("utf-8")
            _, hat_resp = call("POST", base + "/api/garments", hat_body,
                               "application/json")
            hat_id = hat_resp["data"]["id"]
            call("POST", f"{base}/api/garments/{hat_id}/images?angle=front",
                 make_png(), "image/png")

        html = dump_dom(browser, base + "/", profile)
        for needle, label in [
            ('class="closet-section"', "衣帽柜独立分区"),
            ('class="closet"', "柜体"),
            ('class="closet__top"', "顶柜"),
            ('class="closet-door"', "顶柜门"),
            ('class="closet-box"', "顶柜收纳盒"),
            ('class="closet__middle"', "中间格子"),
            ('class="closet-grid closet-shoes"', "左侧鞋格"),
            ('class="closet-grid closet-hats"', "右上帽格"),
            ('class="closet-grid closet-bags"', "右下包格"),
            ('class="closet__drawers"', "底部抽屉"),
            ('class="closet-drawer__front"', "抽屉面板"),
            ('class="closet-drawer__cells"', "抽屉小格"),
            ('class="closet-item__tag"', "衣帽柜悬停标签"),
            ('class="closet-item closet-item--shoes"', "鞋子渲染"),
            ('class="closet-item closet-item--hat"', "帽子渲染"),
            ('class="closet-item closet-item--bag"', "包渲染"),
            ("UI 测试运动鞋", "鞋子名称显示"),
            ("UI 测试贝雷帽", "帽子名称显示"),
            ("UI 测试托特包", "包名称显示"),
            ("包 · 棕色", "包信息包含类别与颜色"),
            ("帽子 · 米色", "帽子信息包含类别与颜色"),
            ("衣帽柜", "衣帽柜标题"),
            ("5 件", "衣帽柜数量"),
            ("收纳盒 1", "顶柜收纳盒标签"),
            ("鞋 · 8 格", "鞋格标签"),
            ("帽子（上） / 包（下）", "帽包标签"),
            ("小配饰抽屉 · 9 格", "抽屉标签"),
            ("小配饰 1–3", "抽屉区间标签"),
            ('class="closet-drawer__cell-index"', "抽屉小格编号"),
        ]:
            ok = needle in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{needle}")

        cell_count = html.count('closet-cell')
        ok = cell_count >= 26
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 柜子格子数量（实际 {cell_count}）")

        ok = "shoe-section" not in html and "shelf-item" not in html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 旧鞋柜和隔板结构已移除")

        # 2.3 配饰区与抽屉
        for name, style, color in [
            ("UI 测试围巾", "hang", "beige"),
            ("UI 测试手套", "bag", "red"),
            ("UI 测试项链", "flat", "yellow"),
            ("UI 测试戒指", "drawer", "white"),
        ]:
            body = json.dumps(
                {
                    "name": name,
                    "category": "accessory",
                    "color": color,
                    "display_style": style,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            call("POST", base + "/api/garments", body, "application/json")

        html = dump_dom(browser, base + "/", profile)
        for needle, label in [
            ('class="accessory-section"', "配饰独立收纳区"),
            ('class="accessory-item accessory-item--hang"', "挂杆单品"),
            ('class="accessory-item accessory-item--bag"', "纸袋单品"),
            ('class="accessory-item accessory-item--flat"', "平放单品"),
            ('class="accessory-rod"', "细挂杆"),
            ('class="accessory-clip"', "小夹子"),
            ('class="accessory-bag__front"', "牛皮纸袋"),
            ('class="accessory-flat"', "平放台面"),
            ('class="accessory-tag"', "常驻小标签"),
            ("UI 测试围巾", "配饰名称显示"),
            ('class="closet-item closet-item--drawer"', "抽屉配饰渲染"),
            ("UI 测试戒指", "抽屉配饰名称"),
            ("1 件", "抽屉数量角标"),
            ('data-chips="display_style"', "表单摆放方式选项"),
            ("摆放方式", "表单摆放方式标签"),
            ("抽屉", "表单包含抽屉选项"),
            ("帽子", "表单包含帽子类别"),
        ]:
            ok = needle in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{needle}")

        accessory_count = html.count('accessory-item accessory-item--')
        ok = accessory_count == 3
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 配饰区只显示 3 件非抽屉配饰"
              f"（实际 {accessory_count}）")

        ok = cell_count == html.count('closet-cell')
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 抽屉配饰替换空格，格位总数不变")

        # 3. 筛选控件
        for needle, label in [
            ('id="filter-color"', "颜色筛选下拉框"),
            ('id="filter-season"', "季节筛选下拉框"),
            ('id="filter-scene"', "场合筛选下拉框"),
            ('id="category-filters"', "类别筛选行"),
            ('id="btn-clear-filters"', "清除筛选按钮"),
        ]:
            ok = needle in html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 4. 详情页（通过 hash 直接打开）
        detail_html = dump_dom(browser, f"{base}/#garment/{garment_id}", profile)
        for text, label in [
            ("UI 测试白T", "详情页显示衣服名称"),
            ("返回衣柜", "返回按钮"),
            ("角度图", "角度图区域"),
            ("替换", "替换按钮"),
            ("编辑信息", "编辑信息按钮"),
            ("添加时间", "信息表显示添加时间"),
        ]:
            ok = text in detail_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        # 5. 旋转视图
        image_count = detail_html.count('class="rotate-view__img"')
        dot_count = detail_html.count('class="rotate-view__dot"') + detail_html.count(
            'class="rotate-view__dot is-active"'
        )
        check_rot = image_count == 3
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 旋转视图挂载了 3 张图（实际 {image_count}）")

        check_rot = dot_count == 3
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 角度指示点有 3 个（实际 {dot_count}）")

        check_rot = "rotateY(" in detail_html
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 旋转角度已写入样式")

        row_count = detail_html.count('class="angle-row"')
        check_rot = row_count == 5
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 角度图列表有 5 行（实际 {row_count}）")

        check_rot = "?v=" in detail_html
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 图片地址带缓存版本号")

        adjust_count = detail_html.count('class="angle-adjust"')
        check_rot = adjust_count == 3
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 微调面板有 3 个（实际 {adjust_count}）")

        check_rot = "微调" in detail_html
        failures += 0 if check_rot else 1
        print(f"[{'PASS' if check_rot else 'FAIL'}] 微调按钮存在")

        # 6. 搭配库与搭配编辑
        outfit_payload = json.dumps(
            {"name": "UI 搭配", "scenes": ["日常"]}, ensure_ascii=False
        ).encode("utf-8")
        _, outfit_resp = call("POST", base + "/api/outfits", outfit_payload, "application/json")
        outfit_id = outfit_resp["data"]["id"]
        call(
            "PUT",
            f"{base}/api/outfits/{outfit_id}/items?view=flat",
            json.dumps({
                "items": [{
                    "garment_id": garment_id, "x": 0.5, "y": 0.4,
                    "scale": 1, "rotation": 0, "z_index": 0,
                }]
            }).encode("utf-8"),
            "application/json",
        )

        for angle in ANGLES:
            model_service.save_image(angle, make_png())

        outfits_html = dump_dom(browser, base + "/#outfits", profile)
        for text, label in [("UI 搭配", "搭配名称"), ("1 套搭配", "搭配数量")]:
            ok = text in outfits_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{text}")

        for needle, label in [
            ('class="model-hero"', "搭配页模特卡片"),
            ('id="model-view"', "模特旋转视图"),
            ('id="model-dots"', "模特角度圆点"),
            ("我的试衣模特", "模特标题"),
            ("基准模特", "基准模特标签"),
        ]:
            ok = needle in outfits_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{needle}")

        model_images = outfits_html.count('class="rotate-view__img"')
        ok = model_images == 5
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 模特五角度渲染（实际 {model_images}）")

        ok = 'id="sidebar-catalog" hidden' in outfits_html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 离开衣柜页时侧栏目录隐藏")

        editor_html = dump_dom(browser, f"{base}/#outfit/{outfit_id}", profile)
        for text, label in [
            ("场景标签", "场景面板"),
            ("选中的单品", "单品面板"),
            ("UI 搭配", "名称输入框"),
        ]:
            ok = text in editor_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{text}")

        canvas_items = editor_html.count('class="canvas-item"')
        ok = canvas_items == 1
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 画布渲染 1 件单品（实际 {canvas_items}）")

        editor_items = editor_html.count('class="editor-item"')
        ok = editor_items >= 1
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 左侧衣柜列出衣服（实际 {editor_items}）")

        # 7. 搭配库筛选与真实封面
        for needle, label in [
            ('id="outfit-scene-filters"', "场景筛选栏"),
            ('id="outfit-search"', "搭配搜索框"),
        ]:
            ok = needle in outfits_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        mini_count = outfits_html.count('class="outfit-mini__item"')
        ok = mini_count == 1
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 搭配封面渲染 1 件单品（实际 {mini_count}）")

        ok = "导出图片" in editor_html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 编辑器有导出按钮")

        for needle, label in [
            ('id="item-clip-top"', "上边缘裁切滑块"),
            ('id="item-clip-bottom"', "下边缘裁切滑块"),
        ]:
            ok = needle in editor_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        ok = "clip-path:" in outfits_html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 搭配封面应用了裁切")

        # 9. 搭配上身图
        status, _ = call(
            "POST", f"{base}/api/outfits/{outfit_id}/images?angle=front",
            make_png(600, 900), "image/png",
        )
        ok = status == 200
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 上传搭配上身图")

        outfits_html2 = dump_dom(browser, base + "/#outfits", profile)
        ok = 'class="outfit-worn-cover"' in outfits_html2 and "outfit-badge" in outfits_html2
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 搭配库封面使用上身图")

        worn_html = dump_dom(browser, f"{base}/#outfit/{outfit_id}/worn", profile)
        for needle, label in [
            ('id="worn-view"', "上身旋转视图"),
            ('id="worn-angle-list"', "上身角度列表"),
            ("上身图", "上身图标题"),
        ]:
            ok = needle in worn_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")

        worn_images = worn_html.count('class="rotate-view__img"')
        ok = worn_images == 1
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 上身旋转视图挂载 1 张图（实际 {worn_images}）")

        ok = "上身展示" in editor_html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 编辑器有上身展示按钮")

        # 10. 设置与回收站
        settings_html = dump_dom(browser, base + "/#settings", profile)
        for text, label in [
            ("数据安全", "数据安全区块"),
            ("启动体验", "启动体验区块"),
            ('id="welcome-toggle"', "欢迎页开关"),
            ("回收站", "回收站区块"),
            ("立即备份", "备份按钮"),
            ("回收站里没有衣服", "空回收站提示"),
        ]:
            ok = text in settings_html
            failures += 0 if ok else 1
            print(f"[{'PASS' if ok else 'FAIL'}] {label}：{text}")

        # 8. 导出接口
        status, export_resp = call(
            "POST", base + "/api/export?name=UI%E6%90%AD%E9%85%8D",
            make_png(1200, 1600), "image/png",
        )
        ok = status == 200 and export_resp.get("data", {}).get("size", 0) > 0
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 导出 PNG 成功")

        html = detail_html
        ok = "本地服务连接失败" not in html and "启动失败" not in html
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 页面没有启动错误提示")
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(_TEMP_ROOT, ignore_errors=True)

    print(f"\n结果：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
