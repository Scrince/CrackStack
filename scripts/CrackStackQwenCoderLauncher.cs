using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class CrackStackCodexLauncher
{
    [STAThread]
    private static int Main()
    {
        string exePath = Application.ExecutablePath;
        string root = Path.GetDirectoryName(exePath) ?? Environment.CurrentDirectory;
        string pythonw = Path.Combine(root, "runtime", "python", "windows-x64", "pythonw.exe");
        string python = Path.Combine(root, "runtime", "python", "windows-x64", "python.exe");
        string bat = Path.Combine(root, "run.bat");

        try
        {
            if (File.Exists(pythonw) || File.Exists(python))
            {
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = File.Exists(pythonw) ? pythonw : python,
                    Arguments = "-m harness.cli gui",
                    WorkingDirectory = root,
                    UseShellExecute = false
                };
                startInfo.EnvironmentVariables["CRACKSTACK_ROOT"] = root;
                startInfo.EnvironmentVariables["PYTHONPATH"] =
                    root + ";" + Path.Combine(root, "runtime", "site-packages", "windows-x64");
                startInfo.EnvironmentVariables["PATH"] =
                    Path.Combine(root, "runtime", "python", "windows-x64") + ";" +
                    Path.Combine(root, "runtime", "python", "windows-x64", "Scripts") + ";" +
                    Environment.GetEnvironmentVariable("PATH");
                Process.Start(startInfo);
                return 0;
            }

            if (File.Exists(bat))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = bat,
                    Arguments = "gui",
                    WorkingDirectory = root,
                    UseShellExecute = true
                });
                return 0;
            }

            MessageBox.Show(
                "Could not find CrackStack Codex's portable Python runtime or run.bat next to this launcher.",
                "CrackStack Codex",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "CrackStack Codex", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
