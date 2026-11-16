"""主窗口：工作区侧栏 + 对话列表 + 操作栏。"""

from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QFileInfo, QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontMetricsF, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QFileIconProvider, QLabel, QLineEdit, QMenu, QWidget

from . import model, restart, store, theme
from .dialogs import AboutDialog, ConfirmDialog, DetailsDialog
from .widgets import (
    AccentProgress, BannerTone, CheckGlyph, ChromeWindow, FlatButton, GlyphButton,
    InfoBanner, RoundedPanel, SearchField, StatusRow, StepState, ToggleSwitch,
    make_scroll_area,
)

WIN_W, WIN_H = 1000, 660
SIDEBAR_W = 252

ICON_BADGE = 30


# ================================================================ 设置
class SettingsStore:
    def __init__(self) -> None:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.path = os.path.join(base, "DSHManager", "settings.ini")
        self._data: dict[str, str] = {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if "=" in line:
                        key, value = line.split("=", 1)
                        self._data[key.strip()] = value.strip()
        except OSError:
            pass

    def get_bool(self, key: str, default: bool) -> bool:
        value = self._data.get(key)
        if value is None:
            return default
        return value == "1"

    def set_bool(self, key: str, value: bool) -> None:
        self._data[key] = "1" if value else "0"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
                for k, v in self._data.items():
                    handle.write(f"{k}={v}\n")
        except OSError:
            pass


# ================================================================ 图标
def load_dsh_icon(size: int = 30) -> QPixmap | None:
    """优先用自带的 logo，缺省时退回 DSH 自己的可执行文件图标。"""
    bundled = theme.resource_path("dshmanager.png")
    if os.path.exists(bundled):
        pixmap = QPixmap(bundled)
        if not pixmap.isNull():
            return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    exe = restart.find_exe()
    if not exe:
        return None
    try:
        icon = QFileIconProvider().icon(QFileInfo(exe))
        if icon.isNull():
            return None
        return icon.pixmap(size, size)
    except Exception:
        return None


class LogoBadge(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 30):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._pixmap = load_dsh_icon(size * 2)  # 超采样：高分屏下保持清晰

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._pixmap is not None and not self._pixmap.isNull():
            painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))
            return
        theme.fill_rounded(painter, theme.ACCENT, rect, 8)
        painter.setFont(theme.font(11.0, bold=True))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, int(Qt.AlignCenter), "D")


# ================================================================ 侧栏卡片
class WorkspaceCard(QWidget):
    clicked = Signal(str)
    toggled = Signal(str, bool)     # wid, 是否整块选中
    action = Signal(str, str)      # wid, "unregister" | "delete-all"

    def __init__(self, workspace, parent: QWidget | None = None):
        super().__init__(parent)
        self.workspace = workspace
        self._selected = False
        self._hover = False
        self.setFixedHeight(62)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self._more = GlyphButton("more", self, diameter=24)
        self._more.move(self.width() - 58, 8)
        self._more.clicked.connect(self._open_menu)
        self._more.setVisible(False)

        self._check = CheckGlyph(self)
        self._check.move(self.width() - 32, 22)
        self._check.toggled.connect(lambda value: self.toggled.emit(self.workspace.wid, value))

    def set_selected(self, value: bool) -> None:
        self._selected = value
        self.update()

    def set_check_state(self, checked: bool, partial: bool) -> None:
        self._check.set_checked(checked)
        self._check.set_partial(partial)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._more.move(self.width() - 58, 8)
        self._check.move(self.width() - 32, 22)
        super().resizeEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self._more.setVisible(True)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._more.setVisible(False)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.workspace.wid)

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#FFFFFF;border:1px solid #E5EBF3;border-radius:10px;padding:6px;}"
            "QMenu::item{padding:8px 20px;border-radius:6px;color:#101828;font-size:12px;}"
            "QMenu::item:selected{background:#EAF3FF;}"
            "QMenu::separator{height:1px;background:#EDF2F8;margin:4px 10px;}"
        )
        if self.workspace.unregistered:
            act_register = QAction("添加到DSH配置", menu)
            act_register.triggered.connect(lambda: self.action.emit(self.workspace.wid, "register"))
            menu.addAction(act_register)
            menu.addSeparator()
        if not self.workspace.is_ungrouped and not self.workspace.unregistered:
            act_unregister = QAction("仅删除工作区登记", menu)
            act_unregister.triggered.connect(lambda: self.action.emit(self.workspace.wid, "unregister"))
            menu.addAction(act_unregister)
        act_all = QAction("删除全部对话" + ("并移除登记" if not self.workspace.is_ungrouped else ""), menu)
        act_all.triggered.connect(lambda: self.action.emit(self.workspace.wid, "delete-all"))
        menu.addAction(act_all)
        menu.exec(self._more.mapToGlobal(QPointF(0, self._more.height()).toPoint()))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        if self._selected:
            theme.fill_rounded(painter, theme.ACCENT_SOFT, rect, 11)
            theme.draw_rounded_border(painter, theme.ACCENT_BORDER, rect, 11, 1.0)
        elif self._hover:
            theme.fill_rounded(painter, theme.SURFACE, rect, 11)

        # 图标
        if self.workspace.unregistered:
            theme.fill_rounded(painter, theme.WARNING, QRectF(2.0, 16.0, 3.0, self.height() - 32.0), 1.5)

        badge = QRectF(12, 15, 32, 32)
        fill = theme.ACCENT if self._selected else theme.SURFACE_STRONG
        theme.fill_rounded(painter, fill, badge, 9)
        painter.setFont(theme.font(10.0, bold=True))
        painter.setPen(QColor(255, 255, 255) if self._selected else theme.MUTED)
        initial = (self.workspace.title or "?")[:1].upper()
        painter.drawText(badge, int(Qt.AlignCenter), initial)

        title_font = theme.font(9.6, bold=True)
        painter.setFont(title_font)
        painter.setPen(theme.TEXT)
        right_pad = 40 if self._hover else 14
        title_width = self.width() - 56 - right_pad
        painter.drawText(QRectF(52, 10, title_width, 22), int(Qt.AlignVCenter | Qt.AlignLeft),
                         theme.ellipsize(self.workspace.title, title_font, int(title_width)))

        meta_font = theme.font(8.0)
        metrics = QFontMetricsF(meta_font)
        count = len(self.workspace.sessions)
        count_text = f"{count}个对话" if count else "没有对话"
        pill_w = metrics.horizontalAdvance(count_text) + 14
        pill_rect = QRectF(self.width() - 40 - pill_w, 33, pill_w, 17)
        pill_fill = theme.ACCENT_SOFT if self._selected else theme.SURFACE_STRONG
        theme.fill_rounded(painter, pill_fill, pill_rect, 8.5)
        painter.setFont(meta_font)
        painter.setPen(theme.ACCENT if self._selected else theme.MUTED)
        painter.drawText(pill_rect, int(Qt.AlignCenter), count_text)

        path_width = max(20.0, self.width() - 52 - 40 - pill_w - 8)
        painter.setPen(theme.SUBTLE)
        painter.drawText(QRectF(52, 32, path_width, 18), int(Qt.AlignVCenter | Qt.AlignLeft),
                         theme.ellipsize(self.workspace.path, meta_font, int(path_width)))


# ================================================================ 对话行
class ConversationRow(QWidget):
    toggled = Signal(str, bool)

    def __init__(self, session, parent: QWidget | None = None):
        super().__init__(parent)
        self.session = session
        self._hover = False
        self._checked = False
        self.setFixedHeight(56)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self._check = CheckGlyph(self)
        self._check.setGeometry(12, (56 - 18) // 2, 18, 18)
        self._check.toggled.connect(self._on_check)

    def set_checked(self, value: bool) -> None:
        self._checked = bool(value)
        self._check.set_checked(self._checked)
        self.update()

    def _on_check(self, value: bool) -> None:
        self._checked = value
        self.update()
        self.toggled.emit(self.session.sid, value)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._check.set_checked(not self._check.is_checked(), emit=True)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        width, height = float(self.width()), float(self.height())
        if self._checked:
            theme.fill_rounded(painter, theme.ROW_SELECTED, QRectF(0, 0, width, height), 8)
        elif self._hover:
            theme.fill_rounded(painter, theme.ROW_HOVER, QRectF(0, 0, width, height), 8)

        title_font = theme.font(9.6)
        meta_font = theme.font(8.2)
        meta_text = " · ".join(x for x in (self.session.rel_time, self.session.size_text) if x)
        meta_width = QFontMetricsF(meta_font).horizontalAdvance(meta_text) + 8

        title_rect = QRectF(42, 8, max(40.0, width - 42 - meta_width - 24), 22)
        painter.setFont(title_font)
        painter.setPen(theme.TEXT)
        painter.drawText(title_rect, int(Qt.AlignVCenter | Qt.AlignLeft),
                         theme.ellipsize(self.session.title, title_font, int(title_rect.width())))

        sub_rect = QRectF(42, 28, max(40.0, width - 42 - meta_width - 24), 18)
        sub_font = theme.font(8.2)
        painter.setFont(sub_font)
        painter.setPen(theme.SUBTLE)
        tags = []
        if self.session.pinned:
            tags.append("已置顶")
        if self.session.archived:
            tags.append("已归档")
        sub_text = " · ".join(tags) if tags else "双击工作区卡片可查看路径"
        painter.drawText(sub_rect, int(Qt.AlignVCenter | Qt.AlignLeft),
                         theme.ellipsize(sub_text, sub_font, int(sub_rect.width())))

        painter.setFont(meta_font)
        painter.setPen(theme.MUTED)
        painter.drawText(QRectF(width - meta_width - 16, 0, meta_width, height),
                         int(Qt.AlignVCenter | Qt.AlignRight), meta_text)

        pen = QPen(theme.ROW_DIVIDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(QPointF(42, height - 1), QPointF(width - 16, height - 1))


# ================================================================ 后台任务
class ScanWorker(QThread):
    done = Signal(object, str)
    failed = Signal(str)

    def __init__(self, dsh_home: str):
        super().__init__()
        self.dsh_home = dsh_home

    def run(self) -> None:
        try:
            wpath = store.workspace_path(self.dsh_home)
            data = store.load_json(wpath)
            workspaces = model.scan(self.dsh_home, data)
            self.done.emit(workspaces, wpath)
        except Exception:
            self.failed.emit(traceback.format_exc())


class DeleteWorker(QThread):
    step = Signal(int, str, str)     # index, state, text
    done = Signal(object)            # store.DeleteResult
    failed = Signal(str)

    def __init__(self, dsh_home: str, sessions, workspace_ids, restart_after: bool):
        super().__init__()
        self.dsh_home = dsh_home
        self.sessions = sessions
        self.workspace_ids = set(workspace_ids)
        self.restart_after = restart_after

    def run(self) -> None:
        try:
            result = store.DeleteResult()
            wpath = store.workspace_path(self.dsh_home)

            self.step.emit(0, StepState.WORKING, "删除中")
            for session in self.sessions:
                errors = store.delete_session_files(session)
                result.errors.extend(errors)
                result.deleted_sessions += 1
            self.step.emit(0, StepState.DONE, f"{len(self.sessions)}个")

            self.step.emit(1, StepState.WORKING, "清理中")
            data = store.load_json(wpath)
            sids = {s.sid for s in self.sessions}
            changed = store.clean_references(data, sids, self.workspace_ids)
            self.step.emit(1, StepState.DONE, "已清理" if changed else "无需清理")

            self.step.emit(2, StepState.WORKING, "写入中")
            if changed:
                result.backup = store.backup(wpath)
                store.atomic_write(wpath, store.dump_json(data))
            self.step.emit(2, StepState.DONE, os.path.basename(result.backup) if result.backup else "未改动")
            result.deleted_workspaces = len(self.workspace_ids)

            if self.restart_after:
                self.step.emit(3, StepState.WORKING, "重启中")
                exe = restart.find_exe()
                pids = restart.list_pids() if exe else []
                if not exe:
                    self.step.emit(3, StepState.FAILED, "未找到DSH")
                    result.errors.append("没有找到DeepSeek Harness.exe")
                elif not pids:
                    self.step.emit(3, StepState.DONE, "DSH未运行")
                else:
                    restart.spawn_waiter(exe, pids)
                    ok, code, detail = restart.kill_dsh()
                    if ok:
                        self.step.emit(3, StepState.DONE, "已重启")
                    elif code in (1, 5) or "拒绝访问" in detail or "Access is denied" in detail:
                        self.step.emit(3, StepState.FAILED, "需要管理员权限")
                        result.errors.append(f"结束DSH被拒绝（exit {code}）：{detail}")
                    else:
                        self.step.emit(3, StepState.FAILED, f"exit {code}")
                        result.errors.append(f"taskkill失败（exit {code}）：{detail}")
            else:
                self.step.emit(3, StepState.DONE, "已跳过")

            self.done.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


# ================================================================ 主窗口
class MainWindow(ChromeWindow):
    def __init__(self) -> None:
        super().__init__(WIN_W, WIN_H, "DSH对话管理器")
        icon_path = theme.resource_path("dshmanager.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.settings = SettingsStore()
        self.dsh_home = os.environ.get("DSH_HOME") or os.path.join(os.path.expanduser("~"), ".dsh")
        self.store_path = store.workspace_path(self.dsh_home)
        self.workspaces: list = []
        self.current_wid = ""
        self.selected: set[str] = set()
        self.selected_ws: set[str] = set()
        self._rows: dict[str, ConversationRow] = {}
        self._cards: list[WorkspaceCard] = []
        self._scan_worker: ScanWorker | None = None
        self._delete_worker: DeleteWorker | None = None
        self._last_details = ""
        self._busy = False
        self._pinned = False
        self._build_ui()
        QTimer.singleShot(60, self.refresh)

    # ------------------------------------------------------------ 构建
    def _build_ui(self) -> None:
        self._logo = LogoBadge(self, 30)
        self._logo.move(20, 11)
        self._title = QLabel("DSH对话管理器", self)
        self._title.setFont(theme.font(10.6, bold=True))
        self._title.setStyleSheet("color:#101828;background:transparent;")
        self._title.setGeometry(58, 11, 300, 30)

        self._close = GlyphButton("close", self)
        self._close.move(WIN_W - 46, 11)
        self._close.clicked.connect(self.close)
        self.enable_window_drag(self._title)

        self._sidebar_label = QLabel("工作区", self)
        self._sidebar_label.setFont(theme.font(8.4, bold=True))
        self._sidebar_label.setStyleSheet("color:#98A2B3;background:transparent;")
        self._sidebar_label.setGeometry(20, 66, 160, 22)

        self._cards_area, self._cards_body, self._cards_layout = make_scroll_area(self)
        self._cards_area.setGeometry(10, 94, 232, 462)
        self._cards_layout.setContentsMargins(0, 0, 6, 8)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch(1)

        self._open_dir = FlatButton("打开数据目录", primary=False, parent=self, height=34)
        self._open_dir.setGeometry(12, 608, 104, 34)
        self._open_dir.clicked.connect(self._open_data_dir)

        self._about = FlatButton("关于", primary=False, parent=self, height=34)
        self._about.setGeometry(124, 608, 104, 34)
        self._about.clicked.connect(self._show_about)

        self._add_ws = FlatButton("添加工作区", primary=True, parent=self, height=34)
        self._add_ws.setGeometry(12, 566, 212, 34)
        self._add_ws.clicked.connect(self._add_workspace_dialog)



        # 右侧顶部
        self._search = SearchField(self)
        self._search.setGeometry(272, 64, 300, 36)
        self._search.text_changed.connect(self._on_search)

        self._refresh = FlatButton("刷新", primary=False, parent=self)
        self._refresh.setGeometry(588, 64, 80, 36)
        self._refresh.clicked.connect(self._manual_refresh)

        self._restart_toggle = ToggleSwitch(self, self.settings.get_bool("restart_after_delete", True))
        self._restart_toggle.move(690, 70)
        self._restart_toggle.toggled.connect(self._on_restart_toggled)

        self._restart_label = QLabel("删除后自动重启DSH", self)
        self._restart_label.setFont(theme.font(8.6))
        self._restart_label.setStyleSheet("color:#667085;background:transparent;")
        self._restart_label.setGeometry(740, 70, 210, 24)

        # 全选行
        self._select_all = CheckGlyph(self)
        self._select_all.setGeometry(272, 118, 18, 18)
        self._select_all.toggled.connect(self._on_select_all)

        self._select_all_label = QLabel("全选", self)
        self._select_all_label.setFont(theme.font(8.8))
        self._select_all_label.setStyleSheet("color:#667085;background:transparent;")
        self._select_all_label.setGeometry(298, 114, 80, 24)

        self._sel_label = QLabel("", self)
        self._sel_label.setFont(theme.font(8.6))
        self._sel_label.setStyleSheet("color:#98A2B3;background:transparent;")
        self._sel_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._sel_label.setGeometry(700, 114, 280, 24)

        # 列表
        self._list_area, self._list_body, self._list_layout = make_scroll_area(self)
        self._list_area.setGeometry(264, 148, 724, 388)
        self._list_layout.setContentsMargins(8, 0, 8, 8)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)

        self._empty = QLabel("", self)
        self._empty.setFont(theme.font(9.0))
        self._empty.setStyleSheet("color:#98A2B3;background:transparent;")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setGeometry(264, 300, 724, 40)
        self._empty.setVisible(False)

        # 进度面板
        self._progress = QWidget(self)
        self._progress.setGeometry(264, 148, 724, 388)
        self._progress.setVisible(False)
        self._progress_bg = RoundedPanel(self._progress, fill=theme.SURFACE, border=theme.BORDER, radius=14)
        self._progress_bg.setGeometry(0, 0, 724, 300)
        self._bar = AccentProgress(self._progress)
        self._bar.setGeometry(20, 18, 684, 4)
        self._steps = []
        titles = ["删除对话文件", "清理workspace.json引用", "备份并写盘", "重启DeepSeek Harness"]
        for index, text in enumerate(titles):
            row = StatusRow(text, "", self._progress)
            row.setGeometry(12, 36 + index * 52, 700, 52)
            self._steps.append(row)

        # 横幅
        self._banner = InfoBanner(self)
        self._banner.setGeometry(272, 548, 704, 40)
        self._banner.action_clicked.connect(self._show_details)
        self._banner.setVisible(False)

        # 底部动作栏
        self._hint = QLabel("", self)
        self._hint.setFont(theme.font(8.8))
        self._hint.setStyleSheet("color:#667085;background:transparent;")
        self._hint.setGeometry(272, 609, 372, 28)

        self._cancel_sel = FlatButton("取消选择", primary=False, parent=self, auto_width=True)
        self._cancel_sel.setGeometry(660, 604, 100, 38)
        self._cancel_sel.clicked.connect(self._clear_selection)
        self._cancel_sel.set_enabled_state(False)

        self._delete_btn = FlatButton("删除并重启", primary=True, parent=self)
        self._delete_btn.setGeometry(772, 604, 204, 38)
        self._delete_btn.clicked.connect(self._delete_selected)
        self._delete_btn.set_enabled_state(False)
        metrics = QFontMetricsF(self._delete_btn.font())
        self._delete_btn.setFixedWidth(max(112, int(metrics.horizontalAdvance("删除并重启")) + 40))

        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("F5"), self, self.refresh)
        QShortcut(QKeySequence("Ctrl+A"), self, self._select_all_now)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("/"), self, self._search.focus)

    # ------------------------------------------------------------ 数据
    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._refresh.set_enabled_state(False)
        if not self._pinned:
            self._set_banner("正在扫描会话目录 …", BannerTone.INFO)
        self._scan_worker = ScanWorker(self.dsh_home)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_done(self, workspaces, wpath) -> None:
        self._busy = False
        self.store_path = wpath
        self._refresh.set_enabled_state(True)
        self.workspaces = workspaces
        self.selected.clear()
        self.selected_ws.clear()
        wids = [w.wid for w in workspaces]
        if self.current_wid not in wids:
            self.current_wid = wids[0] if wids else ""
        self._rebuild_cards()
        self._rebuild_rows()
        total = sum(len(w.sessions) for w in workspaces)
        if self._pinned:
            return
        if total:
            unregistered = [w for w in workspaces if w.unregistered]
            suffix = f"（{len(unregistered)}个未登记，可从卡片⋯菜单添加）" if unregistered else ""
            self._set_banner(f"共{len(workspaces)}个工作区 · {total}个对话" + suffix, BannerTone.INFO)
        else:
            self._set_banner("还没有找到任何对话。", BannerTone.WARNING)

    def _on_scan_failed(self, message: str) -> None:
        self._busy = False
        self._refresh.set_enabled_state(True)
        self._last_details = message
        self._set_banner("扫描失败，点右侧查看详情。", BannerTone.ERROR, "查看详情")

    def _workspace(self, wid: str):
        for ws in self.workspaces:
            if ws.wid == wid:
                return ws
        return None

    # ------------------------------------------------------------ 渲染
    def _rebuild_cards(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for workspace in self.workspaces:
            card = WorkspaceCard(workspace, self._cards_body)
            card.clicked.connect(self._on_card_clicked)
            card.action.connect(self._on_card_action)
            card.set_selected(workspace.wid == self.current_wid)
            card.toggled.connect(self._on_card_toggled)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
            self._cards.append(card)
        self._refresh_card_states()

    def _rebuild_rows(self) -> None:
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows = {}
        workspace = self._workspace(self.current_wid)
        keyword = self._search.text().strip().lower()
        count = 0
        if workspace is not None:
            for session in workspace.sessions:
                if keyword and keyword not in session.title.lower():
                    continue
                row = ConversationRow(session, self._list_body)
                row.toggled.connect(self._on_row_toggled)
                row.set_checked(session.sid in self.selected)
                self._list_layout.insertWidget(self._list_layout.count() - 1, row)
                self._rows[session.sid] = row
                count += 1
        self._empty.setVisible(count == 0)
        if count == 0:
            self._empty.setText("（这条工作区还没有对话）" if not keyword else "没有匹配的对话")
        self._update_action_bar()

    def _update_action_bar(self) -> None:
        n = len(self.selected)
        w = len(self.selected_ws)
        restart = self.settings.get_bool("restart_after_delete", True)
        self._delete_btn.set_text("删除并重启" if restart else "删除")
        self._delete_btn.set_enabled_state((n > 0 or w > 0) and not self._busy)
        self._cancel_sel.set_enabled_state(n > 0 or w > 0)
        self._cancel_sel.fit_to_text()
        delete_x = 976 - self._delete_btn.width()
        self._delete_btn.move(delete_x, 604)
        self._cancel_sel.move(delete_x - 8 - self._cancel_sel.width(), 604)
        if n or w:
            parts = []
            if n:
                parts.append(f"{n}个对话")
            if w:
                parts.append(f"{w}个工作区")
            self._sel_label.setText("已选" + " · ".join(parts))
        else:
            self._sel_label.setText("")
        workspace = self._workspace(self.current_wid)
        if workspace is not None:
            note = " · 未登记到DSH，可从卡片⋯菜单添加" if workspace.unregistered else ""
            if n == 0 and w == 0 and not workspace.unregistered:
                note = " · 数据目录 " + self.dsh_home
            self._hint.setText(f"{workspace.title} · {len(workspace.sessions)}个对话" + note)
        self._sync_select_all()

    def _sync_select_all(self) -> None:
        sids = [sid for sid in self._rows]
        if not sids:
            self._select_all.set_checked(False)
            self._select_all.set_partial(False)
            return
        chosen = sum(1 for sid in sids if sid in self.selected)
        self._select_all.set_checked(chosen == len(sids))
        self._select_all.set_partial(0 < chosen < len(sids))

    def _set_banner(self, message: str, tone: str, action: str = "", pin: bool = False) -> None:
        if pin:
            self._pinned = True
        self._banner.set_message(message, tone, action)
        self._banner.setVisible(bool(message))

    def _show_details(self) -> None:
        if self._last_details:
            DetailsDialog(self, "详细信息", self._last_details).exec()

    # ------------------------------------------------------------ 交互
    def _on_card_clicked(self, wid: str) -> None:
        self.current_wid = wid
        for card in self._cards:
            card.set_selected(card.workspace.wid == wid)
        self._rebuild_rows()

    def _on_row_toggled(self, sid: str, checked: bool) -> None:
        if checked:
            self.selected.add(sid)
        else:
            self.selected.discard(sid)
            self._drop_workspace_for_session(sid)
        self._refresh_card_states()
        self._update_action_bar()

    def _on_card_toggled(self, wid: str, checked: bool) -> None:
        workspace = self._workspace(wid)
        if workspace is None:
            return
        sids = {s.sid for s in workspace.sessions}
        if checked:
            self.selected.update(sids)
            self.selected_ws.add(wid)
        else:
            self.selected.difference_update(sids)
            self.selected_ws.discard(wid)
        for sid, row in self._rows.items():
            if sid in sids:
                row.set_checked(checked)
        self._refresh_card_states()
        self._update_action_bar()

    def _drop_workspace_for_session(self, sid: str) -> None:
        for workspace in self.workspaces:
            if any(s.sid == sid for s in workspace.sessions):
                self.selected_ws.discard(workspace.wid)
                return

    def _refresh_card_states(self) -> None:
        for card in self._cards:
            workspace = card.workspace
            sids = [s.sid for s in workspace.sessions]
            chosen = sum(1 for sid in sids if sid in self.selected)
            checked = workspace.wid in self.selected_ws
            card.set_check_state(checked, (not checked) and chosen > 0)

    def _on_restart_toggled(self, value: bool) -> None:
        self.settings.set_bool("restart_after_delete", value)
        self._update_action_bar()

    def _on_select_all(self, checked: bool) -> None:
        for sid, row in self._rows.items():
            row.set_checked(checked)
            if checked:
                self.selected.add(sid)
            else:
                self.selected.discard(sid)
        if not checked:
            for workspace in self.workspaces:
                if any(s.sid in self._rows for s in workspace.sessions):
                    self.selected_ws.discard(workspace.wid)
        self._refresh_card_states()
        self._update_action_bar()

    def _select_all_now(self) -> None:
        if self._rows:
            self._select_all.set_checked(True, emit=True)

    def _clear_selection(self) -> None:
        self.selected.clear()
        self.selected_ws.clear()
        self._select_all.set_checked(False)
        self._select_all.set_partial(False)
        for row in self._rows.values():
            row.set_checked(False)
        self._refresh_card_states()
        self._update_action_bar()

    def _manual_refresh(self) -> None:
        self._pinned = False
        self.refresh()

    def _show_about(self) -> None:
        from . import __version__
        AboutDialog(self, __version__, self.dsh_home).exec()

    def _on_search(self, _text: str) -> None:
        self._rebuild_rows()

    def _open_data_dir(self) -> None:
        try:
            os.startfile(self.dsh_home)
        except OSError:
            self._set_banner("打不开数据目录。", BannerTone.WARNING)


    def _add_workspace_dialog(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "选择要添加到管理器的工作区文件夹")
        if not path:
            return
        self._register_workspace(path)

    def _register_workspace(self, path: str) -> None:
        """把文件夹登记进workspace.json，并挂上目录匹配的对话。"""
        if self._busy or not path:
            return
        try:
            data = store.load_json(self.store_path)
            wanted = model.norm_path(path)
            sids = []
            for workspace in self.workspaces:
                for session in workspace.sessions:
                    if model.norm_path(session.cwd) == wanted:
                        sids.append(session.sid)
            title = os.path.basename(path.rstrip("\\/")) or path
            store.backup(self.store_path)
            store.add_workspace(data, path, title, sids)
            store.atomic_write(self.store_path, store.dump_json(data))
            self._pinned = True
            self._set_banner(f"已添加工作区「{title}」，关联{len(sids)}个对话", BannerTone.SUCCESS, pin=True)
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            self._last_details = repr(exc)
            self._set_banner("添加工作区失败，点右侧查看详情。", BannerTone.ERROR, "查看详情")

    def _selected_sessions(self) -> list:
        result = []
        for workspace in self.workspaces:
            for session in workspace.sessions:
                if session.sid in self.selected:
                    result.append(session)
        return result

    # ------------------------------------------------------------ 删除
    def _delete_selected(self) -> None:
        if isinstance(QApplication.focusWidget(), QLineEdit):
            return
        sessions = self._selected_sessions()
        workspace_ids = [wid for wid in self.selected_ws if self._workspace(wid) is not None]
        if (not sessions and not workspace_ids) or self._busy:
            return
        items = [f"{s.title}（{s.rel_time}）" for s in sessions]
        for wid in workspace_ids:
            workspace = self._workspace(wid)
            items.append(f"整个工作区：{workspace.title}")
        if workspace_ids and sessions:
            title = f"删除{len(sessions)}个对话和{len(workspace_ids)}个工作区？"
        elif workspace_ids:
            title = f"删除{len(workspace_ids)}个工作区？"
        else:
            title = f"删除{len(sessions)}个对话？"
        message = "会话日志和缓存会被永久删除，无法恢复。"
        if workspace_ids:
            message += "工作区会从DSH列表中移除登记，文件夹本身保留。"
        message += "workspace.json会在写入前自动备份。"
        dialog = ConfirmDialog(
            self,
            title,
            message,
            items,
            confirm_label="删除",
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self._run_delete(sessions, workspace_ids)

    def _on_card_action(self, wid: str, action: str) -> None:
        workspace = self._workspace(wid)
        if workspace is None or self._busy:
            return
        sessions = list(workspace.sessions)
        if action == "register":
            self._register_workspace(workspace.register_path or workspace.path)
            return

        if action == "unregister":
            dialog = ConfirmDialog(
                self,
                f"移除工作区「{workspace.title}」？",
                "只从DSH的列表里移除登记，工作区文件夹和对话日志都会保留。",
                [],
                confirm_label="移除",
            )
            if dialog.exec() == ConfirmDialog.Accepted:
                self._run_delete([], [wid])
            return

        items = [f"{s.title}（{s.rel_time}）" for s in sessions[:8]]
        dialog = ConfirmDialog(
            self,
            f"删除「{workspace.title}」的全部{len(sessions)}个对话？",
            "会话日志和缓存会被永久删除，无法恢复；工作区文件夹本身会保留。",
            items,
            confirm_label="全部删除",
        )
        if dialog.exec() == ConfirmDialog.Accepted:
            self._run_delete(sessions, [wid])

    def _run_delete(self, sessions, workspace_ids) -> None:
        self._busy = True
        self._last_details = ""
        self._set_banner("", BannerTone.INFO)
        self._banner.setVisible(False)
        self._list_area.setVisible(False)
        self._empty.setVisible(False)
        self._progress.setVisible(True)
        for index, row in enumerate(self._steps):
            row.set_state(StepState.PENDING, "")
        self._bar.set_target(0.05)
        self._delete_btn.set_enabled_state(False)

        self._delete_worker = DeleteWorker(
            self.dsh_home, sessions, workspace_ids,
            self.settings.get_bool("restart_after_delete", True),
        )
        self._delete_worker.step.connect(self._on_delete_step)
        self._delete_worker.done.connect(self._on_delete_done)
        self._delete_worker.failed.connect(self._on_delete_failed)
        self._delete_worker.start()

    def _on_delete_step(self, index: int, state: str, text: str) -> None:
        if 0 <= index < len(self._steps):
            self._steps[index].set_state(state, text)
        progress = min(1.0, (index + (1.0 if state == StepState.DONE else 0.4)) / len(self._steps))
        self._bar.set_target(progress)

    def _on_delete_done(self, result) -> None:
        self._busy = False
        self._bar.set_target(1.0)
        self.selected.clear()
        self.selected_ws.clear()
        QTimer.singleShot(600, self._leave_progress)
        if result.errors:
            self._last_details = "\n".join(result.errors)
            self._set_banner(f"完成，但有{len(result.errors)}个问题，点右侧查看详情。",
                             BannerTone.WARNING, "查看详情")
        else:
            self._set_banner(
                f"已删除{result.deleted_sessions}个对话"
                + ("，并移除了工作区登记" if result.deleted_workspaces else "")
                + ("，备份：{}".format(os.path.basename(result.backup)) if result.backup else ""),
                BannerTone.SUCCESS,
            )
        self._pinned = True
        QTimer.singleShot(200, self.refresh)

    def _on_delete_failed(self, message: str) -> None:
        self._busy = False
        self._last_details = message
        self._leave_progress()
        self._set_banner("操作失败，点右侧查看详情。", BannerTone.ERROR, "查看详情")

    def _leave_progress(self) -> None:
        self._progress.setVisible(False)
        self._list_area.setVisible(True)
        self._update_action_bar()

    # ------------------------------------------------------------ 其他
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(theme.ROW_DIVIDER)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(QPointF(252, 52), QPointF(252, WIN_H - 1))
        painter.drawLine(QPointF(272, 596), QPointF(976, 596))
