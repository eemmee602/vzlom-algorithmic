using System.Windows;
using System.Windows.Controls;
using Vzlom.Core;

namespace Vzlom.Controls;

public partial class SettingsDialog : Window
{
    private readonly ApiClient _api;
    private readonly SshClient _ssh;
    private readonly List<KeyEntry> _keys = new();

    public SettingsDialog(ApiClient api, SshClient ssh)
    {
        InitializeComponent();
        _api = api;
        _ssh = ssh;

        LoadExisting();
    }

    private void LoadExisting()
    {
        // Clés existantes
        var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "api_keys.json");
        if (File.Exists(path))
        {
            try
            {
                var json = File.ReadAllText(path);
                var arr = Newtonsoft.Json.JsonConvert.DeserializeObject<string[]>(json);
                if (arr != null)
                {
                    foreach (var k in arr)
                    {
                        var masked = k.Length > 12 ? k[..12] + "..." + k[^4..] : k;
                        _keys.Add(new KeyEntry { Value = k, Display = masked });
                    }
                    KeyList.ItemsSource = null;
                    KeyList.ItemsSource = _keys;
                }
            }
            catch { }
        }

        // Config SSH
        var sshPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ssh_config.json");
        if (File.Exists(sshPath))
        {
            try
            {
                var cfg = Newtonsoft.Json.JsonConvert.DeserializeObject<SshConfig>(File.ReadAllText(sshPath));
                if (cfg != null)
                {
                    SshHost.Text = cfg.Host;
                    SshPort.Text = cfg.Port.ToString();
                    SshUser.Text = cfg.User;
                    SshPass.Text = cfg.Password ?? "";
                }
            }
            catch { }
        }
    }

    private void OnAddKey(object sender, RoutedEventArgs e)
    {
        var key = NewKeyBox.Text.Trim();
        if (string.IsNullOrEmpty(key) || key == "sk-or-v1-...") return;

        var masked = key.Length > 12 ? key[..12] + "..." + key[^4..] : key;
        _keys.Add(new KeyEntry { Value = key, Display = masked });
        KeyList.ItemsSource = null;
        KeyList.ItemsSource = _keys;
        NewKeyBox.Text = "";
        SaveKeys();
    }

    private void OnRemoveKey(object sender, RoutedEventArgs e)
    {
        if (KeyList.SelectedItem is KeyEntry entry)
        {
            _keys.Remove(entry);
            KeyList.ItemsSource = null;
            KeyList.ItemsSource = _keys;
            SaveKeys();
        }
    }

    private void SaveKeys()
    {
        var arr = _keys.Select(k => k.Value).ToArray();
        var json = Newtonsoft.Json.JsonConvert.SerializeObject(arr, Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "api_keys.json"), json);

        // Recharger dans l'API
        foreach (var k in arr)
            _api.AddApiKey(k);
    }

    private void OnSaveSsh(object sender, RoutedEventArgs e)
    {
        var cfg = new SshConfig
        {
            Host = SshHost.Text.Trim(),
            Port = int.TryParse(SshPort.Text.Trim(), out var p) ? p : 22,
            User = SshUser.Text.Trim(),
            Password = SshPass.Text.Trim(),
        };

        var json = Newtonsoft.Json.JsonConvert.SerializeObject(cfg, Newtonsoft.Json.Formatting.Indented);
        File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "ssh_config.json"), json);

        // Connecter immédiatement
        _ssh.Configure(cfg.Host, cfg.Port, cfg.User, cfg.Password ?? "", false);
        _ssh.Connect();

        MessageBox.Show($"SSH configuré et connecté à {cfg.Host}", "SSH", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void OnSaveModel(object sender, RoutedEventArgs e)
    {
        var model = ModelBox.Text.Trim();
        if (!string.IsNullOrEmpty(model))
            _api.SetModel(model);

        var fallbacks = FallbackBox.Text.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var fb in fallbacks)
            if (!string.IsNullOrEmpty(fb))
                _api.AddFallbackModel(fb);

        MessageBox.Show($"Modèle : {model}\nFallbacks : {fallbacks.Length}", "Modèle sauvegardé", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void OnClose(object sender, RoutedEventArgs e) => Close();
}

public class KeyEntry
{
    public string Value { get; set; } = "";
    public string Display { get; set; } = "";
}
