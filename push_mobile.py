#!/usr/bin/env python3
"""Push new mobile/index.html to GitHub and local"""
import urllib.request, json, base64, re

TOKEN = "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"
headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
}

# Get current SHA
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/mobile/index.html"
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=10)
sha = json.loads(resp.read())["sha"]
print(f"Current SHA: {sha}")

# Read the new content from local file
with open("/home/vzlom-bridge/mobile_v2.html", "r") as f:
    new_content = f.read()

# Push to GitHub
encoded = base64.b64encode(new_content.encode()).decode()
payload = json.dumps({
    "message": "feat: login/register, per-user memory, auto-agent loop + visual effects (v2)",
    "content": encoded,
    "sha": sha,
}).encode()

req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
try:
    resp2 = urllib.request.urlopen(req2, timeout=20)
    result = json.loads(resp2.read())
    print(f"PUSHED OK: {result['commit']['sha']}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()

# Also update local
with open("/home/vzlom-bridge/mobile_index.html", "w") as f:
    f.write(new_content)
print("Local updated.")
