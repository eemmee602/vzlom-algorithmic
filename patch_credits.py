#!/usr/bin/env python3
"""Fix max_tokens in mobile HTML for free tier"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/mobile/index.html"

# Get current SHA
req = urllib.request.Request(url, headers=headers)
sha = json.loads(urllib.request.urlopen(req, timeout=10).read())["sha"]

# Read current file
req2 = urllib.request.Request(url + "?ref=main", headers=headers)
data = json.loads(urllib.request.urlopen(req2, timeout=10).read())
current = base64.b64decode(data["content"]).decode()

# Fix max_tokens: 8192 → 2048 (free tier)
fixed = current.replace("max_tokens:8192", "max_tokens:2048")
# Also fix the default model if needed (use cheaper model)
fixed = fixed.replace('"openai/gpt-4o"', '"google/gemini-2.0-flash-lite"')

count = fixed.count("max_tokens:2048")
print(f"Replaced max_tokens: {count} occurrences")

# Push
encoded = base64.b64encode(fixed.encode()).decode()
payload = json.dumps({"message": "fix: reduce max_tokens 8192→2048 for free tier, use gemini flash lite", "content": encoded, "sha": sha}).encode()
req3 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
resp = json.loads(urllib.request.urlopen(req3, timeout=20).read())
print(f"PUSHED: {resp['commit']['sha'][:8]}")

# Also update local
with open("/home/vzlom-bridge/mobile_index.html", "w") as f:
    f.write(fixed)
with open("/home/vzlom-bridge/mobile_v2.html", "w") as f:
    f.write(fixed)
print("Local updated")
