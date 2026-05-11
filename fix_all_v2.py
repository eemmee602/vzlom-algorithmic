#!/usr/bin/env python3
"""FIX ALL remaining using issues - correctly this time"""
import urllib.request, json, base64

TOKEN = "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"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

def get(path):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/{path}"
    req = urllib.request.Request(url, headers=H)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return data["sha"], base64.b64decode(data["content"]).decode()

def push(path, content, sha, msg):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/{path}"
    payload = json.dumps({"message": msg, "content": base64.b64encode(content.encode()).decode(), "sha": sha}).encode()
    req = urllib.request.Request(url, data=payload, headers=H, method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return resp['commit']['sha'][:8]

# ── 1. MemoryManager.cs ── uses File, Path, FileInfo → needs using System.IO
sha, c = get("Core/MemoryManager.cs")
c = c.replace("using System.Text;", "using System.IO;\nusing System.Text;")
push("Core/MemoryManager.cs", c, sha, "fix: add using System.IO (for File, Path, FileInfo)")
print("✅ MemoryManager.cs")

# ── 2. MemoryDialog.xaml.cs ── uses File → needs using System.IO
sha, c = get("Controls/MemoryDialog.xaml.cs")
c = c.replace("using System.Windows;", "using System.IO;\nusing System.Windows;")
push("Controls/MemoryDialog.xaml.cs", c, sha, "fix: add using System.IO (for File.ReadAllText)")
print("✅ MemoryDialog.xaml.cs")

# ── 3. SettingsDialog.xaml.cs ── uses File, Path, SshConfig
sha, c = get("Controls/SettingsDialog.xaml.cs")
# Replace the first lines - add usings after the existing ones
old = """using System.Windows.Controls;
using Vzlom.Core;"""
new = """using System.Windows.Controls;
using System.IO;
using Vzlom.Core;
using Vzlom.Faces;"""
c = c.replace(old, new)
push("Controls/SettingsDialog.xaml.cs", c, sha, "fix: add using System.IO and Vzlom.Faces (for SshConfig)")
print("✅ SettingsDialog.xaml.cs")

# ── 4. PermissionManager.cs ── uses File, Path
sha, c = get("Core/PermissionManager.cs")
old = "using Vzlom.Models;"
new = "using System.IO;\nusing Vzlom.Models;"
if old in c:
    c = c.replace(old, new)
else:
    # Check first lines
    lines = c.split('\n')
    print(f"  PermissionManager.cs starts: {lines[0]}, {lines[1]}, {lines[2]}")
    # Try another approach
    c = c.replace("using Vzlom.Core;", "using System.IO;\nusing Vzlom.Core;")
push("Core/PermissionManager.cs", c, sha, "fix: add using System.IO (for File, Path)")
print("✅ PermissionManager.cs")

# ── 5. ApiClient.cs ── uses StreamReader → needs using System.IO
sha, c = get("Core/ApiClient.cs")
old = """using System.Net.Http;
using System.Text;
using System.Text.Json;"""
new = """using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;"""
c = c.replace(old, new)
push("Core/ApiClient.cs", c, sha, "fix: add using System.IO (for StreamReader)")
print("✅ ApiClient.cs")

# ── 6. HermesFace.xaml.cs ── uses File, Path twice
sha, c = get("Faces/HermesFace.xaml.cs")
old = """using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Vzlom.Core;"""
new = """using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.IO;
using Vzlom.Core;"""
c = c.replace(old, new)
push("Faces/HermesFace.xaml.cs", c, sha, "fix: add using System.IO (for File, Path)")
print("✅ HermesFace.xaml.cs")

print("\n=== ALL FIXES PUSHED ===")
