using System.Net.Http;
using System.Text;
using System.Text.Json;

namespace Vzlom.Core;

public class ApiClient
{
    private readonly HttpClient _http = new();
    private string? _apiKey;
    private string _model = "openai/gpt-4o"; // défaut

    public event Action<string>? OnStreamChunk;
    public event Action<string>? OnBashCommand;
    public event Action<string>? OnStatusChange;

    public void SetApiKey(string key) => _apiKey = key;
    public void SetModel(string model) => _model = model;

    public async Task SendMessageAsync(string message, List<object> history)
    {
        if (string.IsNullOrEmpty(_apiKey))
        {
            OnStatusChange?.Invoke("⚠️ Aucune clé API configurée");
            return;
        }

        OnStatusChange?.Invoke("🤔 Réflexion en cours...");

        var payload = new
        {
            model = _model,
            messages = history,
            stream = true,
            max_tokens = 4096
        };

        var json = JsonSerializer.Serialize(payload);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        try
        {
            var request = new HttpRequestMessage(HttpMethod.Post, "https://openrouter.ai/api/v1/chat/completions");
            request.Headers.Add("Authorization", $"Bearer {_apiKey}");
            request.Content = content;

            var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);

            if (!response.IsSuccessStatusCode)
            {
                OnStatusChange?.Invoke($"❌ Erreur API : {response.StatusCode}");
                return;
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
                        }
                    }
                }
                catch { }
            }

            OnStatusChange?.Invoke("✅ Terminé");
        }
        catch (Exception ex)
        {
            OnStatusChange?.Invoke($"❌ Erreur : {ex.Message}");
        }
    }
}
