"""测试：waiter 等待目标进程退出后再拉起。"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from dshmanager import restart  # noqa: E402

work = os.path.join(HERE, "out")
os.makedirs(work, exist_ok=True)
marker_src = os.path.join(work, "marker.cs")
marker_exe = os.path.join(work, "marker.exe")
open(marker_src, "w", encoding="utf-8").write(
    "using System;using System.IO;internal static class P{private static void Main(){"
    "File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,\"fired.txt\"),"
    "DateTime.Now.ToString(\"HH:mm:ss.fff\"));}}"
)
csc = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
subprocess.run([csc, "/nologo", "/out:" + marker_exe, marker_src], check=True, capture_output=True)
for name in ("fired.txt",):
    path = os.path.join(work, name)
    if os.path.exists(path):
        os.remove(path)

dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2.0)"])
start = time.time()
rc = restart.waiter_main([marker_exe, str(dummy.pid)])
elapsed = time.time() - start
time.sleep(0.6)
fired = os.path.exists(os.path.join(work, "fired.txt"))
print("waiter rc:", rc, "elapsed: %.2fs" % elapsed, "fired:", fired)
print("PID_ALIVE_SELF:", restart.pid_alive(os.getpid()))
print("PID_ALIVE_DEAD:", restart.pid_alive(999999))
print("LIST_PIDS:", restart.list_pids()[:5], "count", len(restart.list_pids()))
print("FIND_EXE:", restart.find_exe())
