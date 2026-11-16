r"""生成 app 图标：完全沿用 DSH 官方图标的几何与配色参数。

参数全部从 C:\...\Programs\DeepSeek Harness\resources\icon.png（1024×1024）实测：
  - 画布 1024，四周留白 32 px（3.1%），内框 960×960
  - 圆角半径 178 px（内框 18.5%），圆弧圆角（超椭圆指数 n≈2.00）
  - 底板为**竖向浅色渐变**：顶部 (249,249,250) → 底部 (235,238,243)
    （不是纯白，否则在白底资源管理器里看不出圆角）
  - 图形宽 = 内框的 78.3%（752/960），深色图形 (26,29,34) 左右
本脚本只替换图形本体（鲸鱼文件夹徽标），其余参数与 DSH 官方图标一致。
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ASSETS = os.path.join(ROOT, "src", "dshmanager", "assets")

CANVAS = 1024
MARGIN = 32                 # 1024 画布下的边距（DSH 官方图标实测）
RADIUS = 178                # 内框 960 的圆角半径（DSH 官方图标实测）
ICON_WIDTH_RATIO = 0.783    # 图形宽 / 内框宽（DSH 官方图标实测 752/960）
BG_TOP = (249, 249, 250)    # DSH 底板顶部色
BG_BOTTOM = (235, 238, 243)  # DSH 底板底部色
GLYPH_COLOR = (26, 29, 34)  # DSH 图形色
HALO_ALPHA = 48             # 源图四周有极淡的半透明光晕，低于此 alpha 视为背景

GLYPH_CANDIDATES = [
    os.path.join(ROOT, "..", "logo", "鲸鱼文件夹历史图标.png"),
    os.path.join(ASSETS, "logo.png"),
]
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]


def load_glyph() -> Image.Image:
    """读取徽标并裁到实体像素（忽略四周淡光晕）。"""
    for path in GLYPH_CANDIDATES:
        if not os.path.exists(path):
            continue
        image = Image.open(path).convert("RGBA")
        alpha = image.getchannel("A").point(lambda v: 0 if v < HALO_ALPHA else v)
        image.putalpha(alpha)
        box = alpha.getbbox()
        if box is None:
            continue
        glyph = image.crop(box)
        solid = Image.new("RGBA", glyph.size, GLYPH_COLOR + (0,))
        solid.putalpha(glyph.getchannel("A"))
        return solid
    raise FileNotFoundError("找不到 logo 源图")


def tile(big: int) -> Image.Image:
    """按 DSH 参数绘制底板：留白 32/1024 + 圆弧圆角 + 竖向渐变。"""
    unit = big / CANVAS
    margin = int(round(MARGIN * unit))
    radius = int(round(RADIUS * unit))
    box = [margin, margin, big - margin - 1, big - margin - 1]

    grad = Image.new("RGBA", (1, big), (0, 0, 0, 0))
    for y in range(big):
        f = y / max(1, big - 1)
        grad.putpixel((0, y), (
            int(round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * f)),
            int(round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * f)),
            int(round(BG_BOTTOM[2] if False else BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * f)),
            255,
        ))
    fill = grad.resize((big, big), Image.BILINEAR)

    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    base = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    base.paste(fill, (0, 0), mask)
    return base


def build(size: int) -> Image.Image:
    scale = 4
    big = size * scale
    unit = big / CANVAS
    inner = big - 2 * int(round(MARGIN * unit))

    base = tile(big)

    glyph = load_glyph()
    target_w = int(round(inner * ICON_WIDTH_RATIO))
    factor = target_w / glyph.width
    glyph = glyph.resize((target_w, max(1, int(round(glyph.height * factor)))), Image.LANCZOS)

    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    layer.paste(glyph, ((big - glyph.width) // 2, (big - glyph.height) // 2), glyph)
    base.alpha_composite(layer)

    return base.resize((size, size), Image.LANCZOS)


def main() -> int:
    build(1024).save(os.path.join(ASSETS, "logo.png"), "PNG", optimize=True)
    icon = build(256)
    icon.save(os.path.join(ASSETS, "dshmanager.png"), "PNG", optimize=True)
    icon.save(os.path.join(ASSETS, "dshmanager.ico"), sizes=SIZES)
    print("icon: canvas=%d margin=%d radius=%d glyph=%.1f%% of tile" % (
        CANVAS, MARGIN, RADIUS, ICON_WIDTH_RATIO * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
