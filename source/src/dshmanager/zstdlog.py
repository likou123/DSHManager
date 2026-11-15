"""多帧 zstd 会话日志解码：只取会话头与标题，避免整份日志解压。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import zstandard

HEAD_LIMIT = 1_600_000      # 先读这么多压缩字节，绝大多数会话头 + 标题都在里面
TAIL_LIMIT = 2_400_000      # 头部没找到标题时，再补读尾部
MAGIC = b"\x28\xb5\x2f\xfd"


@dataclass
class SessionFacts:
    session_id: str = ""
    cwd: str = ""
    title: str = ""
    created_at: float = 0.0
    last_active: float = 0.0


def _decode(buf: bytes) -> str:
    """把一段（可能由多个独立帧首尾相接的）zstd 数据解成长文本。"""
    if not buf:
        return ""
    try:
        dctx = zstandard.ZstdDecompressor()
        with dctx.stream_reader(buf, read_across_frames=True) as reader:
            chunks = []
            while True:
                try:
                    chunk = reader.read(1 << 20)
                except Exception:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", "replace")
    except Exception:
        return ""


def _first_frame_boundary(buf: bytes, start: int) -> int:
    idx = buf.find(MAGIC, start)
    return idx if idx >= 0 else -1


def _scan(text: str, facts: SessionFacts) -> None:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        kind = obj.get("type") or ""
        if kind == "session" and not facts.cwd:
            data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
            facts.session_id = str(data.get("id") or obj.get("id") or "")
            facts.cwd = str(data.get("cwd") or obj.get("cwd") or "")
            created = data.get("createdAt") or obj.get("createdAt")
            if isinstance(created, (int, float)):
                facts.created_at = float(created)
            elif isinstance(created, str):
                facts.created_at = _iso_to_epoch(created)
        elif kind == "session/title":
            data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                facts.title = title.strip()


def _iso_to_epoch(value: str) -> float:
    from datetime import datetime, timezone
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return 0.0


def read_session_facts(log_path: str, fallback_id: str = "") -> SessionFacts:
    facts = SessionFacts(session_id=fallback_id)
    try:
        size = os.path.getsize(log_path)
        with open(log_path, "rb") as handle:
            head = handle.read(min(size, HEAD_LIMIT))
        text = _decode(head)
        _scan(text, facts)
        if not facts.title and size > HEAD_LIMIT:
            with open(log_path, "rb") as handle:
                start = max(0, size - TAIL_LIMIT)
                handle.seek(start)
                tail = handle.read()
            boundary = _first_frame_boundary(tail, 0)
            if boundary >= 0:
                _scan(_decode(tail[boundary:]), facts)
        if not facts.title:
            _scan(text, facts)
    except (OSError, PermissionError):
        pass
    return facts
