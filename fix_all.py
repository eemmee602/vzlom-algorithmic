#!/usr/bin/env python3
"""Mass fix all missing usings + missing MemoryDialog.xaml.cs"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
headers2 = {**headers, "Content-Type": "application/json"}

def get_file(path):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    return data["sha"], base64.b64decode(data["content"]).decode()

def push_file(path, content, sha, msg):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    encoded = base64.b64encode(content.encode()).decode()
    payload = json.dumps({"message": msg, "content": encoded, "sha": sha}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers2, method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return resp['commit']['sha'][:8]

def create_file(path, content, msg):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    encoded = base64.b64encode(content.encode()).decode()
    payload = json.dumps({"message": msg, "content": encoded}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers2, method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return resp['commit']['sha'][:8]

# 1. MemoryManager.cs - add using System.IO
sha, content = get_file("src/Vzlom/Core/MemoryManager.cs")
old = "using Vzlom.Models;"
new = "using System.IO;\nusing Vzlom.Models;"
content = content.replace(old, new)
push_file("src/Vzlom/Core/MemoryManager.cs", content, sha, "fix: add using System.IO")
print("✅ MemoryManager.cs")

# 2. SettingsDialog.xaml.cs - add using System.IO + using Vzlom.Faces
sha, content = get_file("src/Vzlom/Controls/SettingsDialog.xaml.cs")
old = "using Vzlom.Core;"
new = "using System.IO;\nusing Vzlom.Core;\nusing Vzlom.Faces;"
content = content.replace(old, new)
push_file("src/Vzlom/Controls/SettingsDialog.xaml.cs", content, sha, "fix: add missing usings (System.IO, Vzlom.Faces)")
print("✅ SettingsDialog.xaml.cs")

# 3. PermissionManager.cs - add using System.IO
sha, content = get_file("src/Vzlom/Core/PermissionManager.cs")
old = "using Vzlom.Models;"
new = "using System.IO;\nusing Vzlom.Models;"
content = content.replace(old, new)
push_file("src/Vzlom/Core/PermissionManager.cs", content, sha, "fix: add using System.IO")
print("✅ PermissionManager.cs")

# 4. ApiClient.cs - add using System.IO (for StreamReader)
sha, content = get_file("src/Vzlom/Core/ApiClient.cs")
old = "using System.Text.Json;\n\nnamespace Vzlom.Core;"
new = "using System.IO;\nusing System.Text.Json;\n\nnamespace Vzlom.Core;"
content = content.replace(old, new)
push_file("src/Vzlom/Core/ApiClient.cs", content, sha, "fix: add using System.IO for StreamReader")
print("✅ ApiClient.cs")

# 5. HermesFace.xaml.cs - add using System.IO
sha, content = get_file("src/Vzlom/Faces/HermesFace.xaml.cs")
old = "using Vzlom.Models;\n\nnamespace Vzlom.Faces;"
new = "using System.IO;\nusing Vzlom.Models;\n\nnamespace Vzlom.Faces;"
content = content.replace(old, new)
push_file("src/Vzlom/Faces/HermesFace.xaml.cs", content, sha, "fix: add using System.IO")
print("✅ HermesFace.xaml.cs")

# 6. Create MemoryDialog.xaml.cs (missing file!)
mem_dialog_cs = """using System.Windows;
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
"""
create_file("src/Vzlom/Controls/MemoryDialog.xaml.cs", mem_dialog_cs, "feat: create MemoryDialog.xaml.cs (was missing)")
print("✅ MemoryDialog.xaml.cs CREATED")
