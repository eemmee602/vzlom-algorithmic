using System.IO;
using System.Windows;
using System.Windows.Controls;
using Vzlom.Core;

namespace Vzlom.Controls;

public partial class MemoryDialog : Window
{
    private readonly MemoryManager _memory;

    public MemoryDialog(MemoryManager memory)
    {
        InitializeComponent();
        _memory = memory;
        Loaded += OnLoaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        var content = _memory.GetMemoryContext();
        MemoryContent.Text = content;
    }

    private void OnOpenFile(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog();
        if (dialog.ShowDialog() == true)
        {
            var text = File.ReadAllText(dialog.FileName);
            MemoryContent.Text = text;
        }
    }

    private void OnClear(object sender, RoutedEventArgs e)
    {
        _memory.Clear();
        MemoryContent.Text = "";
    }

    private void OnClose(object sender, RoutedEventArgs e)
    {
        _memory.SaveMemory("[Utilisateur] Fermeture mémoire", "system");
        Close();
    }
}

public class OpenFileDialog
{
    public string? FileName { get; set; }
    public bool ShowDialog()
    {
        var dialog = new Microsoft.Win32.OpenFileDialog();
        var result = dialog.ShowDialog();
        FileName = dialog.FileName;
        return result == true;
    }
}
