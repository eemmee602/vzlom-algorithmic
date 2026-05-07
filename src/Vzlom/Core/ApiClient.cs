using System.Net.Http;
using System.Text;
using System.Text.Json;

namespace Vzlom.Core;

public class ApiClient : IDisposable
{
    private readonly HttpClient _http = new();
    private readonly List<string> _apiKeys = new();
    private int _currentKeyIndex = 0;
    private string _model = "openai/gpt-4o";
    private string _baseUrl = "https://openrouter.ai/api/v1/chat/completions";
    private readonly List<string> _fallbackModels = new();

    public event Action<string>? OnStreamChunk;
    public event Action<string>? OnBashCommand;
    public event Action<string>? OnStatusChange;

    public void AddApiKey(string key) => _apiKeys.Add(key);

    public void SetModel(string model) => _model = model;
    public void SetBaseUrl(string url) => _baseUrl = url;

    public void AddFallbackModel(string model) => _fallbackModels.Add(model);

    public async Task SendMessageAsync(string message, List<object> history, SshClient? ssh = null)
    {
        if (_apiKeys.Count == 0)
        {
            OnStatusChange?.Invoke("⚠️ Aucune clé API configurée. Menu > Paramètres API");
            return;
        }

        int attempts = 0;
        int maxAttempts = Math.Max(_apiKeys.Count, 1) + _fallbackModels.Count;
        string? lastError = null;

        while (attempts <= maxAttempts)
        {
            var currentKey = _apiKeys[_currentKeyIndex % _apiKeys.Count];
            var currentModel = attempts < 1 ? _model
                            : _fallbackModels.Count > attempts - 1 ? _fallbackModels[attempts - 1]
                            : _model;

            try
            {
                if (attempts > 0)
                    OnStatusChange?.Invoke($"🔄 Bascule auto → {currentModel} (key {(_currentKeyIndex % _apiKeys.Count) + 1})");

                await SendWithKey(currentKey, currentModel, message, history, ssh);
                return; // Succès
            }
            catch (Exception ex)
            {
                lastError = ex.Message;
                OnStatusChange?.Invoke($"⚠️ Échec {currentModel} : {ex.Message}");
                _currentKeyIndex = (_currentKeyIndex + 1) % _apiKeys.Count;
                attempts++;
            }
        }

        OnStatusChange?.Invoke($"❌ Tous les providers ont échoué. Dernière erreur : {lastError}");
    }

    private async Task SendWithKey(string key, string model, string message, List<object> history, SshClient? ssh)
    {
        var payload = new
        {
            model,
            messages = history,
            stream = true,
            max_tokens = 8192
        };

        var json = JsonSerializer.Serialize(payload);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        var request = new HttpRequestMessage(HttpMethod.Post, _baseUrl);
        request.Headers.Add("Authorization", $"Bearer {key}");
        request.Headers.Add("HTTP-Referer", "https://github.com/eemmee602/vzlom-algorithmic");
        request.Headers.Add("X-Title", "Vzlom Algorithmic");
        request.Content = content;

        OnStatusChange?.Invoke($"🤖 {model} en cours...");
        var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);

        if (!response.IsSuccessStatusCode)
        {
            var errBody = await response.Content.ReadAsStringAsync();
            throw new Exception($"HTTP {(int)response.StatusCode}: {errBody[..Math.Min(errBody.Length, 200)]}");
        }

        using var stream = await response.Content.ReadAsStreamAsync();
        using var reader = new StreamReader(stream);

        string? fullResponse = null;
        while (!reader.EndOfStream)
        {
            var line = await reader.ReadLineAsync();
            if (string.IsNullOrEmpty(line)) continue;
            if (!line.StartsWith("data: ")) continue;

            var data = line[6..];
            if (data == "[DONE]") break;

            try
            {
                using var doc = JsonDocument.Parse(data);
                var root = doc.RootElement;
                var choices = root.GetProperty("choices");
                if (choices.ValueKind == JsonValueKind.Array && choices.GetArrayLength() > 0)
                {
                    var delta = choices[0].GetProperty("delta");
                    if (delta.TryGetProperty("content", out var contentProp))
                    {
                        var text = contentProp.GetString() ?? "";
                        fullResponse += text;
                        OnStreamChunk?.Invoke(text);

                        // Détecter commandes bash inline
                        if (text.Contains("--bash--") || text.Contains("`$ "))
                        {
                            var cmd = ExtractBashCommand(fullResponse ?? text);
                            if (cmd != null && ssh != null && ssh.IsConnected)
                            {
                                OnBashCommand?.Invoke(cmd);
                                var result = ssh.Execute(cmd, 60);
                                OnStatusChange?.Invoke($"✅ bash $ {cmd} terminé ({result.Length} chars)");
                            }
                        }
                    }
                }
            }
            catch { }
        }

        OnStatusChange?.Invoke("✅ Terminé");
    }

    private string? ExtractBashCommand(string text)
    {
        // Format: --bash-- ls -la
        var idx = text.IndexOf("--bash--");
        if (idx >= 0)
        {
            var after = text[(idx + 8)..].Trim();
            var end = after.IndexOfAny(new[] { '\n', '\r', '\t' });
            return end >= 0 ? after[..end].Trim() : after;
        }

        // Format: ```bash\n...\n```
        var match = System.Text.RegularExpressions.Regex.Match(text, @"```bash\s*\n(.*?)```", System.Text.RegularExpressions.RegexOptions.Singleline);
        if (match.Success)
            return match.Groups[1].Value.Trim();

        return null;
    }

    public void Dispose() => _http.Dispose();
}
