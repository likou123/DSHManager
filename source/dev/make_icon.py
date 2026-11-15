"""从 DeepSeek Harness.exe 提取图标，生成 png + ico。"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QFileInfo, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QFileIconProvider  # noqa: E402

from dshmanager import restart, theme  # noqa: E402

app = QGuiApplication([])
assets = os.path.join(ROOT, "src", "dshmanager", "assets")
os.makedirs(assets, exist_ok=True)
png_path = os.path.join(assets, "dshmanager.png")
ico_path = os.path.join(assets, "dshmanager.ico")

pixmap = None
exe = restart.find_exe()
print("dsh exe:", exe)
if exe:
    icon = QFileIconProvider().icon(QFileInfo(exe))
    print("icon null:", icon.isNull())
    if not icon.isNull():
        pixmap = icon.pixmap(256, 256)

if pixmap is None or pixmap.isNull():
    print("fallback to painted badge")
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    theme.fill_rounded(painter, theme.ACCENT, QRectF(0, 0, 256, 256), 56)
    painter.setFont(theme.font(120, bold=True))
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(QRectF(0, 0, 256, 256), int(Qt.AlignCenter), "D")
    painter.end()

pixmap.save(png_path, "PNG")

from PIL import Image  # noqa: E402

img = Image.open(png_path).convert("RGBA")
img.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon:", ico_path, img.size, "unique colors:", len(img.getcolors(100000) or []))
