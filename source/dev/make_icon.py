"""由 assets/logo.png 生成 dshmanager.png 与 dshmanager.ico。"""

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "src", "dshmanager", "assets"))
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    logo = os.path.join(ASSETS, "logo.png")
    if not os.path.exists(logo):
        print("缺少 logo.png:", logo)
        return 1
    image = Image.open(logo).convert("RGBA")
    icon = image.resize((256, 256), Image.LANCZOS)
    icon.save(os.path.join(ASSETS, "dshmanager.png"), "PNG", optimize=True)
    icon.save(os.path.join(ASSETS, "dshmanager.ico"), sizes=SIZES)
    print("icon generated from logo.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
