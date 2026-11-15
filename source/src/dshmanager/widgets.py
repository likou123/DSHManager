"""自绘控件库：Soft Minimal Desktop Utility 风格（对齐 MagDsh）。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen, QRegion
from PySide6.QtWidgets import QDialog, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from . import theme

ROW_HEIGHT = 56


# ================================================================ 窗口壳
class ChromeBase:
    RADIUS = 16

    def _init_chrome(self, width: int, height: int, title: str) -> None:
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(width, height)
        self._drag_widgets: list[QWidget] = []

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        theme.fill_rounded(painter, theme.WINDOW, rect, self.RADIUS)
        theme.draw_rounded_border(painter, theme.BORDER, rect, self.RADIUS, 1.0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_mask()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_mask()

    def _apply_mask(self) -> None:
        path = theme.rounded_path(QRectF(0, 0, self.width(), self.height()), self.RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def enable_window_drag(self, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.installEventFilter(self)
            self._drag_widgets.append(widget)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched in self._drag_widgets and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                    return True
        return super().eventFilter(watched, event)


class ChromeWindow(ChromeBase, QWidget):
    def __init__(self, width: int, height: int, title: str, parent: QWidget | None = None):
        QWidget.__init__(self, parent)
        self._init_chrome(width, height, title)
        self.setWindowTitle(title)


class ChromeDialog(ChromeBase, QDialog):
    def __init__(self, width: int, height: int, title: str, parent: QWidget | None = None):
        QDialog.__init__(self, parent)
        self._init_chrome(width, height, title)
        self.setModal(True)


# ================================================================ 小图标按钮
class GlyphButton(QWidget):
    clicked = Signal()

    def __init__(self, kind: str = "close", parent: QWidget | None = None, diameter: int = 30):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(diameter, diameter)
        self._hover = False
        self._pressed = False
        self.setCursor(Qt.ArrowCursor)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._pressed:
            return
        self._pressed = False
        self.update()
        if self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._hover or self._pressed:
            fill = theme.GLYPH_PRESSED if self._pressed else theme.GLYPH_HOVER
            theme.fill_rounded(painter, fill, rect, 8)

        color = theme.TEXT if (self._hover or self._pressed) else theme.MUTED
        pen = QPen(color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        cx, cy = self.width() / 2.0, self.height() / 2.0

        if self.kind == "close":
            arm = 4.6
            painter.drawLine(QPointF(cx - arm, cy - arm), QPointF(cx + arm, cy + arm))
            painter.drawLine(QPointF(cx + arm, cy - arm), QPointF(cx - arm, cy + arm))
        else:  # more
            pen.setWidthF(2.0)
            painter.setPen(pen)
            for dx in (-4.5, 0.0, 4.5):
                painter.drawPoint(QPointF(cx + dx, cy))


# ================================================================ 按钮
class FlatButton(QWidget):
    clicked = Signal()

    def __init__(self, text: str, primary: bool = False, parent: QWidget | None = None, height: int = 38, danger: bool = False, auto_width: bool = False):
        super().__init__(parent)
        self._text = text
        self._primary = primary
        self._danger = danger
        self._auto_width = auto_width
        self._hover = False
        self._pressed = False
        self._enabled = True
        self.setFixedHeight(height)
        self.setFont(theme.font(9.3, bold=True))
        self.setCursor(Qt.PointingHandCursor)

    def set_text(self, text: str) -> None:
        self._text = text
        if self._auto_width:
            self.fit_to_text()
        self.update()

    def fit_to_text(self, pad: int = 34, min_width: int = 56) -> None:
        """按文字宽度定宽：字数相同的按钮会得到相同的长度。"""
        metrics = QFontMetricsF(self.font())
        self.setFixedWidth(max(min_width, int(metrics.horizontalAdvance(self._text)) + pad))

    def set_enabled_state(self, enabled: bool) -> None:
        self._enabled = enabled
        self.setEnabled(enabled)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._pressed = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._enabled:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._pressed:
            return
        self._pressed = False
        self.update()
        if self._enabled and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        fill, border, foreground = self._palette()
        theme.fill_rounded(painter, fill, rect, 10)
        if border is not None:
            theme.draw_rounded_border(painter, border, rect, 10, 1.0)
        painter.setFont(self.font())
        painter.setPen(foreground)
        painter.drawText(rect, int(Qt.AlignCenter), self._text)

    def _palette(self):
        if not self._enabled:
            if self._primary:
                return theme.ACCENT_DISABLED, None, QColor(255, 255, 255)
            return theme.BUTTON_DISABLED_FILL, theme.BORDER, theme.SUBTLE
        if self._danger:
            if self._pressed:
                return QColor(185, 32, 22), None, QColor(255, 255, 255)
            if self._hover:
                return QColor(201, 40, 28), None, QColor(255, 255, 255)
            return theme.DANGER, None, QColor(255, 255, 255)
        if self._primary:
            if self._pressed:
                return theme.ACCENT_PRESSED, None, QColor(255, 255, 255)
            if self._hover:
                return theme.ACCENT_HOVER, None, QColor(255, 255, 255)
            return theme.ACCENT, None, QColor(255, 255, 255)
        if self._pressed:
            return theme.BUTTON_PRESSED, theme.BORDER_STRONG, theme.TEXT
        if self._hover:
            return theme.BUTTON_HOVER, theme.BUTTON_BORDER_HOVER, theme.TEXT
        return theme.WINDOW, theme.BORDER, theme.TEXT


# ================================================================ 面板
class RoundedPanel(QWidget):
    def __init__(self, parent: QWidget | None = None, fill: QColor | None = None,
                 border: QColor | None = None, radius: float = 14):
        super().__init__(parent)
        self._fill = fill if fill is not None else theme.SURFACE
        self._border = border if border is not None else theme.BORDER
        self._radius = radius

    def set_colors(self, fill: QColor | None = None, border: QColor | None = None) -> None:
        if fill is not None:
            self._fill = fill
        if border is not None:
            self._border = border
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        theme.fill_rounded(painter, self._fill, rect, self._radius)
        theme.draw_rounded_border(painter, self._border, rect, self._radius, 1.0)


# ================================================================ 复选框
class CheckGlyph(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, size: int = 18):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._checked = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool, emit: bool = False) -> None:
        if self._checked == bool(value):
            return
        self._checked = bool(value)
        self.update()
        if emit:
            self.toggled.emit(self._checked)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.set_checked(not self._checked, emit=True)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        if self._checked:
            theme.fill_rounded(painter, theme.ACCENT, rect, 5)
            pen = QPen(QColor(255, 255, 255))
            pen.setWidthF(1.8)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            w, h = self.width(), self.height()
            painter.drawPolyline([
                QPointF(w * 0.28, h * 0.52),
                QPointF(w * 0.44, h * 0.68),
                QPointF(w * 0.74, h * 0.33),
            ])
        else:
            theme.fill_rounded(painter, theme.WINDOW, rect, 5)
            color = theme.ACCENT if self._hover else theme.BORDER_STRONG
            theme.draw_rounded_border(painter, color, rect, 5, 1.2)


# ================================================================ 搜索框
class SearchField(QWidget):
    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None, placeholder: str = "搜索对话标题"):
        super().__init__(parent)
        self.setFixedHeight(36)
        self._focused = False
        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setStyleSheet(
            "QLineEdit{background:transparent;border:none;padding:0px;color:#101828;}"
        )
        self._edit.setFont(theme.font(9.2))
        self._edit.setPlaceholderText(placeholder)
        self._edit.setGeometry(36, 0, max(10, self.width() - 48), self.height())
        self._edit.textChanged.connect(self.text_changed.emit)
        self._edit.setFocusPolicy(Qt.StrongFocus)

    def text(self) -> str:
        return self._edit.text()

    def clear(self) -> None:
        self._edit.clear()

    def focus(self) -> None:
        self._edit.setFocus()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._edit.setGeometry(36, 0, max(10, self.width() - 48), self.height())
        super().resizeEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        self._focused = True
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._focused = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        theme.fill_rounded(painter, theme.WINDOW, rect, 9)
        if self._focused:
            theme.draw_rounded_border(painter, theme.ACCENT, rect, 9, 1.3)
        else:
            theme.draw_rounded_border(painter, theme.BORDER_STRONG, rect, 9, 1.0)

        pen = QPen(theme.SUBTLE)
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        cx, cy = 18.0, self.height() / 2.0
        painter.drawEllipse(QRectF(cx - 6.0, cy - 7.0, 10.5, 10.5))
        painter.drawLine(QPointF(cx + 4.0, cy + 3.0), QPointF(cx + 8.0, cy + 7.0))


# ================================================================ 开关
class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None, checked: bool = True):
        super().__init__(parent)
        self.setFixedSize(42, 24)
        self._checked = bool(checked)
        self._pos = 1.0 if checked else 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.setCursor(Qt.PointingHandCursor)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool, emit: bool = False) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        if not self._timer.isActive():
            self._timer.start()
        if emit:
            self.toggled.emit(value)

    def _tick(self) -> None:
        target = 1.0 if self._checked else 0.0
        delta = target - self._pos
        if abs(delta) < 0.02:
            self._pos = target
            self._timer.stop()
            self.update()
            return
        self._pos += delta * 0.25
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.set_checked(not self._checked, emit=True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing, True)
        rect = QRectF(0, 1, self.width(), self.height() - 2)
        track = theme.ACCENT if self._checked else QColor(214, 222, 233)
        theme.fill_rounded(painter, track, rect, self.height() / 2.0)
        knob = 18.0
        x = 3.0 + (self.width() - knob - 6.0) * self._pos
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QRectF(x, (self.height() - knob) / 2.0, knob, knob))


# ================================================================ 状态胶囊
class PillTone:
    NEUTRAL = "neutral"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    ACCENT = "accent"


class StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None, height: int = 20):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._text = ""
        self._tone = PillTone.NEUTRAL
        self.setFont(theme.font(7.8, bold=True))

    def set_status(self, text: str, tone: str) -> None:
        self._text = text or ""
        metrics = QFontMetricsF(self.font())
        self.setFixedWidth(int(metrics.horizontalAdvance(self._text)) + 20)
        self._tone = tone
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        fill, foreground = self._palette()
        theme.fill_rounded(painter, fill, rect, self.height() / 2.0)
        painter.setFont(self.font())
        painter.setPen(foreground)
        painter.drawText(rect, int(Qt.AlignCenter), self._text)

    def _palette(self):
        if self._tone == PillTone.SUCCESS:
            return theme.SUCCESS_SOFT, theme.SUCCESS
        if self._tone == PillTone.WARNING:
            return theme.WARNING_SOFT, theme.WARNING
        if self._tone == PillTone.DANGER:
            return theme.DANGER_SOFT, theme.DANGER
        if self._tone == PillTone.ACCENT:
            return theme.ACCENT_SOFT, theme.ACCENT
        return theme.SURFACE_STRONG, theme.MUTED


# ================================================================ 横幅
class BannerTone:
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class InfoBanner(QWidget):
    action_clicked = Signal()

    def __init__(self, parent: QWidget | None = None, height: int = 40):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._message = ""
        self._tone = BannerTone.INFO
        self._action = ""
        self._hover = False
        self.setCursor(Qt.ArrowCursor)

    def set_message(self, message: str, tone: str = BannerTone.INFO, action: str = "") -> None:
        self._message = message or ""
        self._tone = tone
        self._action = action
        self.setCursor(Qt.PointingHandCursor if action else Qt.ArrowCursor)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._action and self.rect().contains(event.position().toPoint()):
            self.action_clicked.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        fill, border, fg = self._palette()
        theme.fill_rounded(painter, fill, rect, 9)
        theme.draw_rounded_border(painter, border, rect, 9, 1.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(fg)
        painter.drawEllipse(QRectF(16, self.height() / 2.0 - 3.0, 6, 6))

        font = theme.font(8.6)
        painter.setFont(font)
        painter.setPen(fg)
        action_width = 0.0
        if self._action:
            action_font = theme.font(8.6, bold=True)
            metrics = QFontMetricsF(action_font)
            action_width = metrics.horizontalAdvance(self._action) + 16.0
            painter.setFont(action_font)
            painter.setPen(theme.ACCENT)
            painter.drawText(
                QRectF(self.width() - action_width - 12.0, 0, action_width, self.height()),
                int(Qt.AlignVCenter | Qt.AlignRight),
                self._action,
            )
            painter.setFont(font)
            painter.setPen(fg)

        text_width = max(10.0, self.width() - 32.0 - action_width - (12.0 if self._action else 0.0))
        painter.drawText(
            QRectF(30, 0, text_width, self.height()),
            int(Qt.AlignVCenter | Qt.AlignLeft),
            theme.ellipsize(self._message, font, int(text_width)),
        )

    def _palette(self):
        if self._tone == BannerTone.SUCCESS:
            return theme.SUCCESS_SOFT, theme.SUCCESS_BORDER, theme.SUCCESS
        if self._tone == BannerTone.WARNING:
            return theme.WARNING_SOFT, QColor(254, 223, 137), theme.WARNING
        if self._tone == BannerTone.ERROR:
            return theme.DANGER_SOFT, theme.DANGER_BORDER, theme.DANGER
        return theme.ACCENT_SOFT, theme.ACCENT_BORDER, theme.ACCENT


# ================================================================ 状态行
class StepState:
    PENDING = "pending"
    WORKING = "working"
    DONE = "done"
    FAILED = "failed"


class StatusRow(QWidget):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self._title = title
        self._subtitle = subtitle
        self._state = StepState.PENDING
        self._state_text = ""
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)

    def set_state(self, state: str, state_text: str = "") -> None:
        self._state = state
        self._state_text = state_text
        if state == StepState.WORKING and not self._timer.isActive():
            self._timer.start()
        elif state != StepState.WORKING:
            self._timer.stop()
        self.update()

    def set_texts(self, title: str, subtitle: str = "") -> None:
        self._title = title
        self._subtitle = subtitle
        self.update()

    def _tick(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        width, height = float(self.width()), float(self.height())
        self._draw_icon(painter, QPointF(24.0, height / 2.0))

        title_font = theme.font(9.6, bold=True)
        painter.setFont(title_font)
        painter.setPen(theme.TEXT)
        painter.drawText(QRectF(46, 4, width - 46 - 110, 22), int(Qt.AlignVCenter | Qt.AlignLeft),
                         theme.ellipsize(self._title, title_font, int(width - 156)))

        if self._subtitle:
            sub_font = theme.font(8.2)
            painter.setFont(sub_font)
            painter.setPen(theme.MUTED)
            painter.drawText(QRectF(46, 25, width - 46 - 24, 18), int(Qt.AlignVCenter | Qt.AlignLeft),
                             theme.ellipsize(self._subtitle, sub_font, int(width - 70)))

        state_font = theme.font(8.2, bold=self._state in (StepState.DONE, StepState.FAILED))
        painter.setFont(state_font)
        painter.setPen(self._state_color())
        painter.drawText(QRectF(width - 18 - 90, 0, 90, height), int(Qt.AlignVCenter | Qt.AlignRight), self._state_text)

        pen = QPen(theme.ROW_DIVIDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(QPointF(46.0, height - 1.0), QPointF(width - 18.0, height - 1.0))

    def _state_color(self) -> QColor:
        if self._state == StepState.DONE:
            return theme.SUCCESS
        if self._state == StepState.FAILED:
            return theme.DANGER
        if self._state == StepState.WORKING:
            return theme.ACCENT
        return theme.SUBTLE

    def _draw_icon(self, painter: QPainter, center: QPointF) -> None:
        diameter = 18.0
        box = QRectF(center.x() - diameter / 2.0, center.y() - diameter / 2.0, diameter, diameter)
        if self._state == StepState.DONE:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.SUCCESS)
            painter.drawEllipse(box)
            pen = QPen(QColor(255, 255, 255))
            pen.setWidthF(1.7)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline([
                QPointF(box.left() + 5.0, box.center().y() + 0.4),
                QPointF(box.left() + 8.0, box.center().y() + 3.4),
                QPointF(box.left() + 13.2, box.center().y() - 3.2),
            ])
            return
        if self._state == StepState.FAILED:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.DANGER)
            painter.drawEllipse(box)
            painter.setFont(theme.font(9.0, bold=True))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(box, int(Qt.AlignCenter), "!")
            return
        if self._state == StepState.WORKING:
            pen = QPen(theme.SPINNER_TRACK)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(box.adjusted(1, 1, -1, -1))
            pen = QPen(theme.ACCENT)
            pen.setWidthF(2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawArc(box.adjusted(1, 1, -1, -1), int(-self._angle * 16), int(100 * 16))
            return
        pen = QPen(theme.RING_PENDING)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(box.adjusted(1, 1, -1, -1))
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.DOT_PENDING)
        painter.drawEllipse(QRectF(center.x() - 2.0, center.y() - 2.0, 4.0, 4.0))


# ================================================================ 进度条
class AccentProgress(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self._value = 0.0
        self._target = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def set_target(self, value: float) -> None:
        self._target = max(0.0, min(1.0, float(value)))
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        delta = self._target - self._value
        if abs(delta) < 0.005:
            self._value = self._target
            self._timer.stop()
            self.update()
            return
        self._value += delta * 0.16
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        theme.fill_rounded(painter, theme.PROGRESS_TRACK, rect, 2)
        if self._value > 0.0005:
            theme.fill_rounded(painter, theme.ACCENT, QRectF(0, 0, max(2.0, rect.width() * self._value), rect.height()), 2)


# ================================================================ 滚动区
def make_scroll_area(parent: QWidget | None = None) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    area = QScrollArea(parent)
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setStyleSheet(
        "QScrollArea{background:transparent;border:none;}"
        "QScrollBar:vertical{background:transparent;width:10px;margin:2px;}"
        "QScrollBar::handle:vertical{background:#D5DEEB;border-radius:5px;min-height:28px;}"
        "QScrollBar::handle:vertical:hover{background:#BECBDB;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}"
        "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}"
    )
    body = QWidget()
    body.setStyleSheet("background:transparent;")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    area.setWidget(body)
    return area, body, layout
