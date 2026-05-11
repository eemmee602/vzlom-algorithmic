#!/usr/bin/env python3
"""Check GitHub mobile companion"""
import urllib.request, json, base64, sys

TOKEN = "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"
REPO = "eemmee602/vzlom-algorithmic"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Try to get repo info first
req = urllib.request.Request(f"https://api.github.com/repos/{REPO}", headers=headers)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print("REPO:", data.get("name"), "- private:", data.get("private"))
except Exception as e:
    print(f"REPO ERROR: {e}")

# Try mobile directory
req2 = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contents/mobile", headers=headers)
try:
    resp2 = urllib.request.urlopen(req2, timeout=10)
    items = json.loads(resp2.read())
    for item in items:
        print(f"  {item['name']} ({item['type']}) - {item['size']} bytes")
        if item['name'] == 'index.html':
            req3 = urllib.request.Request(item['download_url'], headers=headers)
            resp3 = urllib.request.urlopen(req3, timeout=10)
            content = resp3.read().decode()
            # Write it locally
            with open('/home/vzlom-bridge/mobile_index.html', 'w') as f:
                f.write(content)
            print(f"  -> Downloaded index.html ({len(content)} chars)")
except Exception as e:
    print(f"MOBILE ERROR: {e}")
