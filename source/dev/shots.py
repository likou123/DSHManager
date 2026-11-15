"""为交付生成多状态截图：主界面 / 确认框 / 进度。"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from dshmanager.dialogs import ConfirmDialog  # noqa: E402
from dshmanager.ui_main import MainWindow  # noqa: E402

OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

app = QApplication([])
window = MainWindow()
window.show()


def save(widget, name):
    widget.grab().save(os.path.join(OUT, name))
    print("saved", name, widget.width(), widget.height())


def selection_title() -> str:
    sessions = len(window.selected)
    spaces = len(window.selected_ws)
    if spaces and sessions:
        return f"删除{sessions}个对话和{spaces}个工作区？"
    if spaces:
        return f"删除{spaces}个工作区？"
    return f"删除{sessions}个对话？"


def step1():
    save(window, "01-main.png")
    workspaces = window.workspaces
    api = next((w for w in workspaces if w.title == "demo-api"), None)
    if api is not None:
        window._on_card_toggled(api.wid, True)
    rows = list(window._rows.values())
    for row in rows[:2]:
        row.set_checked(True)
        window._on_row_toggled(row.session.sid, True)
    save(window, "02-selected.png")

    items = [r.session.title for r in rows[:2]]
    if api is not None:
        items.append(f"整个工作区：{api.title}")
    dialog = ConfirmDialog(
        window,
        selection_title(),
        "会话日志和缓存会被永久删除，无法恢复。工作区会从DSH列表中移除登记，文件夹本身保留。workspace.json 会在写入前自动备份。",
        items,
    )
    dialog.show()
    QTimer.singleShot(200, lambda: (save(dialog, "03-confirm.png"), step2(dialog)))


def step2(dialog):
    dialog.close()
    window._list_area.setVisible(False)
    window._empty.setVisible(False)
    window._progress.setVisible(True)
    window._steps[0].set_state("done", "6个")
    window._steps[1].set_state("done", "已清理")
    window._steps[2].set_state("working", "写入中")
    window._bar.set_target(0.66)
    window._set_banner("已删除6个对话和1个工作区，备份workspace.json.bak-20261114230000", "success")
    QTimer.singleShot(300, lambda: (save(window, "04-progress.png"), app.quit()))


QTimer.singleShot(1800, step1)
sys.exit(app.exec())
