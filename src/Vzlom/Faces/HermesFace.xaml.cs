using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Vzlom.Core;
using Vzlom.Models;

namespace Vzlom.Faces;

public partial class HermesFace : UserControl
{
    private readonly ApiClient _api = new();
    private readonly SshClient _ssh = new();
    private readonly PermissionManager _perms;
    private readonly ScriptManager _scriptMgr;
    private readonly List<object> _history = new();
    private BitmapSource? _pendingImage;
    private Border? _streamingBorder;
    private TextBlock? _streamingBlock;

    public HermesFace(PermissionManager perms, ScriptManager scriptMgr)
    {
        InitializeComponent();
        _perms = perms;
        _scriptMgr = scriptMgr;

        // API events
        _api.OnStreamChunk += OnStreamChunk;
        _api.OnBashCommand += OnBashCommand;
        _api.OnStatusChange += OnStatusChange;

        // SSH events
        _ssh.OnCommandResult += OnCommandResult;
        _ssh.OnStatus += OnStatusChange;

        AddSystemMessage("🤖 Hermès prêt. Envoie un message ou configure SSH/API dans ⚙.");
        LoadSavedKeys();
    }

    // ─── Messages ───

    private void AddSystemMessage(string text) => AddMessage(text, MessageRole.System);

    private void AddMessage(string text, MessageRole role, bool isBashOutput = false)
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
                    MessageRole.Bash => new SolidColorBrush(Color.FromRgb(25, 22, 15)),
                    MessageRole.Status => new SolidColorBrush(Color.FromRgb(20, 30, 20)),
                    _ => new SolidColorBrush(Color.FromRgb(26, 26, 46)),
                }
            };

            var stack = new StackPanel();

            // En-tête bash
            if (role == MessageRole.Bash && !isBashOutput)
            {
                stack.Children.Add(new TextBlock
                {
                    Text = "┌─ bash ───────────────────────────┐",
                    Foreground = new SolidColorBrush(Color.FromRgb(255, 185, 15)),
                    FontSize = 10,
                    FontFamily = new FontFamily("Consolas"),
                    Margin = new Thickness(0, 0, 0, 4),
                });
            }

            var tb = new TextBlock
            {
                Text = text,
                Foreground = role switch
                {
                    MessageRole.Bash when isBashOutput => new SolidColorBrush(Color.FromRgb(180, 220, 180)),
                    MessageRole.Bash => new SolidColorBrush(Color.FromRgb(255, 185, 15)),
                    _ => new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                },
                FontSize = 13,
                FontFamily = new FontFamily("Consolas"),
                TextWrapping = TextWrapping.Wrap,
            };
            stack.Children.Add(tb);

            // Pied bash
            if (role == MessageRole.Bash && !isBashOutput)
            {
                stack.Children.Add(new TextBlock
                {
                    Text = "└───────────────────────────────────┘",
                    Foreground = new SolidColorBrush(Color.FromRgb(255, 185, 15)),
                    FontSize = 10,
                    FontFamily = new FontFamily("Consolas"),
                    Margin = new Thickness(0, 4, 0, 0),
                });
            }

            border.Child = stack;
            ChatPanel.Children.Add(border);
            ChatScroll.ScrollToBottom();
        });
    }

    // ─── Streaming ───
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
            ChatScroll.ScrollToBottom();
        });
    }

    private void OnBashCommand(string cmd) => AddMessage(cmd, MessageRole.Bash);

    private void OnCommandResult(string output, bool isError)
    {
        AddMessage(output, MessageRole.Bash, isBashOutput: true);
    }

    private void OnStatusChange(string status)
    {
        Dispatcher.Invoke(() =>
        {
            StatusLabel.Text = status;
            StatusIcon.Foreground = status.Contains("❌")
                ? new SolidColorBrush(Color.FromRgb(255, 68, 68))
                : status.Contains("✅") || status.Contains("🔗")
                    ? new SolidColorBrush(Color.FromRgb(0, 255, 136))
                    : new SolidColorBrush(Color.FromRgb(0, 212, 255));
        });
    }

    // ─── Envoi message ───
    private async void OnSend(object sender, RoutedEventArgs e)
    {
        var text = InputBox.Text.Trim();
        if (string.IsNullOrEmpty(text) && _pendingImage == null) return;

        AddMessage(text, MessageRole.User);
        _history.Add(new { role = "user", content = text });

        _streamingBlock = null;
        _streamingBorder = null;

        // Extraire code potentiel
        var extracted = await _scriptMgr.ExtractCode(text);
        if (extracted != null)
            AddSystemMessage($"📄 Script détecté ({extracted.Length} chars)");

        // Envoyer à l'API avec SSH context
        await _api.SendMessageAsync(text, _history, _ssh.IsConnected ? _ssh : null);

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

    // ─── Image ───
    private void OnPasteImage(object sender, RoutedEventArgs e)
    {
        if (Clipboard.ContainsImage())
        {
            _pendingImage = Clipboard.GetImage();
            ImageName.Text = $"Image ({_pendingImage.PixelWidth}x{_pendingImage.PixelHeight})";
            ImagePreviewPanel.Visibility = Visibility.Visible;
        }
    }
    private void OnRemoveImage(object sender, RoutedEventArgs e)
    {
        _pendingImage = null;
        ImagePreviewPanel.Visibility = Visibility.Collapsed;
    }

    // ─── SSH ───
    private void OnToggleSsh(object sender, RoutedEventArgs e)
    {
        if (_ssh.IsConnected)
        {
            _ssh.Disconnect();
            SshIndicator.Text = "";
            BtnSsh.Background = Brushes.Transparent;
            return;
        }

        // Charger config depuis fichier
        var cfgPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ssh_config.json");
        if (File.Exists(cfgPath))
        {
            try
            {
                var json = File.ReadAllText(cfgPath);
                var cfg = Newtonsoft.Json.JsonConvert.DeserializeObject<SshConfig>(json);
                if (cfg != null)
                {
                    _ssh.Configure(cfg.Host, cfg.Port, cfg.User, cfg.Password ?? cfg.KeyPath ?? "", !string.IsNullOrEmpty(cfg.KeyPath));
                    if (_ssh.Connect())
                    {
                        SshIndicator.Text = $"🔗 {cfg.Host}";
                        BtnSsh.Background = new SolidColorBrush(Color.FromRgb(0, 100, 60));
                        AddSystemMessage($"🔗 SSH connecté → {cfg.User}@{cfg.Host}:{cfg.Port}");
                    }
                    return;
                }
            }
            catch { }
        }

        AddSystemMessage("⚠️ Aucune config SSH trouvée. Mets tes identifiants dans ⚙ > SSH Config");
    }

    // ─── Bypass toggle ───
    private void OnToggleBypass(object sender, RoutedEventArgs e)
    {
        _perms.BypassMode = !_perms.BypassMode;
        BtnBypass.Background = _perms.BypassMode
            ? new SolidColorBrush(Color.FromRgb(200, 80, 0))
            : Brushes.Transparent;
        AddSystemMessage(_perms.BypassMode ? "⚡ Mode BYPASS activé" : "🔒 Mode permissions normal");
    }

    // ─── Settings ───
    private void OnSettings(object sender, RoutedEventArgs e)
    {
        var dialog = new Controls.SettingsDialog(_api, _ssh);
        dialog.Owner = Window.GetWindow(this);
        dialog.ShowDialog();
    }

    // ─── API Keys persistées ───
    private void LoadSavedKeys()
    {
        var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "api_keys.json");
        if (File.Exists(path))
        {
            try
            {
                var json = File.ReadAllText(path);
                var keys = Newtonsoft.Json.JsonConvert.DeserializeObject<string[]>(json);
                if (keys != null)
                    foreach (var k in keys)
                        if (!string.IsNullOrEmpty(k))
                            _api.AddApiKey(k);
            }
            catch { }
        }
    }
}

public class SshConfig
{
    public string Host { get; set; } = "";
    public int Port { get; set; } = 22;
    public string User { get; set; } = "";
    public string? Password { get; set; }
    public string? KeyPath { get; set; }
}
