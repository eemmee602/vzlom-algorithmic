using System.Text.RegularExpressions;

namespace Vzlom.Core;

public class ScriptManager
{
    private readonly PermissionManager _perms;

    public ScriptManager(PermissionManager perms) => _perms = perms;

    public async Task<string?> ExtractCode(string message)
    {
        // Cherche ```lang ... ``` dans le message
        var match = Regex.Match(message, @"```(\w+)?\s*
(.*?)```", RegexOptions.Singleline);
        if (!match.Success) return null;

        var code = match.Groups[2].Value.Trim();
        var lang = match.Groups[1].Value.ToLower();

        if (string.IsNullOrEmpty(lang)) return code;

        if (!await _perms.RequestAsync(Models.PermissionType.ReadScript,
                $"Lire un script {lang.ToUpper()} ({code.Length} chars)"))
            return null;

        return code;
    }

    public async Task<bool> SaveCodeToEditor(string code, string filename)
    {
        if (!await _perms.RequestAsync(Models.PermissionType.WriteScript,
                $"Sauvegarder {filename} dans l'éditeur"))
            return false;

        OnScriptReady?.Invoke(code, filename);
        return true;
    }

    public event Action<string, string>? OnScriptReady; // code, filename
}
