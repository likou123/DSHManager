"""workspace.json 的读写、备份、原子写与删除语义。"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field


@dataclass
class DeleteResult:
    deleted_sessions: int = 0
    deleted_workspaces: int = 0
    backup: str = ""
    errors: list[str] = field(default_factory=list)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(store: dict) -> str:
    return json.dumps(store, ensure_ascii=False, indent=2)


def backup(path: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    target = f"{path}.bak-{stamp}"
    shutil.copy2(path, target)
    return target


def atomic_write(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def delete_session_files(session) -> list[str]:
    """删会话目录 + 会话缓存；返回错误说明（不抛异常）。"""
    errors: list[str] = []
    for path in (session.dir_path, session.cache_path):
        if not path:
            continue
        if os.path.isdir(path):
            try:
                shutil.rmtree(path)
            except (OSError, PermissionError) as exc:
                errors.append(f"{os.path.basename(path)}：{exc.strerror or exc}")
        elif os.path.isfile(path):
            try:
                os.remove(path)
            except (OSError, PermissionError) as exc:
                errors.append(f"{os.path.basename(path)}：{exc.strerror or exc}")
    return errors


def clean_references(store: dict, session_ids: set[str], workspace_ids: set[str]) -> bool:
    """从 workspace.json 里摘掉会话/工作区引用，返回是否有改动。"""
    changed = False
    global_cfg = store.setdefault("global", {})
    tables = store.setdefault("tables", {})
    workspaces = tables.get("workspaces") or {}

    if session_ids:
        for wid, record in list(workspaces.items()):
            ids = record.get("sessionIds")
            if isinstance(ids, list):
                kept = [sid for sid in ids if str(sid) not in session_ids]
                if len(kept) != len(ids):
                    record["sessionIds"] = kept
                    changed = True
        for key in ("archivedSessionIds", "pinnedSessionIds"):
            ids = global_cfg.get(key)
            if isinstance(ids, list):
                kept = [sid for sid in ids if str(sid) not in session_ids]
                if len(kept) != len(ids):
                    global_cfg[key] = kept
                    changed = True

    if workspace_ids:
        for wid in list(workspace_ids):
            if wid in workspaces:
                del workspaces[wid]
                changed = True
            ids = global_cfg.get("workspaceIds")
            if isinstance(ids, list) and wid in ids:
                global_cfg["workspaceIds"] = [x for x in ids if x != wid]
                changed = True
        if changed:
            tables["workspaces"] = workspaces
            # defaultWorkspaceId 保持原样：与 DSH 语义一致，删了也不清空
    return changed


def workspace_path(dsh_home: str) -> str:
    return os.path.join(dsh_home, "storages", "workspace.json")

def add_workspace(store: dict, path: str, title: str, session_ids: list[str]) -> str:
    """把一个新工作区登记进 workspace.json，返回新的 workspace id。"""
    import uuid
    from datetime import datetime, timezone

    wid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    global_cfg = store.setdefault("global", {})
    tables = store.setdefault("tables", {})
    workspaces = tables.setdefault("workspaces", {})
    ids = global_cfg.setdefault("workspaceIds", [])
    if wid not in ids:
        ids.append(wid)
    workspaces[wid] = {
        "path": path,
        "title": title,
        "sessionIds": list(session_ids),
        "createdAt": now,
        "updatedAt": now,
    }
    return wid

