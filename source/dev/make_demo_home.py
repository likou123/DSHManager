
"""生成一个演示用的 DSH 数据目录（假数据），用于截图时不暴露真实环境。

用法：python dev/make_demo_home.py D:\\demo\\.dsh
"""
import json
import os
import sys
import time
import uuid

import zstandard


WORKSPACES = [
    ("demo-web", r"D:\Projects\demo-web", [
        ("重构登录页样式", 2),
        ("修复深色模式下的对比度", 26),
        ("接入 mock 接口", 180),
        ("打包体积优化", 400),
        ("整理组件目录", 1500),
    ]),
    ("demo-api", r"D:\Projects\demo-api", [
        ("补全用户接口文档", 60),
        ("修复分页边界问题", 240),
        ("增加请求重试", 900),
        ("数据库迁移脚本", 2200),
    ]),
    ("docs-site", r"D:\Projects\docs-site", [
        ("更新快速开始", 120),
        ("补写部署说明", 700),
        ("整理常见问题", 5000),
    ]),
]


def session_id() -> str:
    return "session-" + str(uuid.uuid4())


def make_log(path: str, sid: str, cwd: str, title: str, created: float) -> None:
    header = {
        "type": "session", "version": 4, "id": sid, "createdAt": int(created * 1000),
        "cwd": cwd, "isSeeded": False, "delegationDepth": 0, "agentPreset": "ops-ptc",
    }
    events = [
        header,
        {"type": "session/title", "seq": 0, "time": int(created * 1000) + 5000, "data": {"title": title}},
        {"type": "message", "seq": 1, "time": int(created * 1000) + 9000,
         "data": {"role": "user", "content": "演示数据：这里的对话来自虚构的工作区。"}},
    ]
    payload = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
    compressed = zstandard.ZstdCompressor().compress(payload.encode("utf-8"))
    with open(path, "wb") as handle:
        handle.write(compressed)


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "dsh-demo-home")
    storages = os.path.join(root, "storages")
    sessions = os.path.join(root, "sessions")
    os.makedirs(storages, exist_ok=True)
    os.makedirs(sessions, exist_ok=True)

    now = time.time()
    wids = []
    table = {}
    for name, path, items in WORKSPACES:
        wid = str(uuid.uuid4())
        wids.append(wid)
        sids = []
        project = os.path.join(sessions, "--" + path.replace(":", "").replace("\\", "-") + "--")
        for title, age_min in items:
            sid = session_id()
            sids.append(sid)
            folder = os.path.join(project, sid)
            os.makedirs(folder, exist_ok=True)
            created = now - age_min * 60
            log = os.path.join(folder, "session.v4.jsonl.zstd")
            make_log(log, sid, path, title, created)
            os.utime(log, (created, created))
        table[wid] = {
            "path": path,
            "title": name,
            "sessionIds": sids,
            "createdAt": "2026-10-01T09:00:00.000Z",
            "updatedAt": "2026-11-15T08:00:00.000Z",
        }

    store = {
        "unit": {"name": "workspace", "version": 2},
        "global": {
            "initialized": True,
            "defaultWorkspaceId": wids[0],
            "workspaceIds": wids,
            "archivedSessionIds": [],
            "pinnedSessionIds": [table[wids[0]]["sessionIds"][0]],
        },
        "tables": {"workspaces": table},
    }
    with open(os.path.join(storages, "workspace.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(store, handle, ensure_ascii=False, indent=2)
    print("demo home:", root, "workspaces:", len(wids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
