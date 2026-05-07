using System.Windows;
using System.Windows.Input;
using Vzlom.Faces;
using Vzlom.Core;

namespace Vzlom;

public partial class MainWindow : Window
{
    private bool _isPinned = false;
    private bool _isMaximized = false;
    private EditorFace? _editorFace;
    private HermesFace? _hermesFace;
    public PermissionManager PermManager { get; } = new();
    public ScriptManager ScriptMgr { get; }

    public MainWindow()
    {
        InitializeComponent();
        ScriptMgr = new ScriptManager(PermManager);

        PermManager.OnBypassChanged += OnBypassChanged;
        PermManager.OnStatusMessage += msg => Dispatcher.Invoke(() => StatusText.Text = msg);

        _editorFace = new EditorFace();
        _hermesFace = new HermesFace(PermManager, ScriptMgr);

        PageContainer.Content = _editorFace;
        BtnEditor.Background = System.Windows.Media.Brushes.DarkCyan;

        // Permettre au ScriptManager de passer du code à l'éditeur
        ScriptMgr.OnScriptReady += (code, name) =>
        {
            Dispatcher.Invoke(() =>
            {
                SwitchToEditor();
                _editorFace?.LoadCode(code, name);
                StatusText.Text = $"✅ Script chargé : {name}";
            });
        };
    }

    // ─── Gestion fenêtre ───
    private void OnTitleBarDrag(object sender, MouseButtonEventArgs e)
    {
        if (e.ChangedButton == MouseButton.Left)
        {
            if (_isMaximized)
            {
                _isMaximized = false;
                WindowState = WindowState.Normal;
                BtnMax.Content = "□";
            }
            DragMove();
        }
    }

    private void OnPin(object sender, RoutedEventArgs e)
    {
        _isPinned = !_isPinned;
        Topmost = _isPinned;
        BtnPin.Background = _isPinned
            ? System.Windows.Media.Brushes.DarkCyan
            : System.Windows.Media.Brushes.Transparent;
        StatusText.Text = _isPinned ? "📌 Toujours au-dessus" : "📌 Désépinglé";
    }

    private void OnMinimize(object sender, RoutedEventArgs e)
        => WindowState = WindowState.Minimized;

    private void OnMaximize(object sender, RoutedEventArgs e)
    {
        _isMaximized = !_isMaximized;
        WindowState = _isMaximized ? WindowState.Maximized : WindowState.Normal;
        BtnMax.Content = _isMaximized ? "❐" : "□";
    }

    private void OnClose(object sender, RoutedEventArgs e) => Close();

    // ─── Navigation faces ───
    private void OnSwitchEditor(object sender, RoutedEventArgs e) => SwitchToEditor();
    private void OnSwitchHermes(object sender, RoutedEventArgs e) => SwitchToHermes();

    private void SwitchToEditor()
    {
        PageContainer.Content = _editorFace;
        BtnEditor.Background = System.Windows.Media.Brushes.DarkCyan;
        BtnHermes.Background = System.Windows.Media.Brushes.Transparent;
        StatusText.Text = "📝 Éditeur";
    }

    private void SwitchToHermes()
    {
        PageContainer.Content = _hermesFace;
        BtnHermes.Background = System.Windows.Media.Brushes.DarkCyan;
        BtnEditor.Background = System.Windows.Media.Brushes.Transparent;
        StatusText.Text = "🤖 Hermes";
    }

    private void OnBypassChanged(bool bypass)
    {
        Dispatcher.Invoke(() =>
        {
            BypassIndicator.Text = bypass ? "⚡ BYPASS" : "";
            StatusText.Text = bypass ? "⚡ Mode bypass activé" : "Prêt";
        });
    }
}
