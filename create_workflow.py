#!/usr/bin/env python3
"""Create GitHub Actions workflow to auto-build Vzlom"""
import urllib.request, json, base64

TOKEN = "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"
H = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

workflow = """name: Build Vzlom

on:
  push:
    branches: [ main ]
  workflow_dispatch:  # Permet de lancer manuellement aussi

jobs:
  build:
    runs-on: windows-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Setup .NET 8
      uses: actions/setup-dotnet@v4
      with:
        dotnet-version: '8.0.x'
    
    - name: Restore NuGet packages
      run: dotnet restore src/Vzlom/Vzlom.csproj
    
    - name: Build Release
      run: dotnet publish src/Vzlom/Vzlom.csproj -c Release -r win-x64 --self-contained false -o publish
    
    - name: Upload artifact
      uses: actions/upload-artifact@v4
      with:
        name: Vzlom-Release
        path: publish/
    
    - name: Create Release
      uses: softprops/action-gh-release@v2
      if: startsWith(github.ref, 'refs/tags/')
      with:
        files: publish/**
        generate_release_notes: true
"""

# Check if .github/workflows exists
try:
    url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/.github/workflows"
    req = urllib.request.Request(url, headers=H)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        existing = json.loads(resp.read())
    except:
        existing = []
except:
    existing = []

# Get SHA if file exists
sha = ""
try:
    url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/.github/workflows/build.yml"
    req = urllib.request.Request(url, headers=H)
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    sha = data.get("sha", "")
except:
    sha = ""

# Push workflow file
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/.github/workflows/build.yml"
encoded = base64.b64encode(workflow.encode()).decode()
payload = json.dumps({
    "message": "ci: auto-build Vzlom on push (Windows + .NET 8)",
    "content": encoded,
    **({"sha": sha} if sha else {})
}).encode()
req2 = urllib.request.Request(url, data=payload, headers=H, method="PUT")
resp = json.loads(urllib.request.urlopen(req2, timeout=20).read())
print(f"✅ Workflow créé: {resp['commit']['sha'][:8]}")
