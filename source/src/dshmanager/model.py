"""扫描 ~/.dsh，构建界面用的工作区 / 会话模型。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from .zstdlog import read_session_facts

UNGROUPED_ID = "__ungrouped__"


@dataclass
class Session:
    sid: str
    title: str
    rel_time: str
    size_text: str
    last_active: float
    size_bytes: int
    dir_path: str
    cache_path: str
    project_dir: str
    cwd: str = ""
    archived: bool = False
    pinned: bool = False


@dataclass
class Workspace:
    wid: str
    title: str
    path: str
    sessions: list[Session] = field(default_factory=list)
    is_default: bool = False
    is_ungrouped: bool = False
    unregistered: bool = False
    register_path: str = ""


def rel_time(epoch: float) -> str:
    if epoch <= 0:
        return ""
    delta = max(0.0, time.time() - epoch)
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)}分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)}小时前"
    if delta < 86400 * 30:
        return f"{int(delta // 86400)}天前"
    return time.strftime("%Y-%m-%d", time.localtime(epoch))


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f}KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    return f"{size / 1024 / 1024 / 1024:.2f}GB"


def norm_path(value: str) -> str:
    if not value:
        return ""
    return os.path.normcase(os.path.normpath(value))


def _session_dirs(sessions_root: str) -> list[tuple[str, str]]:
    """返回 (项目目录, 会话目录) 列表。"""
    found: list[tuple[str, str]] = []
    if not os.path.isdir(sessions_root):
        return found
    for project in sorted(os.listdir(sessions_root)):
        project_dir = os.path.join(sessions_root, project)
        if not os.path.isdir(project_dir):
            continue
        for name in os.listdir(project_dir):
            if not name.startswith("session-"):
                continue
            path = os.path.join(project_dir, name)
            if os.path.isdir(path):
                found.append((project_dir, path))
    return found


def _latest_log(session_dir: str) -> tuple[str, int]:
    best_path, best_mtime = "", 0.0
    try:
        for name in os.listdir(session_dir):
            if not name.startswith("session.v") or not name.endswith(".jsonl.zstd"):
                continue
            path = os.path.join(session_dir, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime >= best_mtime:
                best_path, best_mtime = path, mtime
    except OSError:
        pass
    return best_path, int(best_mtime)


def scan(dsh_home: str, store: dict) -> list[Workspace]:
    """把 workspace.json + sessions 目录合成工作区列表。

    已登记的工作区按 workspace.json 顺序输出；磁盘上存在但没有登记、
    或者登记里没有引用到的会话，会按会话记录的工作目录自动聚合成
    「未登记工作区」，交给用户在界面上决定是否登记进 DSH。
    """
    sessions_root = os.path.join(dsh_home, "sessions")
    cache_root = os.path.join(dsh_home, "storages", "session_projcache", "sessions")
    global_cfg = store.get("global") if isinstance(store.get("global"), dict) else {}
    archived = set(global_cfg.get("archivedSessionIds") or [])
    pinned = set(global_cfg.get("pinnedSessionIds") or [])
    workspaces_raw = ((store.get("tables") or {}).get("workspaces") or {})
    default_id = str(global_cfg.get("defaultWorkspaceId") or "")

    sessions: dict[str, Session] = {}
    for project_dir, session_dir in _session_dirs(sessions_root):
        log_path, mtime = _latest_log(session_dir)
        fallback = os.path.basename(session_dir)
        facts = read_session_facts(log_path, fallback) if log_path else None
        if facts is None:
            from .zstdlog import SessionFacts
            facts = SessionFacts(session_id=fallback)
        last_active = float(mtime or 0.0)
        size_bytes = 0
        try:
            for root, _dirs, names in os.walk(session_dir):
                for name in names:
                    try:
                        size_bytes += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
        except OSError:
            pass
        sid = facts.session_id or fallback
        title = facts.title or "（未命名对话）"
        sessions[sid] = Session(
            sid=sid,
            title=title,
            rel_time=rel_time(last_active),
            size_text=human_size(size_bytes),
            last_active=last_active,
            size_bytes=size_bytes,
            dir_path=session_dir,
            cache_path=os.path.join(cache_root, f"{sid}.json"),
            project_dir=project_dir,
            cwd=facts.cwd,
            archived=sid in archived,
            pinned=sid in pinned,
        )

    used: set[str] = set()
    result: list[Workspace] = []
    for wid in (global_cfg.get("workspaceIds") or list(workspaces_raw.keys())):
        raw = workspaces_raw.get(wid)
        if not isinstance(raw, dict):
            continue
        ws = Workspace(
            wid=str(wid),
            title=str(raw.get("title") or os.path.basename(str(raw.get("path") or "")) or "（未命名工作区）"),
            path=str(raw.get("path") or ""),
            is_default=str(wid) == default_id,
        )
        for sid in (raw.get("sessionIds") or []):
            session = sessions.get(str(sid))
            if session is not None:
                ws.sessions.append(session)
                used.add(str(sid))
        ws.sessions.sort(key=lambda s: s.last_active, reverse=True)
        result.append(ws)

    leftovers = [s for sid, s in sessions.items() if sid not in used]
    leftovers.sort(key=lambda s: s.last_active, reverse=True)
    buckets: dict[str, list[Session]] = {}
    for session in leftovers:
        key = norm_path(session.cwd)
        buckets.setdefault(key or "", []).append(session)

    ordered = sorted(
        buckets.items(),
        key=lambda kv: max(s.last_active for s in kv[1]),
        reverse=True,
    )
    for key, items in ordered:
        if key:
            raw_path = items[0].cwd
            title = os.path.basename(raw_path.rstrip("\\/")) or raw_path
            result.append(
                Workspace(
                    wid=f"cwd:{key}",
                    title=title,
                    path=raw_path,
                    sessions=items,
                    unregistered=True,
                    register_path=raw_path,
                )
            )
        else:
            result.append(
                Workspace(
                    wid=UNGROUPED_ID,
                    title="未分组对话",
                    path="没有记录工作目录",
                    sessions=items,
                    is_ungrouped=True,
                )
            )
    return result
