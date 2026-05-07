using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Vzlom.Core;
using Vzlom.Models;

namespace Vzlom.Faces;

public partial class HermesFace : UserControl
{
    private readonly ApiClient _api = new();
    private readonly PermissionManager _perms;
    private readonly ScriptManager _scriptMgr;
    private readonly List<object> _history = new();
    private BitmapSource? _pendingImage;
    private int _msgCount = 0;

    public HermesFace(PermissionManager perms, ScriptManager scriptMgr)
    {
        InitializeComponent();
        _perms = perms;
        _scriptMgr = scriptMgr;

        _api.OnStreamChunk += OnStreamChunk;
        _api.OnBashCommand += OnBashCommand;
        _api.OnStatusChange += OnStatusChange;

        AddSystemMessage("🤖 Hermès prêt. Envoie ton message.");
    }

    private void AddSystemMessage(string text)
    {
        AddMessage(text, MessageRole.System);
    }

    private void AddMessage(string text, MessageRole role)
    {
        Dispatcher.Invoke(() =>
        {
            var border = new Border
            {
                Margin = new Thickness(0, 0, 0, 6),
                Padding = new Thickness(10, 6, 10, 6),
                CornerRadius = new CornerRadius(6),
                Background = role switch
                {
                    MessageRole.User => new SolidColorBrush(Color.FromRgb(15, 52, 96)),
                    MessageRole.Bash => new SolidColorBrush(Color.FromRgb(30, 30, 20)),
                    MessageRole.Status => new SolidColorBrush(Color.FromRgb(20, 30, 20)),
                    MessageRole.System => new SolidColorBrush(Color.FromRgb(26, 26, 46)),
                    _ => new SolidColorBrush(Color.FromRgb(22, 22, 36)),
                }
            };

            var stack = new StackPanel();

            // Label de rôle
            if (role == MessageRole.Bash)
            {
                var label = new TextBlock
                {
                    Text = "┌─ bash ─────────────────────────────┐",
                    Foreground = new SolidColorBrush(Color.FromRgb(255, 170, 0)),
                    FontSize = 11,
                    FontFamily = new FontFamily("Consolas"),
                };
                stack.Children.Add(label);
            }

            var tb = new TextBlock
            {
                Text = text,
                Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                FontSize = 13,
                FontFamily = new FontFamily("Consolas"),
                TextWrapping = TextWrapping.Wrap,
            };
            stack.Children.Add(tb);

            if (role == MessageRole.Bash)
            {
                var label = new TextBlock
                {
                    Text = "└─────────────────────────────────────┘",
                    Foreground = new SolidColorBrush(Color.FromRgb(255, 170, 0)),
                    FontSize = 11,
                    FontFamily = new FontFamily("Consolas"),
                };
                stack.Children.Add(label);
            }

            border.Child = stack;
            ChatPanel.Children.Add(border);
            ChatScroll.ScrollToBottom();
        });
    }

    private Border? _streamingBorder;
    private TextBlock? _streamingBlock;
    private string _currentBuffer = "";

    private void OnStreamChunk(string chunk)
    {
        Dispatcher.Invoke(() =>
        {
            if (_streamingBlock == null)
            {
                _streamingBorder = new Border
                {
                    Margin = new Thickness(0, 0, 0, 6),
                    Padding = new Thickness(10, 6, 10, 6),
                    CornerRadius = new CornerRadius(6),
                    Background = new SolidColorBrush(Color.FromRgb(22, 22, 36)),
                };
                _streamingBlock = new TextBlock
                {
                    Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                    FontSize = 13,
                    FontFamily = new FontFamily("Consolas"),
                    TextWrapping = TextWrapping.Wrap,
                };
                _streamingBorder.Child = _streamingBlock;
                ChatPanel.Children.Add(_streamingBorder);
            }

            _streamingBlock.Text += chunk;
            _currentBuffer += chunk;
            ChatScroll.ScrollToBottom();
        });
    }

    private void OnBashCommand(string cmd)
    {
        AddMessage($">{cmd}", MessageRole.Bash);
    }

    private void OnStatusChange(string status)
    {
        Dispatcher.Invoke(() =>
        {
            StatusLabel.Text = status;
            StatusIcon.Foreground = status.Contains("❌")
                ? new SolidColorBrush(Color.FromRgb(255, 68, 68))
                : status.Contains("✅")
                    ? new SolidColorBrush(Color.FromRgb(0, 255, 136))
                    : new SolidColorBrush(Color.FromRgb(0, 212, 255));
        });
    }

    private async void OnSend(object sender, RoutedEventArgs e)
    {
        var text = InputBox.Text.Trim();
        if (string.IsNullOrEmpty(text) && _pendingImage == null) return;

        AddMessage(text, MessageRole.User);
        _history.Add(new { role = "user", content = text });

        // Si image, ajouter au message
        _streamingBlock = null;
        _streamingBorder = null;
        _currentBuffer = "";

        // Extraire code potentiel
        var extracted = await _scriptMgr.ExtractCode(text);
        if (extracted != null)
        {
            AddMessage($"📄 Script détecté ({extracted.Length} chars)", MessageRole.Status);
        }

        InputBox.Text = "";
    }

    private void OnInputKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && !Keyboard.IsKeyDown(Key.LeftCtrl) && !Keyboard.IsKeyDown(Key.RightCtrl))
        {
            e.Handled = true;
            OnSend(sender, e);
        }
    }

    private void OnPasteImage(object sender, RoutedEventArgs e)
    {
        if (Clipboard.ContainsImage())
        {
            _pendingImage = Clipboard.GetImage();
            ImageName.Text = $"Image presse-papier ({_pendingImage.PixelWidth}x{_pendingImage.PixelHeight})";
            ImagePreviewPanel.Visibility = Visibility.Visible;
        }
    }

    private void OnRemoveImage(object sender, RoutedEventArgs e)
    {
        _pendingImage = null;
        ImagePreviewPanel.Visibility = Visibility.Collapsed;
    }

    private void OnToggleBypass(object sender, RoutedEventArgs e)
    {
        _perms.BypassMode = !_perms.BypassMode;
        BtnBypass.Background = _perms.BypassMode
            ? new SolidColorBrush(Color.FromRgb(255, 100, 0))
            : System.Windows.Media.Brushes.Transparent;
    }
}
