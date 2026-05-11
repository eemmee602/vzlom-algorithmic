#!/usr/bin/env python3
"""Push VzlomUpdater.py and Updater.bat to the GitHub repo"""
import urllib.request, json, base64

TOKEN = "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"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
}
REPO = "eemmee602/vzlom-algorithmic"

def push_file(path, local_path, message):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    # Get existing SHA if exists
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        sha = json.loads(resp.read()).get("sha", "")
    except:
        sha = ""

    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    payload = json.dumps({
        "message": message,
        "content": content,
        **({"sha": sha} if sha else {}),
    }).encode()

    req2 = urllib.request.Request(url, data=payload, headers=HEADERS, method="PUT")
    try:
        resp2 = urllib.request.urlopen(req2, timeout=20)
        result = json.loads(resp2.read())
        print(f"✅ {path} → {result['commit']['sha'][:8]}")
    except Exception as e:
        print(f"❌ {path}: {e}")

push_file("VzlomUpdater.py", "/home/vzlom-bridge/workspace/VzlomUpdater.py",
          "feat: auto-updater script (download, build, install)")
push_file("Updater.bat", "/home/vzlom-bridge/workspace/Updater.bat",
          "feat: windows batch launcher for updater")
