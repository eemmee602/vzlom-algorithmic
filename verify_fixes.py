#!/usr/bin/env python3
"""Verify fixes are on GitHub"""
import urllib.request, json, base64

TOKEN = "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"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

files = [
    "Core/MemoryManager.cs",
    "Controls/MemoryDialog.xaml.cs",
    "Controls/SettingsDialog.xaml.cs",
    "Core/ApiClient.cs",
    "Faces/HermesFace.xaml.cs",
    "Core/PermissionManager.cs",
]

for f in files:
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/{f}"
    req = urllib.request.Request(url, headers=H)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    content = base64.b64decode(data["content"]).decode()
    has_io = "System.IO" in content
    print(f"{'✅' if has_io else '❌'} {f} → {'using System.IO; present' if has_io else 'MISSING!'}")
