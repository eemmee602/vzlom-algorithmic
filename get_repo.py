#!/usr/bin/env python3
"""Get Vzlom repo structure and system prompt"""
import urllib.request, json, base64, sys

TOKEN = "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"
REPO = "eemmee602/vzlom-algorithmic"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Get root contents
req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contents", headers=headers)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    items = json.loads(resp.read())
    for item in items:
        print(f"{item['name']} ({item['type']})")
except Exception as e:
    print(f"ROOT ERROR: {e}")

# Try to find system prompt in source files
# Look at src structure
print("\n=== src/ contents ===")
req2 = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contents/src", headers=headers)
try:
    resp2 = urllib.request.urlopen(req2, timeout=10)
    items = json.loads(resp2.read())
    for item in items:
        print(f"  {item['name']} ({item['type']})")
except Exception as e:
    print(f"SRC ERROR: {e}")
