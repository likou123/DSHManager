"""测试：未登记工作区自动聚合 + 手动登记。"""

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from dshmanager import model, store  # noqa: E402

REAL = os.path.join(os.path.expanduser("~"), ".dsh")
sandbox = tempfile.mkdtemp(prefix="dshm-ws-")
for name in ("sessions", "storages"):
    shutil.copytree(os.path.join(REAL, name), os.path.join(sandbox, name))

wpath = store.workspace_path(sandbox)
data = store.load_json(wpath)

# 1) 把第一个工作区的登记删掉，模拟"磁盘上有会话但没登记"
first_wid = data["global"]["workspaceIds"][0]
record = data["tables"]["workspaces"].pop(first_wid)
data["global"]["workspaceIds"] = [w for w in data["global"]["workspaceIds"] if w != first_wid]
store.atomic_write(wpath, store.dump_json(data))

data2 = store.load_json(wpath)
workspaces = model.scan(sandbox, data2)
unregistered = [w for w in workspaces if w.unregistered]
print("UNREGISTERED_GROUPS", len(unregistered), [w.title for w in unregistered])
print("UNREGISTERED_HAS_PATH", all(w.path for w in unregistered))
print("UNREGISTERED_SESSIONS", sum(len(w.sessions) for w in unregistered))

# 2) 手动登记其中一个
target = unregistered[0]
sids = [s.sid for s in target.sessions]
store.backup(wpath)
store.add_workspace(data2, target.path, "手动添加", sids)
store.atomic_write(wpath, store.dump_json(data2))

data3 = store.load_json(wpath)
new_ids = [wid for wid in data3["global"]["workspaceIds"] if wid not in data2["global"]["workspaceIds"] or True]
added = [wid for wid, rec in data3["tables"]["workspaces"].items() if rec.get("title") == "手动添加"]
print("ADDED_TABLE", len(added) == 1)
print("ADDED_IN_GLOBAL", bool(added) and added[0] in data3["global"]["workspaceIds"])
print("ADDED_SESSION_IDS", len(data3["tables"]["workspaces"][added[0]]["sessionIds"]) == len(sids) if added else False)

after = model.scan(sandbox, data3)
still_unregistered = [w for w in after if w.unregistered and w.title == target.title]
print("NO_LONGER_UNREGISTERED", len(still_unregistered) == 0)
print("WS_COUNT", len(after))
shutil.rmtree(sandbox, ignore_errors=True)
