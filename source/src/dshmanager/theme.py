"""设计令牌：Soft Minimal Desktop Utility（对齐 MagDsh 的 theme.py）。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

# ---------------------------------------------------------------- 颜色
WINDOW = QColor(255, 255, 255)
SURFACE = QColor(247, 249, 252)
SURFACE_STRONG = QColor(242, 246, 251)
BORDER = QColor(229, 235, 243)
BORDER_STRONG = QColor(213, 222, 235)
TEXT = QColor(16, 24, 40)
MUTED = QColor(102, 112, 133)
SUBTLE = QColor(152, 162, 179)
ACCENT = QColor(0, 116, 253)
ACCENT_HOVER = QColor(0, 103, 224)
ACCENT_PRESSED = QColor(0, 89, 196)
ACCENT_SOFT = QColor(234, 243, 255)
ACCENT_DISABLED = QColor(184, 208, 240)
ACCENT_BORDER = QColor(205, 226, 255)
SUCCESS = QColor(18, 148, 95)
SUCCESS_SOFT = QColor(236, 253, 243)
SUCCESS_BORDER = QColor(205, 241, 224)
WARNING = QColor(181, 71, 8)
WARNING_SOFT = QColor(255, 250, 235)
DANGER = QColor(217, 45, 32)
DANGER_SOFT = QColor(254, 243, 242)
DANGER_BORDER = QColor(254, 205, 202)

GLYPH_HOVER = QColor(243, 245, 248)
GLYPH_PRESSED = QColor(234, 238, 244)
BUTTON_PRESSED = QColor(239, 243, 249)
BUTTON_HOVER = QColor(247, 250, 254)
BUTTON_BORDER_HOVER = QColor(190, 208, 230)
BUTTON_DISABLED_FILL = QColor(248, 249, 251)
ROW_DIVIDER = QColor(237, 242, 248)
ROW_HOVER = QColor(247, 250, 254)
ROW_SELECTED = QColor(240, 247, 255)
PROGRESS_TRACK = QColor(237, 242, 248)
SPINNER_TRACK = QColor(225, 235, 249)
RING_PENDING = QColor(203, 213, 225)
DOT_PENDING = QColor(226, 232, 240)

FAMILY = "Microsoft YaHei UI"
FAMILY_FALLBACKS = ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial")


def font(size: float, bold: bool = False) -> QFont:
    f = QFont(FAMILY, -1)
    f.setPointSizeF(size)
    f.setBold(bold)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


# ---------------------------------------------------------------- 绘制
def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    diameter = max(1.0, min(radius * 2.0, min(rect.width(), rect.height())))
    if diameter <= 1.0:
        path.addRect(rect)
        path.closeSubpath()
        return path
    r = diameter / 2.0
    path.moveTo(rect.left() + r, rect.top())
    path.lineTo(rect.right() - r, rect.top())
    path.arcTo(QRectF(rect.right() - diameter, rect.top(), diameter, diameter), 90, -90)
    path.lineTo(rect.right(), rect.bottom() - r)
    path.arcTo(QRectF(rect.right() - diameter, rect.bottom() - diameter, diameter, diameter), 0, -90)
    path.lineTo(rect.left() + r, rect.bottom())
    path.arcTo(QRectF(rect.left(), rect.bottom() - diameter, diameter, diameter), 270, -90)
    path.lineTo(rect.left(), rect.top() + r)
    path.arcTo(QRectF(rect.left(), rect.top(), diameter, diameter), 180, -90)
    path.closeSubpath()
    return path


def fill_rounded(painter: QPainter, color: QColor, rect: QRectF, radius: float) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawPath(rounded_path(rect, radius))
    painter.restore()


def draw_rounded_border(painter: QPainter, color: QColor, rect: QRectF, radius: float, width: float = 1.0) -> None:
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color)
    pen.setWidthF(width)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    inset = QRectF(
        rect.left() + width / 2.0,
        rect.top() + width / 2.0,
        max(1.0, rect.width() - width),
        max(1.0, rect.height() - width),
    )
    painter.drawPath(rounded_path(inset, max(1.0, radius - width / 2.0)))
    painter.restore()


def ellipsize(text: str, f: QFont, width: float) -> str:
    if not text or width <= 0:
        return ""
    metrics = QFontMetricsF(f)
    if metrics.horizontalAdvance(text) <= width:
        return text
    ell = "\u2026"
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if metrics.horizontalAdvance(text[:mid] + ell) <= width:
            low = mid
        else:
            high = mid - 1
    return ell if low <= 0 else text[:low] + ell


def resource_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "dshmanager" / "assets"
    return Path(__file__).resolve().parent / "assets"


def resource_path(name: str) -> str:
    return str(resource_dir() / name)
