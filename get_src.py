#!/usr/bin/env python3
"""Get Vzlom key source files"""
import urllib.request, json, base64, sys

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

def get_file(path):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    if data.get("type") == "file":
        req2 = urllib.request.Request(data["download_url"], headers=headers)
        resp2 = urllib.request.urlopen(req2, timeout=10)
        content = resp2.read().decode()
        return content
    return str(data)[:200]

files = [
    "src/Vzlom/Faces/HermesFace.xaml.cs",
    "src/Vzlom/Core/ApiClient.cs",
    "src/Vzlom/Controls/SettingsDialog.xaml.cs",
    "src/Vzlom/Controls/SettingsDialog.xaml",
]

for f in files:
    print(f"{'='*60}")
    print(f"FILE: {f}")
    print(f"{'='*60}")
    content = get_file(f)
    print(content[:3000])
    if len(content) > 3000:
        print(f"\n... ({len(content)} total chars, showing first 3000)")
    print()
