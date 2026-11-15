"""结束并重新拉起 DSH：PID 探测、等待退出、taskkill 诊断、UAC 重试。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import ctypes

IMAGE = "DeepSeek Harness.exe"
WAIT_LIMIT_MS = 90_000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def find_exe() -> str:
    override = os.environ.get("DSH_MANAGER_EXE", "")
    if override and os.path.isfile(override):
        return override
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local, "Programs", "DeepSeek Harness", "DeepSeek Harness.exe") if local else "",
        r"C:\Program Files\DeepSeek Harness\DeepSeek Harness.exe",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def list_pids() -> list[int]:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {IMAGE}", "/FO", "CSV", "/NH"],
            capture_output=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in out.decode("mbcs", "replace").splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == IMAGE.lower():
            try:
                pids.append(int(parts[1]))
            except ValueError:
                pass
    return pids


_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = _KERNEL32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # 拒绝访问说明进程还在，只是权限不够
        return ctypes.get_last_error() == 5
    try:
        code = ctypes.c_ulong()
        if not _KERNEL32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259  # STILL_ACTIVE
    finally:
        _KERNEL32.CloseHandle(handle)


def kill_dsh() -> tuple[bool, int, str]:
    try:
        proc = subprocess.run(
            ["taskkill", "/F", "/IM", IMAGE],
            capture_output=True,
            timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, -1, str(exc)
    raw = (proc.stdout or b"").decode("mbcs", "replace") + (proc.stderr or b"").decode("mbcs", "replace")
    detail = " ".join(raw.split())
    return proc.returncode == 0, proc.returncode, detail


def kill_elevated() -> bool:
    try:
        params = "/F /IM \"DeepSeek Harness.exe\""
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "taskkill", params, None, 0)
        return int(rc) > 32
    except Exception:
        return False


def _command_prefix() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "dshmanager"]


def spawn_waiter(exe: str, pids: list[int]) -> None:
    """起一个脱离本进程的 waiter：等这些 PID 全部退出后再拉起 exe。"""
    args = _command_prefix() + ["--relaunch-waiter", exe] + [str(p) for p in pids]
    subprocess.Popen(
        args,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def spawn_detached(exe: str) -> None:
    subprocess.Popen(
        [exe],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def waiter_main(argv: list[str]) -> int:
    """--relaunch-waiter <exe> <pid...>：隐藏进程，等目标退出后拉起。"""
    if not argv:
        return 2
    exe = argv[0]
    pids = [int(x) for x in argv[1:] if x.isdigit()]
    deadline = time.time() + WAIT_LIMIT_MS / 1000.0
    while pids and any(pid_alive(p) for p in pids):
        if time.time() > deadline:
            return 3
        time.sleep(0.15)
    try:
        spawn_detached(exe)
    except OSError:
        return 4
    return 0
