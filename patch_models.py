#!/usr/bin/env python3
"""Update mobile HTML with multiple models and smart failover"""
import urllib.request, json, base64

TOKEN = "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"
headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/mobile/index.html"

# Get SHA
req = urllib.request.Request(url, headers=headers)
sha = json.loads(urllib.request.urlopen(req, timeout=10).read())["sha"]

# Read file
req2 = urllib.request.Request(url + "?ref=main", headers=headers)
data = json.loads(urllib.request.urlopen(req2, timeout=10).read())
current = base64.b64decode(data["content"]).decode()

# 1. Fix default model + fallbacks
old_defaults = """  keys:['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'],model:'openai/gpt-4o',falls:[],auto:'smart'"""
new_defaults = """  keys:['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'],model:'google/gemini-2.0-flash-001',falls:['google/gemini-2.0-flash-lite','deepseek/deepseek-chat','mistralai/mistral-small-2501','meta-llama/llama-3.2-3b-instruct','cohere/command-r7b-12-2024','qwen/qwen2.5-7b-instruct'],auto:'smart'"""

# 2. Fix the input fields too
old_model_input = """<input type="text" id="inModel" value="openai/gpt-4o">"""
new_model_input = """<input type="text" id="inModel" value="google/gemini-2.0-flash-001">"""

old_falls = """<textarea id="inFall" rows="2">anthropic/claude-sonnet-4-20250514</textarea>"""
new_falls = """<textarea id="inFall" rows="4">google/gemini-2.0-flash-lite
deepseek/deepseek-chat
mistralai/mistral-small-2501
meta-llama/llama-3.2-3b-instruct</textarea>"""

# Apply patches
fixed = current.replace(old_defaults, new_defaults)
fixed = fixed.replace(old_model_input, new_model_input)
fixed = fixed.replace(old_falls, new_falls)

# 3. Make sure max_tokens is 2048 (not 8192)
fixed = fixed.replace("max_tokens:8192", "max_tokens:2048")
fixed = fixed.replace("max_tokens:4096", "max_tokens:2048")

# 4. Smarter failover: show which model is being tried
old_loop_try = """const model=att<1?S.model:(S.falls?.[att-1]||S.model);"""
new_loop_try = """const model=att<1?S.model:(S.falls?.[att-1]||S.model);addMsg('🔄 Tentative '+(att+1)+'/'+(maxAtt+1)+': '+model.split('/').pop(),'status');"""

fixed = fixed.replace(old_loop_try, new_loop_try)

# Stats
for check in ['gemini-2.0-flash-001', 'gemini-2.0-flash-lite', 'deepseek/deepseek-chat', 'mistralai/mistral-small', 'llama-3.2-3b', 'cohere/command-r7b', 'qwen/qwen2.5-7b', 'max_tokens:2048']:
    c = fixed.count(check)
    print(f"  {check}: {c}")

print(f"Total size: {len(fixed)} chars")

# Push
encoded = base64.b64encode(fixed.encode()).decode()
payload = json.dumps({"message": "feat: 7 fallback models (free/cheap), smart rotation, auto-failover", "content": encoded, "sha": sha}).encode()
req3 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
resp = json.loads(urllib.request.urlopen(req3, timeout=20).read())
print(f"PUSHED: {resp['commit']['sha'][:8]}")

# Local
with open("/home/vzlom-bridge/mobile_index.html", "w") as f: f.write(fixed)
with open("/home/vzlom-bridge/mobile_v2.html", "w") as f: f.write(fixed)
print("Local OK")
