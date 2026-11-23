"""把「五视角转面图」自动拆成五张单品图。

用法：
    .venv/Scripts/python.exe tools/split_turnaround.py 转面图.png
    .venv/Scripts/python.exe tools/split_turnaround.py 转面图.png -o 输出目录

输出顺序固定为：正面、左前45°、左侧面、左后135°、背面。
脚本只做裁切，不抠背景；切完后用平台「智能抠图」批量处理。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

OUTPUT_NAMES = [
    "01_正面.png",
    "02_左前45.png",
    "03_左侧面.png",
    "04_左后135.png",
    "05_背面.png",
]

BACKGROUND_THRESHOLD = 244
PADDING = 8
PANEL_GAP_RATIO = 0.04     # 视角之间的空白至少占总宽度的 4%
MIN_CONTENT_RATIO = 0.02   # 内容少于总宽 2% 的区间不算一个视角


def is_background(pixel: tuple[int, int, int], threshold: int = BACKGROUND_THRESHOLD) -> bool:
    """接近纯白的像素视为背景。"""
    return min(pixel[0], pixel[1], pixel[2]) >= threshold


def content_columns(image: Image.Image, threshold: int = BACKGROUND_THRESHOLD) -> list[bool]:
    """逐列判断是否有非背景内容。"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    step_y = max(1, height // 300)

    columns = []
    for x in range(width):
        has_content = False
        for y in range(0, height, step_y):
            if not is_background(pixels[x, y], threshold):
                has_content = True
                break
        columns.append(has_content)
    return columns


def find_panel_gaps(columns: list[bool], min_gap: int) -> list[tuple[int, int]]:
    """找出宽度足够的空白区间，作为视角之间的分隔。"""
    gaps = []
    start = None

    for x, has_content in enumerate(columns):
        if not has_content:
            if start is None:
                start = x
        elif start is not None:
            if x - start >= min_gap:
                gaps.append((start, x - 1))
            start = None

    if start is not None and len(columns) - start >= min_gap:
        gaps.append((start, len(columns) - 1))
    return gaps


def trim_panel(panel: Image.Image, threshold: int = BACKGROUND_THRESHOLD) -> Image.Image:
    """裁掉单张视角四周的白边，并留出少量边距。"""
    rgb = panel.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    step_x = max(1, width // 200)
    step_y = max(1, height // 200)

    def column_has_content(x: int) -> bool:
        return any(
            not is_background(pixels[x, y], threshold) for y in range(0, height, step_y)
        )

    def row_has_content(y: int) -> bool:
        return any(
            not is_background(pixels[x, y], threshold) for x in range(0, width, step_x)
        )

    left = 0
    while left < width and not column_has_content(left):
        left += 1
    right = width - 1
    while right >= left and not column_has_content(right):
        right -= 1
    top = 0
    while top < height and not row_has_content(top):
        top += 1
    bottom = height - 1
    while bottom >= top and not row_has_content(bottom):
        bottom -= 1

    if left > right or top > bottom:
        return panel

    left = max(0, left - PADDING)
    top = max(0, top - PADDING)
    right = min(width - 1, right + PADDING)
    bottom = min(height - 1, bottom + PADDING)
    return panel.crop((left, top, right + 1, bottom + 1))


def split_sheet(image: Image.Image) -> tuple[list[Image.Image], str]:
    """切出五个视角，返回 (视角图列表, 切分方式说明)。"""
    width, height = image.size
    columns = content_columns(image)
    min_gap = max(8, int(width * PANEL_GAP_RATIO))
    gaps = find_panel_gaps(columns, min_gap)

    # 中间刚好有 4 个足够宽的空白，就以空白中心为切分线
    inner_gaps = [gap for gap in gaps if gap[0] > 0 and gap[1] < width - 1]
    if len(inner_gaps) == len(OUTPUT_NAMES) - 1:
        cuts = [0] + [round((left + right) / 2) for left, right in inner_gaps] + [width]
        mode = "按视角间空白切分"
    else:
        slice_width = width / len(OUTPUT_NAMES)
        cuts = [round(index * slice_width) for index in range(len(OUTPUT_NAMES))] + [width]
        mode = "未找到 4 个分隔空白，按等宽五等分切分"

    panels = []
    for index in range(len(OUTPUT_NAMES)):
        left = min(width - 1, max(0, cuts[index]))
        right = min(width - 1, max(left, cuts[index + 1] - 1))
        panel = image.crop((left, 0, right + 1, height))
        panels.append(trim_panel(panel))

    return panels, mode


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分五视角转面图")
    parser.add_argument("image", help="转面图文件路径")
    parser.add_argument("-o", "--output", help="输出目录")
    args = parser.parse_args()

    source = Path(args.image).expanduser().resolve()
    if not source.is_file():
        print(f"找不到文件：{source}")
        return 1

    output_dir = (
        Path(args.output).expanduser().resolve()
        if args.output
        else source.parent / "五视图拆分"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        image = image.convert("RGBA")
        panels, mode = split_sheet(image)

    for name, panel in zip(OUTPUT_NAMES, panels):
        path = output_dir / name
        panel.save(path, "PNG")
        print(f"已输出 {path}  {panel.size[0]}x{panel.size[1]}")

    print(f"切分方式：{mode}")
    print(f"输出目录：{output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
