"""确认 / 错误 / 关于 对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QWidget

from . import theme
from .widgets import ChromeDialog, CheckGlyph, FlatButton, GlyphButton, RoundedPanel


class _Label(QLabel):
    def __init__(self, parent: QWidget, text: str, size: float, bold: bool, color: QColor):
        super().__init__(text, parent)
        self.setFont(theme.font(size, bold=bold))
        self.setStyleSheet(f"color:{color.name()};background:transparent;")
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.NoTextInteraction)


class ConfirmDialog(ChromeDialog):
    """危险操作确认：标题 + 说明 + 影响列表 + 可选开关 + 取消/确认。"""

    def __init__(self, parent, title: str, message: str, items: list[str],
                 confirm_label: str = "确认删除", extra_label: str = "", danger: bool = True):
        shown = items[:8]
        more = len(items) - len(shown)
        rows = len(shown) + (1 if more > 0 else 0)
        panel_h = (rows * 22 + 22) if items else 0
        height = 226 + panel_h + (46 if extra_label else 0) + 56

        super().__init__(620, max(height, 300), title, parent)
        width = 620

        self._title = _Label(self, title, 12.5, True, theme.TEXT)
        self._title.setGeometry(28, 44, 520, 28)

        self._message = _Label(self, message, 9.0, False, theme.MUTED)
        self._message.setGeometry(28, 78, 564, 44)

        y = 132
        if items:
            self._panel = RoundedPanel(self, fill=theme.SURFACE, border=theme.BORDER, radius=12)
            self._panel.setGeometry(28, y, 564, panel_h)
            row_y = y + 12
            for text in shown:
                label = _Label(self, "· " + text, 8.8, False, theme.MUTED)
                label.setGeometry(44, row_y, 532, 20)
                row_y += 22
            if more > 0:
                label = _Label(self, f"… 以及另外 {more} 项", 8.8, False, theme.SUBTLE)
                label.setGeometry(44, row_y, 532, 20)
            y += panel_h + 14

        if extra_label:
            self._extra_check = CheckGlyph(self)
            self._extra_check.setGeometry(30, y + 4, 18, 18)
            self._extra_text = _Label(self, extra_label, 8.8, False, theme.MUTED)
            self._extra_text.setGeometry(58, y + 2, 520, 22)
            y += 34
        else:
            self._extra_check = None

        buttons_y = max(y + 18, self.height() - 58)
        self._cancel = FlatButton("取消", primary=False, parent=self)
        self._cancel.setGeometry(width - 232, buttons_y, 96, 38)
        self._cancel.clicked.connect(self.reject)

        self._confirm = FlatButton(confirm_label, primary=not danger, danger=danger, parent=self)
        self._confirm.setGeometry(width - 124, buttons_y, 96, 38)
        self._confirm.clicked.connect(self.accept)

        self._close = GlyphButton("close", self)
        self._close.move(width - 42, 12)
        self._close.clicked.connect(self.reject)
        self.enable_window_drag(self._title, self._message)

    def extra_checked(self) -> bool:
        return bool(self._extra_check.is_checked()) if self._extra_check is not None else False


class DetailsDialog(ChromeDialog):
    def __init__(self, parent, title: str, body: str):
        super().__init__(720, 440, title, parent)
        label = _Label(self, title, 11.5, True, theme.TEXT)
        label.setGeometry(24, 40, 640, 26)

        view = QPlainTextEdit(self)
        view.setReadOnly(True)
        view.setPlainText(body)
        view.setFont(theme.font(8.6))
        view.setStyleSheet(
            "QPlainTextEdit{background:#F7F9FC;border:1px solid #E5EBF3;border-radius:10px;"
            "padding:8px;color:#101828;selection-background-color:#EAF3FF;}"
        )
        view.setGeometry(24, 76, 672, 300)

        ok = FlatButton("知道了", primary=True, parent=self)
        ok.setGeometry(600, 390, 96, 36)
        ok.clicked.connect(self.accept)

        close = GlyphButton("close", self)
        close.move(720 - 42, 12)
        close.clicked.connect(self.accept)


class AboutDialog(ChromeDialog):
    def __init__(self, parent, version: str, dsh_home: str):
        super().__init__(560, 372, "关于", parent)
        title = _Label(self, "DSH 对话管理器", 13.0, True, theme.TEXT)
        title.setGeometry(28, 44, 460, 30)

        sub = _Label(self, f"DSHManager v{version}", 9.0, False, theme.MUTED)
        sub.setGeometry(28, 78, 460, 22)

        body = _Label(
            self,
            "整理 DeepSeek Harness 保存在本机的对话：按工作区浏览，支持搜索与批量删除。\n"
            "删除完成后可以自动重启 DSH。\n\n"
            f"数据目录：{dsh_home}\n"
            "写入前会自动备份 workspace.json；被删除的对话无法恢复。",
            8.8, False, theme.MUTED,
        )
        body.setGeometry(28, 106, 504, 150)

        ok = FlatButton("知道了", primary=True, parent=self)
        ok.setGeometry(436, 312, 96, 36)
        ok.clicked.connect(self.accept)

        close = GlyphButton("close", self)
        close.move(560 - 42, 12)
        close.clicked.connect(self.accept)

