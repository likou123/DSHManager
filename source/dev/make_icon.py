
r"""生成 app 图标：完全沿用 DSH 官方图标的几何参数（画布/边距/圆角）。

从 C:\...\Programs\DeepSeek Harness\resources\icon.png 拟合得到：
  canvas 1024×1024，四周留白 32 px（3.1%），内框 960×960，圆角半径 178 px
  （= 内框的 18.5%），圆角为**圆弧**（超椭圆指数 n≈2.00，拟合 RMSE 1.2 px）。

本脚本只替换配色与图形：白底 + 黑色鲸鱼图形，几何参数与 DSH 官方图标一致。
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ASSETS = os.path.join(ROOT, "src", "dshmanager", "assets")

CANVAS = 1024
MARGIN = 32           # 1024 画布的边距（与 DSH 官方图标一致）
RADIUS = 178          # 内框 960 的圆角半径（与 DSH 官方图标一致）
GLYPH_WIDTH_RATIO = 0.73   # 图形占画布宽度比例（DSH 官方图标约为 73%）

GLYPH_CANDIDATES = [
    os.path.join(ROOT, "..", "logo", "鲸鱼文件夹历史图标.png"),
    os.path.join(ASSETS, "logo.png"),
]
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]


def load_glyph() -> Image.Image:
    for path in GLYPH_CANDIDATES:
        if os.path.exists(path):
            image = Image.open(path).convert("RGBA")
            return image.crop(image.getbbox())
    raise FileNotFoundError("找不到 logo 源图")


def build(size: int) -> Image.Image:
    scale = 4
    big = size * scale
    unit = big / CANVAS
    margin = int(round(MARGIN * unit))
    inner = big - margin * 2
    radius = int(round(RADIUS * unit * (inner / (960 * unit))))

    base = Image.new("RGBA", (big, big), (255, 255, 255, 0))
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(
        [margin, margin, big - margin - 1, big - margin - 1],
        radius=radius,
        fill=(255, 255, 255, 255),
    )

    glyph = load_glyph()
    target_w = int(big * GLYPH_WIDTH_RATIO)
    factor = target_w / glyph.width
    glyph = glyph.resize((target_w, max(1, int(glyph.height * factor))), Image.LANCZOS)

    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    layer.paste(glyph, ((big - glyph.width) // 2, (big - glyph.height) // 2), glyph)
    base.alpha_composite(layer)

    return base.resize((size, size), Image.LANCZOS)


def main() -> int:
    build(1024).save(os.path.join(ASSETS, "logo.png"), "PNG", optimize=True)
    icon = build(256)
    icon.save(os.path.join(ASSETS, "dshmanager.png"), "PNG", optimize=True)
    icon.save(os.path.join(ASSETS, "dshmanager.ico"), sizes=SIZES)
    print("icon generated with DSH geometry: canvas=%d margin=%d radius=%d" % (CANVAS, MARGIN, RADIUS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
