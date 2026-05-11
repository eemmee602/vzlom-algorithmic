#!/usr/bin/env python3
"""Get full HermesFace.xaml.cs and look for system prompt"""
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
        return resp2.read().decode()
    return str(data)[:200]

content = get_file("src/Vzlom/Faces/HermesFace.xaml.cs")
# Save to file for reading
with open("/home/vzlom-bridge/hermes_face_full.txt", "w") as f:
    f.write(content)
print(f"SAVED: {len(content)} chars")

# Search for system prompt keywords
import re
for kw in ["SYSTEM_PROMPT", "system_prompt", "system", "thinking", "réflexion", "--thinking", "--status", "RÈGLE"]:
    for i, line in enumerate(content.split('\n'), 1):
        if kw.lower() in line.lower():
            print(f"  Line {i}: {line.strip()[:120]}")
