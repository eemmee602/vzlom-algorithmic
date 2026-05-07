using System.Net.Http;
using System.Text.Json;

namespace Vzlom.Core;

public class UpdateManager
{
    private readonly string _repoUrl = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/releases/latest";

    public async Task<UpdateInfo?> CheckAsync()
    {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Add("User-Agent", "Vzlom");

        try
        {
            var json = await http.GetStringAsync(_repoUrl);
            var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;

            return new UpdateInfo
            {
                Tag = root.GetProperty("tag_name").GetString() ?? "v0.0.0",
                Url = root.GetProperty("html_url").GetString() ?? "",
                Body = root.GetProperty("body").GetString() ?? "",
            };
        }
        catch { return null; }
    }
}

public class UpdateInfo
{
    public string Tag { get; set; } = "";
    public string Url { get; set; } = "";
    public string Body { get; set; } = "";
}
