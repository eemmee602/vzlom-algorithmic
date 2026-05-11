#!/usr/bin/env python3
"""Get Vzlom.csproj and fix it with ImplicitUsings + add missing .xaml.cs files"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

# 1. Get Vzlom.csproj
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Vzlom.csproj"
req = urllib.request.Request(url, headers=headers)
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
csproj_sha = data["sha"]
csproj = base64.b64decode(data["content"]).decode()
print(f"csproj: {len(csproj)} chars")

# 2. Add ImplicitUsings to csproj
old_proj = '<PropertyGroup>\n    <TargetFramework>net8.0-windows</TargetFramework>'
new_proj = '<PropertyGroup>\n    <TargetFramework>net8.0-windows</TargetFramework>\n    <ImplicitUsings>enable</ImplicitUsings>'
if old_proj in csproj:
    csproj = csproj.replace(old_proj, new_proj)
    print("✅ Added ImplicitUsings to csproj")
else:
    print(f"⚠ Pattern not found in csproj. First 500 chars:\n{csproj[:500]}")

# 3. Push csproj
headers2 = {**headers, "Content-Type": "application/json"}
payload = json.dumps({"message": "fix: add ImplicitUsings enable (File/Path/StreamReader global)", "content": base64.b64encode(csproj.encode()).decode(), "sha": csproj_sha}).encode()
req2 = urllib.request.Request(url, data=payload, headers=headers2, method="PUT")
resp = json.loads(urllib.request.urlopen(req2, timeout=20).read())
print(f"PUSHED csproj: {resp['commit']['sha'][:8]}")

# 4. Get MemoryDialog.xaml.cs (it's referenced by XAML but might not exist)
try:
    url3 = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/src/Vzlom/Controls/MemoryDialog.xaml.cs"
    req3 = urllib.request.Request(url3, headers=headers)
    data3 = json.loads(urllib.request.urlopen(req3, timeout=10).read())
    print(f"MemoryDialog.xaml.cs exists: {data3.get('size',0)} bytes")
except Exception as e:
    print(f"MemoryDialog.xaml.cs: {e}")
