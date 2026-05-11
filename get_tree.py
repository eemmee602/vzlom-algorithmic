#!/usr/bin/env python3
"""Get Vzlom full source tree"""
import urllib.request, json, base64, sys

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

def get_contents(path):
    url = f"https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/{path}"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        items = json.loads(resp.read())
        return items
    except Exception as e:
        return {"error": str(e)}

def list_tree(prefix, indent=0):
    items = get_contents(prefix)
    if isinstance(items, dict) and "error" in items:
        print("  " * indent + f"[{prefix}: {items['error']}]")
        return
    for item in items:
        print("  " * indent + f"{item['name']} ({item['type']}, {item.get('size',0)}B)")
        if item['type'] == 'dir':
            list_tree(prefix + "/" + item['name'], indent+1)

# List everything under src/Vzlom
list_tree("src/Vzlom")

print("\n=== api_defaults.json ===")
item = get_contents("api_defaults.json")
if isinstance(item, list):
    item = item[0]
if item.get("type") == "file":
    req = urllib.request.Request(item["download_url"], headers=headers)
    resp = urllib.request.urlopen(req, timeout=10)
    content = resp.read().decode()
    print(content[:2000])
