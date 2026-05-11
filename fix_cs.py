#!/usr/bin/env python3
"""Fix HermesFace.xaml.cs - add missing using for BitmapSource"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Faces/HermesFace.xaml.cs"

req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
sha = data["sha"]
content = base64.b64decode(data["content"]).decode()

# Add missing using
old = "using System.Windows.Media;\nusing Vzlom.Core;"
new = "using System.Windows.Media;\nusing System.Windows.Media.Imaging;\nusing Vzlom.Core;"
fixed = content.replace(old, new)

if content == fixed:
    print("❌ Pattern not found!")
    # Show first 10 lines
    for i, line in enumerate(content.split('\n')[:10], 1):
        print(f"  L{i}: {line}")
else:
    print("✅ Added using System.Windows.Media.Imaging")
    encoded = base64.b64encode(fixed.encode()).decode()
    payload = json.dumps({"message": "fix: add missing using for BitmapSource", "content": encoded, "sha": sha}).encode()
    req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
    resp = json.loads(urllib.request.urlopen(req2, timeout=20).read())
    print(f"PUSHED: {resp['commit']['sha'][:8]}")
