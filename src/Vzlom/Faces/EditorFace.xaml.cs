using System.Windows;
using System.Windows.Controls;
using ICSharpCode.AvalonEdit;
using System.IO;

namespace Vzlom.Faces;

public partial class EditorFace : UserControl
{
    private string? _currentFile;

    public EditorFace()
    {
        InitializeComponent();
    }

    public void LoadCode(string code, string? filename = null)
    {
        Editor.Document.Text = code;
        _currentFile = filename;
        UpdateInfoBar();
    }

    public string GetCode() => Editor.Document.Text;

    private void OnOpen(object sender, RoutedEventArgs e)
    {
        var dialog = new Microsoft.Win32.OpenFileDialog
        {
            Filter = "Scripts Lua|*.lua|Tous|*.*",
            DefaultExt = ".lua"
        };

        if (dialog.ShowDialog() == true)
        {
            Editor.Document.Text = File.ReadAllText(dialog.FileName);
            _currentFile = dialog.FileName;
            UpdateInfoBar();
        }
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        if (_currentFile != null)
        {
            File.WriteAllText(_currentFile, Editor.Document.Text);
            UpdateInfoBar();
        }
        else
        {
            var dialog = new Microsoft.Win32.SaveFileDialog
            {
                Filter = "Scripts Lua|*.lua|Tous|*.*",
                DefaultExt = ".lua"
            };

            if (dialog.ShowDialog() == true)
            {
                File.WriteAllText(dialog.FileName, Editor.Document.Text);
                _currentFile = dialog.FileName;
                UpdateInfoBar();
            }
        }
    }

    private void OnRun(object sender, RoutedEventArgs e)
    {
        // Placeholder pour exécution Solara/externe
        InfoBar.Text = "▶ Exécution... (intégration Solara à venir)";
    }

    private void OnClear(object sender, RoutedEventArgs e)
    {
        Editor.Document.Text = "";
        _currentFile = null;
        InfoBar.Text = "Éditeur vidé";
    }

    private void UpdateInfoBar()
    {
        var lines = Editor.Document.LineCount;
        var chars = Editor.Document.TextLength;
        var file = _currentFile != null ? Path.GetFileName(_currentFile) : "non-sauvegardé";
        InfoBar.Text = $"{file} · {lines} lignes · {chars} chars";
    }
}
