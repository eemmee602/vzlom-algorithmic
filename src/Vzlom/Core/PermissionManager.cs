using System.IO;
using Vzlom.Models;

namespace Vzlom.Core;

public class PermissionManager
{
    private readonly Dictionary<PermissionType, PermissionLevel> _persistent = new();
    private readonly Dictionary<PermissionType, PermissionLevel> _session = new();
    private bool _bypassMode = false;

    public bool BypassMode
    {
        get => _bypassMode;
        set { _bypassMode = value; OnBypassChanged?.Invoke(value); }
    }

    public event Action<bool>? OnBypassChanged;
    public event Action<PermissionRequest>? OnPermissionRequired;
    public event Action<string>? OnStatusMessage;

    public PermissionManager()
    {
        LoadPersistent();
    }

    public async Task<bool> RequestAsync(PermissionType type, string description)
    {
        if (_bypassMode) return true;

        // Vérifier persistent
        if (_persistent.TryGetValue(type, out var level))
        {
            if (level == PermissionLevel.AllowAlways) return true;
            if (level == PermissionLevel.Deny) return false;
        }

        // Vérifier session
        if (_session.TryGetValue(type, out var sLevel))
        {
            if (sLevel == PermissionLevel.AllowSession) return true;
            if (sLevel == PermissionLevel.Deny) return false;
        }

        // Demander à l'utilisateur
        var req = new PermissionRequest
        {
            Type = type,
            Description = description,
            Tcs = new TaskCompletionSource<PermissionLevel>()
        };

        OnPermissionRequired?.Invoke(req);
        var result = await req.Tcs.Task;

        switch (result)
        {
            case PermissionLevel.AllowAlways:
                _persistent[type] = PermissionLevel.AllowAlways;
                SavePersistent();
                return true;
            case PermissionLevel.AllowSession:
                _session[type] = PermissionLevel.AllowSession;
                OnStatusMessage?.Invoke($"✅ {description} — autorisé pour la session");
                return true;
            case PermissionLevel.AllowOnce:
                OnStatusMessage?.Invoke($"✅ {description} — autorisé une fois");
                return true;
            default:
                OnStatusMessage?.Invoke($"⛔ {description} — refusé");
                return false;
        }
    }

    private void LoadPersistent()
    {
        var path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "permissions.json");
        if (File.Exists(path))
        {
            try
            {
                var json = File.ReadAllText(path);
                var data = Newtonsoft.Json.JsonConvert.DeserializeObject<Dictionary<string, string>>(json);
                if (data != null)
                {
                    foreach (var kv in data)
                    {
                        if (Enum.TryParse<PermissionType>(kv.Key, out var type) && Enum.TryParse<PermissionLevel>(kv.Value, out var level))
                            _persistent[type] = level;
                    }
                }
            }
            catch { }
        }
    }

    private void SavePersistent()
    {
        try
        {
            var data = _persistent.ToDictionary(kv => kv.Key.ToString(), kv => kv.Value.ToString());
            var json = Newtonsoft.Json.JsonConvert.SerializeObject(data, Newtonsoft.Json.Formatting.Indented);
            File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "permissions.json"), json);
        }
        catch { }
    }

    public void ClearSession() => _session.Clear();
}

public class PermissionRequest
{
    public PermissionType Type { get; set; }
    public string Description { get; set; } = "";
    public TaskCompletionSource<PermissionLevel> Tcs { get; set; } = new();
}
