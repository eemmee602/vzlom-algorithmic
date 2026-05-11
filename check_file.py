#!/usr/bin/env python3
"""Verify actual content of MemoryManager.cs line 19 area"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Core/MemoryManager.cs"
req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
content = base64.b64decode(data["content"]).decode()

print(f"File: {data['size']} bytes, SHA: {data['sha'][:8]}")
print("--- First 25 lines ---")
for i, line in enumerate(content.split('\n')[:25], 1):
    print(f"{i:3d}|{line}")
