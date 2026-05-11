#!/usr/bin/env python3
"""Push the fixed mobile HTML to GitHub"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/mobile/index.html"

# Get SHA
req = urllib.request.Request(url, headers=headers)
sha = json.loads(urllib.request.urlopen(req, timeout=10).read())["sha"]

with open("/home/vzlom-bridge/mobile_v2.html", "rb") as f:
    content = base64.b64encode(f.read()).decode()

payload = json.dumps({"message": "fix: login/register screens separate, no nesting, cleaner UI", "content": content, "sha": sha}).encode()
req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
resp2 = json.loads(urllib.request.urlopen(req2, timeout=20).read())
print(f"PUSHED: {resp2['commit']['sha'][:8]}")
