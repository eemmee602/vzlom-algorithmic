#!/usr/bin/env python3
"""Fix EditorFace.xaml line 27 font issue"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Faces/EditorFace.xaml"

# Get SHA
req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
sha = data["sha"]
current = base64.b64decode(data["content"]).decode()

# Find line 27
lines = current.split('\n')
for i in range(25, 30):
    if i < len(lines):
        print(f"  L{i}: {lines[i]}")

# Fix: replace single quotes around Consolas with proper XML quotes
# The issue is likely: FontFamily='Consolas' should be FontFamily="Consolas"
fixed = current.replace("FontFamily='Consolas'", 'FontFamily="Consolas"')
fixed = fixed.replace("FontFamily='Consolas'", 'FontFamily="Consolas"')

# Also check for any other single-quoted attributes
lines2 = fixed.split('\n')
for i in range(25, 30):
    if i < len(lines2):
        print(f"  L{i}': {lines2[i]}")

# Push
encoded = base64.b64encode(fixed.encode()).decode()
payload = json.dumps({"message": "fix: EditorFace.xaml FontFamily quote syntax", "content": encoded, "sha": sha}).encode()
req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
resp = json.loads(urllib.request.urlopen(req2, timeout=20).read())
print(f"PUSHED: {resp['commit']['sha'][:8]}")
