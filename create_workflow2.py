#!/usr/bin/env python3
"""Create GitHub Actions workflow - v2"""
import urllib.request, json, base64

TOKEN = "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"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

workflow = """name: Build Vzlom

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v4
    - name: Setup .NET 8
      uses: actions/setup-dotnet@v4
      with:
        dotnet-version: '8.0.x'
    - name: Restore
      run: dotnet restore src/Vzlom/Vzlom.csproj
    - name: Build
      run: dotnet publish src/Vzlom/Vzlom.csproj -c Release -r win-x64 --self-contained false -o publish
    - name: Upload
      uses: actions/upload-artifact@v4
      with:
        name: Vzlom
        path: publish/
"""

# Create the file directly - GitHub API auto-creates directories
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/.github/workflows/build.yml"
encoded = base64.b64encode(workflow.encode()).decode()
payload = json.dumps({
    "message": "ci: auto-build Vzlom on push",
    "content": encoded,
}).encode()

req = urllib.request.Request(url, data=payload, headers=H, method="PUT")
try:
    resp = urllib.request.urlopen(req, timeout=20)
    data = json.loads(resp.read())
    print(f"✅ Workflow: {data['commit']['sha'][:8]}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"❌ {e.code}: {body[:200]}")
    # Try to read the existing file first
    try:
        req2 = urllib.request.Request(url, headers=H)
        existing = json.loads(urllib.request.urlopen(req2, timeout=10).read())
        print(f"  File exists, SHA: {existing.get('sha','?')}")
        payload2 = json.dumps({
            "message": "ci: auto-build Vzlom on push (update)",
            "content": encoded,
            "sha": existing["sha"]
        }).encode()
        req3 = urllib.request.Request(url, data=payload2, headers=H, method="PUT")
        resp3 = urllib.request.urlopen(req3, timeout=20)
        data3 = json.loads(resp3.read())
        print(f"✅ Updated: {data3['commit']['sha'][:8]}")
    except Exception as e2:
        print(f"  Also failed: {e2}")
