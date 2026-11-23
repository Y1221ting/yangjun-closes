"""生成三张示例角度图，用于第一次导入流程测试。

生成的图片不是真实衣服，只是带透明背景的示意图形。
用法：.venv/Scripts/python.exe tools/make_samples.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "samples"
SIZE = (800, 1000)
FABRIC = (232, 224, 210, 255)
SHADOW = (205, 196, 182, 255)
LINE = (168, 158, 144, 255)


def blank() -> Image.Image:
    return Image.new("RGBA", SIZE, (0, 0, 0, 0))


def draw_front() -> Image.Image:
    img = blank()
    draw = ImageDraw.Draw(img)
    draw.polygon([(250, 300), (150, 400), (205, 500), (260, 460)], fill=FABRIC, outline=LINE)
    draw.polygon([(550, 300), (650, 400), (595, 500), (540, 460)], fill=FABRIC, outline=LINE)
    draw.rounded_rectangle([230, 280, 570, 830], radius=46, fill=FABRIC, outline=LINE, width=4)
    draw.ellipse([335, 262, 465, 336], fill=SHADOW, outline=LINE, width=3)
    draw.line([(400, 350), (400, 810)], fill=LINE, width=2)
    draw.line([(300, 780), (500, 780)], fill=LINE, width=2)
    return img


def draw_side() -> Image.Image:
    img = blank()
    draw = ImageDraw.Draw(img)
    draw.ellipse([345, 300, 455, 430], fill=FABRIC, outline=LINE, width=3)
    draw.rounded_rectangle([340, 330, 460, 830], radius=34, fill=FABRIC, outline=LINE, width=4)
    draw.line([(455, 360), (455, 820)], fill=LINE, width=2)
    return img


def draw_back() -> Image.Image:
    img = blank()
    draw = ImageDraw.Draw(img)
    draw.polygon([(250, 300), (150, 400), (205, 500), (260, 460)], fill=FABRIC, outline=LINE)
    draw.polygon([(550, 300), (650, 400), (595, 500), (540, 460)], fill=FABRIC, outline=LINE)
    draw.rounded_rectangle([230, 280, 570, 830], radius=46, fill=FABRIC, outline=LINE, width=4)
    draw.line([(400, 300), (400, 820)], fill=LINE, width=2)
    return img


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, image in (("front", draw_front()), ("side", draw_side()), ("back", draw_back())):
        path = OUTPUT_DIR / f"示例-白T-{name}.png"
        image.save(path, "PNG")
        print(f"已生成 {path}")


if __name__ == "__main__":
    main()
