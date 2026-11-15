using System;
using System.IO;
using System.Text;
using System.Diagnostics;
using System.Reflection;

internal static class Program
{
    private static int Main()
    {
        try { Console.OutputEncoding = new UTF8Encoding(false); }
        catch { }
        try { Console.Title = "DSH 对话管理器"; }
        catch { }

        string dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "DSHManager");
        string script = Path.Combine(dir, "dsh-manager.mjs");

        try
        {
            Directory.CreateDirectory(dir);
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("dsh-manager.mjs"))
            {
                if (s == null)
                {
                    Console.WriteLine("内置脚本丢失，无法启动。");
                    Pause();
                    return 1;
                }
                using (FileStream f = File.Create(script))
                {
                    s.CopyTo(f);
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("释放内置脚本失败：" + ex.Message);
            Pause();
            return 1;
        }

        string node = FindNode();
        if (node == null)
        {
            Console.WriteLine("没有找到 Node 运行时。");
            Console.WriteLine("请确认 DeepSeek Harness 已正常安装（找不到 .dsh\\dsh-runtimes 下的 node.exe）。");
            Pause();
            return 1;
        }

        try
        {
            ProcessStartInfo psi = new ProcessStartInfo(node, "\"" + script + "\"");
            psi.UseShellExecute = false;
            psi.WorkingDirectory = dir;
            Process p = Process.Start(psi);
            p.WaitForExit();
            return p.ExitCode;
        }
        catch (Exception ex)
        {
            Console.WriteLine("启动失败：" + ex.Message);
            Pause();
            return 1;
        }
    }

    private static string FindNode()
    {
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

        string[] candidates = new string[]
        {
            Path.Combine(home, ".dsh", "dsh-runtimes", "dsh-primary-runtime", "dependencies", "node", "bin", "node.exe"),
            Path.Combine(local, "Programs", "DeepSeek Harness", "resources", "runtime", "primary-runtime", "dependencies", "node", "bin", "node.exe")
        };

        foreach (string c in candidates)
        {
            if (File.Exists(c)) return c;
        }

        string runtimes = Path.Combine(home, ".dsh", "dsh-runtimes");
        if (Directory.Exists(runtimes))
        {
            foreach (string dir in Directory.GetDirectories(runtimes))
            {
                string c = Path.Combine(dir, "dependencies", "node", "bin", "node.exe");
                if (File.Exists(c)) return c;
            }
        }

        string pathVar = Environment.GetEnvironmentVariable("PATH");
        if (pathVar != null)
        {
            foreach (string part in pathVar.Split(';'))
            {
                if (part.Length == 0) continue;
                try
                {
                    string c = Path.Combine(part.Trim(), "node.exe");
                    if (File.Exists(c)) return c;
                }
                catch { }
            }
        }

        return null;
    }

    private static void Pause()
    {
        Console.WriteLine("");
        Console.WriteLine("按回车键退出...");
        try { Console.ReadLine(); }
        catch { }
    }
}
