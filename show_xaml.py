#!/usr/bin/env python3
"""Get EditorFace.xaml full content and find the exact issue"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Faces/EditorFace.xaml"
req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
content = base64.b64decode(data["content"]).decode()

# Print ALL lines with their content hex for inspection
for i, line in enumerate(content.split('\n'), 1):
    print(f"{i:3d}|{line}")
