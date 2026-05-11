#!/usr/bin/env python3
"""Search for Réflexion / thinking / status in Vzlom desktop code"""
import urllib.request, json, base64, re, sys

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

def get_github_file(path):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    if data.get("type") == "file":
        req2 = urllib.request.Request(data["download_url"], headers=headers)
        resp2 = urllib.request.urlopen(req2, timeout=10)
        return resp2.read().decode()
    return str(data)[:200]

# Check these files for status/reflexion patterns
files = [
    "src/Vzlom/Faces/HermesFace.xaml",
    "src/Vzlom/Controls/SettingsDialog.xaml.cs",
    "src/Vzlom/MainWindow.xaml",
    "src/Vzlom/MainWindow.xaml.cs",
    "src/Vzlom/Core/ApiClient.cs",
]

for path in files:
    content = get_github_file(path)
    print(f"\n{'='*60}")
    print(f"FILE: {path}")
    print(f"{'='*60}")
    for kw in ["Réflex", "réflex", "thinking", "--thinking", "Status", "status", "réflexion", "pense"]:
        for i, line in enumerate(content.split('\n'), 1):
            if kw.lower() in line.lower():
                print(f"  Line {i}: {line.strip()[:150]}")

# Also get the full HermesFace.xaml
print("\n\n=== FULL HermesFace.xaml ===")
print(get_github_file("src/Vzlom/Faces/HermesFace.xaml"))
