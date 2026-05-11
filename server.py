#!/usr/bin/env python3
"""
Vzlom Bridge v2.5 — Single server, single port (3456).
Multi-proxy LLM routing avec fallback automatique.
Cles API JAMAIS exposees au client.
"""
import http.server, json, subprocess, os, hashlib, uuid, secrets, time, ssl
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime
from http.client import HTTPSConnection
import sys
from dotenv import load_dotenv

# ─── Config ───
PORT = 3456
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WORKSPACE = os.path.join(BASE_DIR, "workspace")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
KEYS_FILE = os.path.join(DATA_DIR, "keys.json")
SESSIONS = {}
TIMEOUT = 15  # secondes par provider

load_dotenv(os.path.join(BASE_DIR, ".env"))

# ─── Provider configs ───
PROVIDERS = {
    "openrouter": {
        "base": "https://openrouter.ai/api/v1/chat/completions",
        "key": os.getenv("OPENROUTER_API_KEY", ""),
        "model_map": {
            "openai/gpt-4o-mini": "openai/gpt-4o-mini",
            "deepseek/deepseek-chat": "deepseek/deepseek-chat",
            "google/gemini-2.0-flash": "google/gemini-2.0-flash",
            "mistralai/mistral-small-2501": "mistralai/mistral-small-2501",
            "meta-llama/llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        },
    },
    "gemini": {
        "base": "generativelanguage.googleapis.com",
        "key": os.getenv("GEMINI_API_KEY", ""),
        "model_map": {
            "openai/gpt-4o-mini": "gemini-1.5-flash",
            "deepseek/deepseek-chat": "gemini-1.5-flash",
            "google/gemini-2.0-flash": "gemini-2.0-flash",
            "mistralai/mistral-small-2501": "gemini-1.5-flash",
            "meta-llama/llama-3.3-70b-instruct": "gemini-2.0-flash",
        },
    },
    "groq": {
        "base": "api.groq.com",
        "key": os.getenv("GROQ_API_KEY", ""),
        "model_map": {
            "openai/gpt-4o-mini": "llama-3.3-70b-versatile",
            "deepseek/deepseek-chat": "llama-3.1-70b-versatile",
            "google/gemini-2.0-flash": "llama-3.3-70b-versatile",
            "mistralai/mistral-small-2501": "mixtral-8x7b-32768",
            "meta-llama/llama-3.3-70b-instruct": "llama-3.3-70b-versatile",
        },
    },
    "cerebras": {
        "base": "api.cerebras.ai",
        "key": os.getenv("CEREBRAS_API_KEY", ""),
        "model_map": {
            "openai/gpt-4o-mini": "llama3.1-8b",
            "deepseek/deepseek-chat": "llama3.1-8b",
            "google/gemini-2.0-flash": "llama3.1-8b",
            "mistralai/mistral-small-2501": "llama3.1-8b",
            "meta-llama/llama-3.3-70b-instruct": "llama3-70b",
        },
    },
    "mistral": {
        "base": "api.mistral.ai",
        "key": os.getenv("MISTRAL_API_KEY", ""),
        "model_map": {
            "openai/gpt-4o-mini": "mistral-small-latest",
            "deepseek/deepseek-chat": "mistral-small-latest",
            "google/gemini-2.0-flash": "mistral-small-latest",
            "mistralai/mistral-small-2501": "mistral-small-latest",
            "meta-llama/llama-3.3-70b-instruct": "mistral-large-latest",
        },
    },
}

def _gemini_msg(msg):
    role = msg.get("role", "user")
    if role == "system": role = "user"
    if role == "assistant": role = "model"
    return {"role": role, "parts": [{"text": msg.get("content", "")}]}

# ─── Key rotation ───
def load_all_api_keys():
    keys = []
    for prov_name, prov in PROVIDERS.items():
        k = prov["key"]
        if k:
            keys.append({"id": f"{prov_name}_{k[:8]}", "key": k, "provider": prov_name,
                          "source": "env", "created": "env", "hits": 0, "last_used": 0})
    try:
        with open(KEYS_FILE) as f:
            for entry in json.load(f).get("keys", []):
                if entry.get("key"):
                    keys.append({"id": entry.get("id", secrets.token_hex(8)), "key": entry["key"],
                                  "provider": entry.get("provider", "openrouter"),
                                  "source": entry.get("source", "file"),
                                  "created": entry.get("created", "unknown"),
                                  "hits": entry.get("hits", 0),
                                  "last_used": entry.get("last_used", 0)})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[WARN] Erreur chargement keys.json: {e}")
    return keys

def save_api_keys(keys):
    try:
        data_keys = [{k: v for k, v in e.items() if k != "key"} | {"key_exists": True}
                      for e in keys if e["source"] != "env"]
        with open(KEYS_FILE, "w") as f:
            json.dump({"keys": data_keys, "updated": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Erreur sauvegarde keys.json: {e}")

ALL_KEYS = load_all_api_keys()
if not ALL_KEYS:
    print("[WARN] Aucune cle API trouvee !")
if not os.path.exists(KEYS_FILE):
    save_api_keys(ALL_KEYS)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)

# ─── Users ───
def load_users():
    try:
        with open(USERS_FILE) as f: return json.load(f)
    except: return {}

def save_users(users):
    with open(USERS_FILE, "w") as f: json.dump(users, f, indent=2)

def hash_password(pwd, salt=None):
    if salt is None: salt = secrets.token_hex(8)
    return f"{salt}${hashlib.sha256((salt + pwd).encode()).hexdigest()}"

def verify_password(pwd, stored):
    salt, h = stored.split("$", 1)
    return hash_password(pwd, salt) == stored

def create_session(nickname):
    token = "vzlom_" + secrets.token_hex(24)
    SESSIONS[token] = {"nickname": nickname, "created": time.time()}
    return token

def get_user_from_token(token):
    s = SESSIONS.get(token)
    if not s: return None
    if time.time() - s["created"] > 86400:
        del SESSIONS[token]
        return None
    return s["nickname"]

def get_user_memory_file(n): return os.path.join(DATA_DIR, f"memory_{n}.json")

def load_user_memory(n):
    try:
        with open(get_user_memory_file(n)) as f: return json.load(f)
    except: return {"nickname": n, "entries": []}

def save_user_memory(n, data):
    with open(get_user_memory_file(n), "w") as f: json.dump(data, f, indent=2)

def add_user_memory_entry(n, content, src="user"):
    data = load_user_memory(n)
    data["entries"].append({"content": content[:2000], "source": src,
                             "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    if len(data["entries"]) > 10000: data["entries"] = data["entries"][-10000:]
    save_user_memory(n, data)
    return data["entries"][-1]

def get_user_memory_context(n, recent=30):
    data = load_user_memory(n)
    entries = data["entries"][-recent:]
    if not entries: return "Aucune memoire."
    return "\n".join(f"[{e['timestamp']}] {e['source']}: {e['content'][:200] if len(e['content'])>200 else e['content']}" for e in entries)

def get_user_workspace(n):
    p = os.path.join(WORKSPACE, n)
    os.makedirs(p, exist_ok=True)
    return p

def get_user_github_token(n):
    u = load_users().get(n, {})
    return u.get("github_token") or u.get("github")

BLACKLIST = ["rm -rf /", "sudo", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]

def run_bash(cmd, nick):
    for d in BLACKLIST:
        if d in cmd.lower(): return f"BLOCKED: Commande interdite ({d})", True
    cwd = get_user_workspace(nick)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd,
                           env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin", "VZLOM_USER": nick})
        out = r.stdout + ("\n[STDERR]\n" + r.stderr if r.stderr else "")
        return out, (r.returncode != 0)
    except subprocess.TimeoutExpired: return "TIMEOUT: 30s", True
    except Exception as e: return f"ERROR: {e}", True

def get_user_task_file(n): return os.path.join(DATA_DIR, f"tasks_{n}.json")

def load_user_tasks(n):
    try:
        with open(get_user_task_file(n)) as f: return json.load(f)
    except: return {"tasks": []}

def save_user_tasks(n, data):
    with open(get_user_task_file(n), "w") as f: json.dump(data, f, indent=2)

def add_user_task(n, task):
    data = load_user_tasks(n)
    data["tasks"].append({"id": str(uuid.uuid4())[:8], "task": task[:500], "status": "pending",
                           "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "result": ""})
    save_user_tasks(n, data)
    return data["tasks"][-1]

def rotate_key():
    keys = load_all_api_keys()
    if not keys: return None
    keys_sorted = sorted(keys, key=lambda k: k.get("last_used", 0))
    chosen = keys_sorted[0]
    chosen["hits"] = chosen.get("hits", 0) + 1
    chosen["last_used"] = time.time()
    save_api_keys(keys)
    return chosen["key"], chosen["provider"], chosen["id"]

def resolve_provider(model_id):
    if model_id.startswith("google/"): return "gemini"
    if model_id.startswith("deepseek/"): return "openrouter"
    if model_id.startswith("mistralai/") or model_id.startswith("mistral/"): return "mistral"
    if model_id.startswith("meta-llama/"): return "groq"
    if model_id.startswith("openai/"): return "openrouter"
    return "openrouter"

def map_model(pname, cmodel):
    prov = PROVIDERS.get(pname)
    if not prov: return cmodel
    return prov["model_map"].get(cmodel, cmodel)

# ─── Streaming SSE helpers ───
def send_sse(wfile, data):
    try:
        wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
        wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        raise ConnectionError("client disconnected")

def _stream_openrouter(resp, wfile):
    full = ""
    buf = ""
    while True:
        chunk = resp.read(4096)
        if not chunk: break
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line: continue
            if line == "data: [DONE]":
                send_sse(wfile, {"done": True})
                return full
            if line.startswith("data: "):
                try:
                    d = json.loads(line[6:])
                    full += d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    send_sse(wfile, d)
                except (json.JSONDecodeError, IndexError):
                    pass
    return full

def _stream_gemini(resp, wfile):
    full = ""
    buf = ""
    while True:
        chunk = resp.read(4096)
        if not chunk: break
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line: continue
            try:
                j = json.loads(line)
                parts = j.get("candidates", [{}])
                if not parts: continue
                text = parts[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                finish = parts[0].get("finishReason", "")
                if text:
                    full += text
                    send_sse(wfile, {"choices": [{"delta": {"content": text}}]})
                if finish:
                    send_sse(wfile, {"choices": [{"delta": {}, "finish_reason": finish}]})
                    return full
            except (json.JSONDecodeError, (IndexError, KeyError)):
                continue
    return full

# ─── Proxy chat ───
def proxy_chat(self, data):
    model = data.get("model", "openai/gpt-4o-mini")
    msgs = data.get("messages", [])
    max_tokens = data.get("max_tokens", 2048)

    target = resolve_provider(model)
    ordered = ["openrouter", "gemini", "groq", "cerebras", "mistral"]
    providers_order = list(dict.fromkeys([target] + ordered))

    last_err = ""
    headers_sent = False

    for pname in providers_order:
        prov = PROVIDERS.get(pname)
        if not prov or not prov["key"]:
            continue

        try:
            native = map_model(pname, model)
            print(f"[PROXY] Trying {pname}/{native}...")

            if pname == "gemini":
                payload = json.dumps({
                    "contents": [_gemini_msg(m) for m in msgs],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}
                }).encode()
                conn = HTTPSConnection("generativelanguage.googleapis.com", timeout=TIMEOUT)
                conn.request("POST", f"/v1beta/models/{native}:streamGenerateContent?key={prov['key']}",
                             body=payload, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                if resp.status != 200:
                    raise HTTPError(f"https://generativelanguage.googleapis.com", resp.status, resp.read().decode()[:200], resp.headers, None)
                streamer = lambda: _stream_gemini(resp, self.wfile)
            else:
                payload = json.dumps({"model": native, "messages": msgs, "stream": True, "max_tokens": max_tokens}).encode()
                if pname == "groq":
                    conn = HTTPSConnection("api.groq.com", timeout=TIMEOUT)
                    conn.request("POST", "/openai/v1/chat/completions", body=payload,
                                 headers={"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json"})
                elif pname == "cerebras":
                    conn = HTTPSConnection("api.cerebras.ai", timeout=TIMEOUT)
                    conn.request("POST", "/v1/chat/completions", body=payload,
                                 headers={"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json"})
                elif pname == "mistral":
                    conn = HTTPSConnection("api.mistral.ai", timeout=TIMEOUT)
                    conn.request("POST", "/v1/chat/completions", body=payload,
                                 headers={"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json"})
                else:  # openrouter
                    conn = HTTPSConnection("openrouter.ai", timeout=TIMEOUT)
                    conn.request("POST", "/api/v1/chat/completions", body=payload,
                                 headers={"Authorization": f"Bearer {prov['key']}",
                                          "Content-Type": "application/json",
                                          "HTTP-Referer": "https://github.com/eemmee602/vzlom-algorithmic",
                                          "X-Title": "Vzlom Mobile"})
                resp = conn.getresponse()
                if resp.status != 200:
                    raise HTTPError(f"https://openrouter.ai", resp.status, resp.read().decode()[:200], resp.headers, None)
                streamer = lambda: _stream_openrouter(resp, self.wfile)

            if not headers_sent:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Provider", pname)
                self.send_header("X-Model", native)
                self._no_cache()
                self._cors()
                self.end_headers()
                headers_sent = True

            streamer()
            conn.close()
            print(f"[PROXY] {pname} completed")
            return

        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:300]
            except: pass
            last_err = f"[{pname}] HTTP {e.code}: {body[:100]}"
            if e.code == 429: last_err += " (rate limit)"
            print(f"[PROXY] {pname} failed: {last_err}")
            if not headers_sent:
                try: conn.close()
                except: pass
        except Exception as e:
            last_err = f"[{pname}] {str(e)[:120]}"
            print(f"[PROXY] {pname} error: {last_err}")
            if not headers_sent:
                try: conn.close()
                except: pass

    print(f"[PROXY] All providers failed: {last_err}")
    if headers_sent:
        try:
            send_sse(wfile, {"error": "Aucun provider disponible"})
        except: pass
    else:
        self._send_json({"error": f"Aucun provider disponible. Derniere erreur: {last_err[:200]}"}, 429)


# ─── HTTP Handler ───
class BridgeHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    log_message = lambda self, fmt, *args: None

    def _no_cache(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._no_cache()
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self._no_cache()
        self.end_headers()

    def _parse_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        try: return json.loads(self.rfile.read(length).decode("utf-8"))
        except: return {}

    def serve_html(self, filename="mobile_index.html"):
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            self.send_error(404, "HTML not found"); return
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html", "/mobile.html"):
            self.serve_html(); return

        if path in ("/dex", "/dex.html", "/DEX_TLMN.html"):
            self.serve_html("DEX_TLMN.html"); return

        if path == "/favicon.ico":
            fp = os.path.join(BASE_DIR, "favicon.ico")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    c = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(c)))
                self.end_headers()
                self.wfile.write(c)
            else:
                self.send_response(204); self.end_headers()
            return

        if path == "/health":
            st = {}
            for n, p in PROVIDERS.items():
                st[n] = {"online": True, "key_set": bool(p["key"])} if p["key"] else {"online": False, "key_set": False}
            self._send_json({"name": "Vzlom Bridge v2.5", "status": "ok", "version": "2.5", "providers": st,
                              "config": {"default": "openai/gpt-4o-mini",
                                         "fallback_order": ["groq", "mistral", "cerebras", "gemini"]}})
            return

        if path == "/api/config":
            prov_obj = {}
            for n, p in PROVIDERS.items():
                prov_obj[n] = {"online": True, "key_set": bool(p["key"])}
            avail = [n for n, p in PROVIDERS.items() if p["key"]]
            self._send_json({
                "models": {"default": "openai/gpt-4o-mini",
                           "fallbacks": ["deepseek/deepseek-chat", "mistralai/mistral-small-2501",
                                         "meta-llama/llama-3.3-70b-instruct"]},
                "providers": prov_obj, "fallback_default": "groq"
            })
            return

        if path == "/api/keys/next":
            r = rotate_key()
            if not r: self._send_json({"error": "Aucune cle API disponible"}, 503); return
            key, prov, kid = r
            self._send_json({"status": "ok", "provider": prov,
                              "key_masked": key[:8] + "...", "id": kid})
            return

        if path == "/auth/check":
            sid = (qs.get("token") or [None])[0]
            nick = get_user_from_token(sid) if sid else None
            self._send_json({"status": "ok", "nickname": nick} if nick
                            else {"error": "Token invalide"},
                            401 if not nick else 200)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]
        data = self._parse_body()

        if path == "/auth/register":
            nick = (data.get("nickname") or "").strip()
            pwd = (data.get("password") or "").strip()
            gh = (data.get("github_token") or "").strip()
            if len(nick) < 2 or len(pwd) < 2:
                self._send_json({"error": "Surnom (2+) et mot de passe (2+) requis"}, 400); return
            if nick in ("admin", "root"):
                self._send_json({"error": "Ce surnom est reserve"}, 400); return
            users = load_users()
            if nick in users:
                self._send_json({"error": "Ce surnom existe deja"}, 409); return
            users[nick] = {"password": hash_password(pwd),
                           "created": datetime.now().isoformat(), "github_token": gh}
            save_users(users)
            self._send_json({"status": "ok", "nickname": nick,
                              "token": create_session(nick)}); return

        if path == "/auth/login":
            nick = (data.get("nickname") or "").strip()
            pwd = (data.get("password") or "").strip()
            user = load_users().get(nick)
            if not user:
                self._send_json({"error": "Utilisateur inconnu"}, 401); return
            if not verify_password(pwd, user["password"]):
                self._send_json({"error": "Mot de passe incorrect"}, 401); return
            self._send_json({"status": "ok", "nickname": nick,
                              "token": create_session(nick),
                              "github_token": user.get("github_token", "")}); return

        if path == "/auth/check":
            nick = get_user_from_token(token)
            self._send_json({"status": "ok", "nickname": nick} if nick
                            else {"error": "Token invalide"},
                            401 if not nick else 200); return

        if path == "/auth/guest":
            nick = "Guest_" + secrets.token_hex(4)
            tk = create_session(nick)
            self._send_json({"status": "ok", "nickname": nick, "token": tk}); return

        if path == "/api/chat":
            proxy_chat(self, data); return

        nick = get_user_from_token(token) if token else None
        if not nick:
            self._send_json({"error": "Unauthorized"}, 401); return

        if path == "/memory":
            e = add_user_memory_entry(nick, data.get("content", ""),
                                      data.get("source", "api"))
            self._send_json({"status": "saved", "nickname": nick,
                              "entry": e}); return

        if path == "/memory/context":
            self._send_json({"nickname": nick,
                              "context": get_user_memory_context(nick)}); return

        if path == "/bash":
            cmd = data.get("command", "")
            if not cmd:
                self._send_json({"error": "Commande requise"}, 400); return
            out, err = run_bash(cmd, nick)
            self._send_json({"command": cmd, "output": out[:10000],
                              "error": err, "nickname": nick}); return

        if path == "/admin/keys":
            body = data
            if self.command == "POST":
                rk = (body.get("key") or "").strip()
                if len(rk) < 10:
                    self._send_json({"error": "Cle trop courte"}, 400); return
                if any(k["key"] == rk for k in ALL_KEYS):
                    self._send_json({"error": "Cle deja existante"}, 409); return
                ne = {"id": secrets.token_hex(8), "key": rk,
                      "provider": "openrouter", "source": "manual",
                      "created": datetime.now().isoformat(),
                      "hits": 0, "last_used": 0}
                ALL_KEYS.append(ne)
                save_api_keys(ALL_KEYS)
                self._send_json({"status": "ok",
                                  "id": ne["id"]}); return
            if self.command == "DELETE":
                kid = body.get("id", "")
                for i, k in enumerate(ALL_KEYS):
                    if k["id"] == kid and k["source"] != "env":
                        ALL_KEYS.pop(i)
                        save_api_keys(ALL_KEYS)
                        self._send_json({"status": "deleted",
                                          "id": kid}); return
                self._send_json({"error": "Cle non trouvee"}, 404); return

        if path == "/admin/users":
            u = load_users()
            self._send_json({"users": {n: {"created": v.get("created"),
                                            "github": bool(v.get("github_token"))}
                                        for n, v in u.items()}})
            return

        self._send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    print(f"[BRIDGE] Vzlom Bridge v2.5 sur le port {PORT}")
    print(f"[BRIDGE] Providers: {sum(1 for p in PROVIDERS.values() if p['key'])}/5")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Arret...")
        server.server_close()