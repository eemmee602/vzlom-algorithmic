using System.Diagnostics;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace Vzlom.Faces;

public partial class PowerShellFace : UserControl
{
    private Process? _currentProcess;
    private readonly StringBuilder _outputBuffer = new();

    public PowerShellFace()
    {
        InitializeComponent();
        OutputBox.Text = @"💻 Vzlom PowerShell Terminal
═══════════════════════════════════
Tape une commande ci-dessous et presse Enter.
Utilise les boutons du haut pour des commandes rapides.
";
    }

    // ─── Execute ───
    private void OnExecute(object sender, RoutedEventArgs e) => RunCommand(InputBox.Text);

    private void OnInputKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            e.Handled = true;
            RunCommand(InputBox.Text);
        }
    }

    private void OnQuickCommand(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string cmd)
        {
            InputBox.Text = cmd;
            RunCommand(cmd);
        }
    }

    private void OnClear(object sender, RoutedEventArgs e)
    {
        OutputBox.Text = "";
        _outputBuffer.Clear();
    }

    private void OnKillProcess(object sender, RoutedEventArgs e)
    {
        if (_currentProcess != null && !_currentProcess.HasExited)
        {
            try
            {
                _currentProcess.Kill(entireProcessTree: true);
                AppendOutput("\n🛑 Processus tué.\n");
            }
            catch (Exception ex)
            {
                AppendOutput($"\n❌ Erreur kill: {ex.Message}\n");
            }
        }
        else
        {
            AppendOutput("\n⚠️ Aucun processus en cours.\n");
        }
    }

    private async void RunCommand(string command)
    {
        if (string.IsNullOrWhiteSpace(command)) return;

        AppendOutput($"\nPS> {command}\n");

        try
        {
            _currentProcess = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{command}\"",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8
                },
                EnableRaisingEvents = true
            };

            _currentProcess.OutputDataReceived += (s, e) =>
            {
                if (e.Data != null)
                    Dispatcher.Invoke(() => AppendOutput(e.Data + "\n"));
            };

            _currentProcess.ErrorDataReceived += (s, e) =>
            {
                if (e.Data != null)
                    Dispatcher.Invoke(() => AppendError(e.Data + "\n"));
            };

            _currentProcess.Start();
            _currentProcess.BeginOutputReadLine();
            _currentProcess.BeginErrorReadLine();

            await Task.Run(() => _currentProcess.WaitForExit(60000));

            var exitCode = _currentProcess.ExitCode;
            if (exitCode != 0)
                AppendOutput($"\n[Processus terminé avec code: {exitCode}]\n");
            else
                AppendOutput("\n[OK]\n");
        }
        catch (Exception ex)
        {
            AppendOutput($"\n❌ Erreur: {ex.Message}\n");
        }
        finally
        {
            InputBox.Text = "";
            InputBox.Focus();
            _currentProcess = null;
        }
    }

    private void AppendOutput(string text)
    {
        _outputBuffer.Append(text);
        OutputBox.Text = _outputBuffer.ToString();
        OutputBox.CaretIndex = OutputBox.Text.Length;
        OutputScroll.ScrollToBottom();
    }

    private void AppendError(string text)
    {
        // Store error in red-like color marker
        _outputBuffer.Append(text);
        OutputBox.Text = _outputBuffer.ToString();
        OutputBox.CaretIndex = OutputBox.Text.Length;
        OutputScroll.ScrollToBottom();
    }
}
