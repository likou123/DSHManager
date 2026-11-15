"""沙盒测试：复制真实数据，验证删除 / 移除工作区的语义。"""

import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from dshmanager import model, store  # noqa: E402
from dshmanager.ui_main import DeleteWorker  # noqa: E402

REAL = os.path.join(os.path.expanduser("~"), ".dsh")
sandbox = tempfile.mkdtemp(prefix="dshm-test-")
for name in ("sessions", "storages"):
    shutil.copytree(os.path.join(REAL, name), os.path.join(sandbox, name))

app = QCoreApplication([])
wpath = store.workspace_path(sandbox)
data = store.load_json(wpath)
workspaces = model.scan(sandbox, data)
ws = workspaces[0]
target = ws.sessions[0]
print("sandbox:", sandbox)
print("workspace:", ws.title, "sessions:", len(ws.sessions))
print("target:", target.title, target.sid)

results = {}


def run_worker(sessions, wids, key):
    worker = DeleteWorker(sandbox, sessions, wids, False)
    worker.done.connect(lambda res: (results.__setitem__(key, res), app.quit()))
    worker.failed.connect(lambda msg: (print("FAILED", msg), app.quit()))
    worker.start()
    app.exec()


run_worker([target], [], "del")
res = results.get("del")
after = store.load_json(wpath)
flat = [sid for rec in after["tables"]["workspaces"].values() for sid in rec.get("sessionIds", [])]
print("SESSION_DIR_GONE", not os.path.exists(target.dir_path))
print("CACHE_GONE", not os.path.exists(target.cache_path))
print("REF_REMOVED", target.sid not in flat)
print("ARCHIVED_REMOVED", target.sid not in after["global"]["archivedSessionIds"])
print("BACKUP_EXISTS", bool(res.backup) and os.path.exists(res.backup))
print("DELETED_COUNT", res.deleted_sessions, "errors", res.errors)
print("WORKSPACE_IDS_UNCHANGED", after["global"]["workspaceIds"] == data["global"]["workspaceIds"])

run_worker([], [ws.wid], "ws")
after2 = store.load_json(wpath)
print("WS_TABLE_GONE", ws.wid not in after2["tables"]["workspaces"])
print("WS_GLOBAL_GONE", ws.wid not in after2["global"]["workspaceIds"])
print("WS_DEFAULT_KEPT", after2["global"].get("defaultWorkspaceId") == data["global"].get("defaultWorkspaceId"))
print("BACKUP2", bool(results.get("ws").backup) if results.get("ws") else None)
shutil.rmtree(sandbox, ignore_errors=True)
