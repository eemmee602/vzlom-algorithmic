#!/usr/bin/env python3
"""Fix EditorFace.xaml - SyntaxHighlighting missing closing quote"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Faces/EditorFace.xaml"

# Get file
req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
sha = data["sha"]
content = base64.b64decode(data["content"]).decode()

# Fix: add closing quote to SyntaxHighlighting="C#"
# Line 26 in the file ends with "C#" without closing quote
old = 'SyntaxHighlighting="C#\n                                   FontFamily'
new = 'SyntaxHighlighting="C#"\n                                   FontFamily'
fixed = content.replace(old, new)

if content == fixed:
    print("❌ No change - pattern not found!")
    # Debug: show raw bytes around the issue
    lines = content.split('\n')
    for i in range(23, 30):
        print(f"L{i}: {repr(lines[i])}")
else:
    print("✅ Fixed SyntaxHighlighting quote")
    encoded = base64.b64encode(fixed.encode()).decode()
    payload = json.dumps({"message": "fix: missing closing quote on SyntaxHighlighting", "content": encoded, "sha": sha}).encode()
    req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
    resp = json.loads(urllib.request.urlopen(req2, timeout=20).read())
    print(f"PUSHED: {resp['commit']['sha'][:8]}")
