"""入口：--relaunch-waiter 隐藏模式 / --selftest 无界面自检 / 正常启动图形界面。"""

from __future__ import annotations

import json
import os
import sys


def _selftest(out_path: str) -> int:
    """无界面自检：扫描一遍数据目录，把结果写到指定文件。"""
    from . import model, store

    dsh_home = os.environ.get("DSH_HOME") or os.path.join(os.path.expanduser("~"), ".dsh")
    try:
        data = store.load_json(store.workspace_path(dsh_home))
        workspaces = model.scan(dsh_home, data)
        payload = {
            "ok": True,
            "dsh_home": dsh_home,
            "workspaces": [
                {"title": w.title, "path": w.path, "sessions": [
                    {"sid": s.sid, "title": s.title, "rel": s.rel_time} for s in w.sessions
                ]}
                for w in workspaces
            ],
        }
        code = 0
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": repr(exc)}
        code = 1
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return code


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--relaunch-waiter":
        from .restart import waiter_main
        return waiter_main(argv[1:])
    if argv and argv[0] == "--selftest":
        return _selftest(argv[1] if len(argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "dshmanager-selftest.json"))

    from PySide6.QtWidgets import QApplication

    from . import theme
    from .ui_main import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("DSH 对话管理器")
    app.setApplicationDisplayName("DSH 对话管理器")
    app.setFont(theme.font(9.3))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
