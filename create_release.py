#!/usr/bin/env python3
"""Create a GitHub Release so user can download source zip properly"""
import urllib.request, json

TOKEN = "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"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

# Create a tag first on vzlom-algorithmic
tag_name = "v2.0.0-beta1"
repo = "eemmee602/vzlom-algorithmic"

# Get latest commit SHA on main
req = urllib.request.Request(f"https://api.github.com/repos/{repo}/git/ref/heads/main", headers=H)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
main_sha = data["object"]["sha"]
print(f"Main SHA: {main_sha[:8]}")

# Create the tag reference
tag_payload = json.dumps({
    "ref": f"refs/tags/{tag_name}",
    "sha": main_sha
}).encode()
req2 = urllib.request.Request(f"https://api.github.com/repos/{repo}/git/refs", data=tag_payload, headers=H, method="POST")
try:
    resp2 = urllib.request.urlopen(req2, timeout=10)
    print(f"✅ Tag {tag_name} créé")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if "already exists" in body:
        print(f"Tag {tag_name} existe déjà")
    else:
        print(f"Tag error: {e.code} {body[:100]}")

# Create the release
release_payload = json.dumps({
    "tag_name": tag_name,
    "name": "Vzlom v2.0.0-beta1",
    "body": "✅ Code compilable — usings fixés, MemoryDialog.xaml.cs créé, XAML réparé.\n\n**Télécharge le zip Source code** ci-dessous, extrais, puis :\ndotnet publish src/Vzlom/Vzlom.csproj -c Release -r win-x64 --self-contained false -o C:\\Vzlom\n\nPuis lance C:\\Vzlom\\Vzlom.exe",
    "draft": False,
    "prerelease": True
}).encode()

req3 = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases", data=release_payload, headers=H, method="POST")
try:
    resp3 = urllib.request.urlopen(req3, timeout=15)
    release = json.loads(resp3.read())
    print(f"✅ Release créée: {release['html_url']}")
    print(f"📥 ZIP: {release['zipball_url']}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"❌ Release error: {e.code} {body[:200]}")
