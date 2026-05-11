#!/usr/bin/env python3
"""Update mobile/index.html in the repo with fixes"""
import urllib.request, json, base64, re

TOKEN = "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"
headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
}

# Get current file SHA
url = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/contents/mobile/index.html"
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
sha = data["sha"]
current = base64.b64decode(data["content"]).decode()

print(f"Got file: {len(current)} chars, SHA: {sha}")
print("Patching...")

# PATCH 1: Remove showThinking() call and replace with just setStatus
# Instead of creating a card, just update the header status text
current = re.sub(
    r"setStatus\('🤔 Réflexion\.\.\.'\);\s*// Show thinking card\s*showThinking\('Analyse de la demande\.\.\.'\);",
    "setStatus('🤔 Analyse...');",
    current
)

# PATCH 2: Add showThinking function (in case it's still called elsewhere), but make it a no-op on the chat
# Actually, just add the function as a stub so no crash
if "function showThinking" not in current:
    current = current.replace(
        "function showStatusCard(msg) {",
        """function showThinking(msg) {
  // Pas de carte dans le chat — status bar seulement
  setStatus('🤔 ' + (msg || 'Réflexion...').substring(0, 25));
}

function showStatusCard(msg) {"""
    )
    print("Added showThinking stub")

# PATCH 3: Remove the thinkingCard DOM manipulation (since no thinkingCard anymore)
# Replace the thinkingCard removal code with a simple setStatus
current = re.sub(
    r"// Remove thinking card when streaming starts\s*const tc = document\.getElementById\('thinkingCard'\);\s*if \(tc\) \{[^}]+\}",
    "// Streaming démarre\n      setStatus('🤖 ' + model.split('/').pop().substring(0, 20));",
    current
)

# PATCH 4: Update status messages to be short (1-2 words)
current = current.replace(
    "setStatus(`🔄 Bascule → ${model}`);",
    "setStatus(`🔄 ${model.split('/').pop().substring(0, 15)}`);",
)
current = current.replace(
    "else setStatus(`🤖 ${model}`);",
    "else setStatus(`🤖 ${model.split('/').pop().substring(0, 18)}`);",
)

# PATCH 5: Set initial status to show the model name cleanly
current = current.replace(
    "setStatus('🤔 Réflexion...');",
    "setStatus('🤔 Analyse...');",
)

print(f"Patched file: {len(current)} chars")

# Encode and push
encoded = base64.b64encode(current.encode()).decode()
payload = json.dumps({
    "message": "fix: remove thinking card, status bar only (1-2 mots)",
    "content": encoded,
    "sha": sha,
}).encode()

req2 = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
try:
    resp2 = urllib.request.urlopen(req2, timeout=15)
    result = json.loads(resp2.read())
    print(f"PUSHED: {result['commit']['sha']}")
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()

# Also update local file on Advin
with open("/home/vzlom-bridge/mobile_index.html", "w") as f:
    f.write(current)
print("Local file updated")
