#!/usr/bin/env python3
"""
Vzlom Bridge v2.5 — Single server, single port (3456).
Multi-proxy LLM routing (OpenRouter → Gemini → Groq → Cerebras → Mistral → Cohere).
Clés API JAMAIS exposées au client. Rotation automatique.
"""
import http.server, json, subprocess, os, hashlib, uuid, secrets, time, mimetypes
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from datetime import datetime
import importlib, sys, http.client, ssl
from dotenv import load_dotenv

# ─── Config ───
PORT = 3456
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
WORKSPACE = os.path.join(BASE_DIR, "workspace")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
KEYS_FILE = os.path.join(DATA_DIR, "keys.json")
SESSIONS = {}

load_dotenv(os.path.join(BASE_DIR, ".env"))

# ─── Provider configs ───
# model_map: traduit le modele client "prefix/name" → nom natif du provider
PROVIDERS = {
    "openrouter": {
        "base": "https://openrouter.ai/api/v1/chat/completions",
        "key": os.getenv("OPENROUTER_API_KEY", ""),
        "headers": lambda k: {
            "Authorization": f"Bearer {k}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/eemmee602/vzlom-algorithmic",
            "X-Title": "Vzlom Mobile",
        },
        "model_map": {
            "openai/gpt-4o-mini": "openai/gpt-4o-mini",
            "deepseek/deepseek-chat": "deepseek/deepseek-chat",
            "google/gemini-2.0-flash": "google/gemini-2.0-flash",
            "mistralai/mistral-small-2501": "mistralai/mistral-small-2501",
            "meta-llama/llama-3.3-70b-instruct": "meta-llama/llama-3.3-70b-instruct",
        },
    },
    "gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
        "key": os.getenv("GEMINI_API_KEY", ""),
        "headers": lambda k: {"Content-Type": "application/json"},
        "model_map": {
            "openai/gpt-4o-mini": "gemini-1.5-flash",
            "deepseek/deepseek-chat": "gemini-1.5-flash",
            "google/gemini-2.0-flash": "gemini-2.0-flash",
            "mistralai/mistral-small-2501": "gemini-1.5-flash",
            "meta-llama/llama-3.3-70b-instruct": "gemini-2.0-flash",
        },
    },
    "groq": {
        "base": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.getenv("GROQ_API_KEY", ""),
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        "model_map": {
            "openai/gpt-4o-mini": "llama-3.3-70b-versatile",
            "deepseek/deepseek-chat": "llama-3.1-70b-versatile",
            "google/gemini-2.0-flash": "llama-3.3-70b-versatile",
            "mistralai/mistral-small-2501": "mixtral-8x7b-32768",
            "meta-llama/llama-3.3-70b-instruct": "llama-3.3-70b-versatile",
        },
    },
    "cerebras": {
        "base": "https://api.cerebras.ai/v1/chat/completions",
        "key": os.getenv("CEREBRAS_API_KEY", ""),
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        "model_map": {
            "openai/gpt-4o-mini": "llama3.1-8b",
            "deepseek/deepseek-chat": "llama3.1-8b",
            "google/gemini-2.0-flash": "llama3.1-8b",
            "mistralai/mistral-small-2501": "llama3.1-8b",
            "meta-llama/llama-3.3-70b-instruct": "llama3-70b",
        },
    },
    "mistral": {
        "base": "https://api.mistral.ai/v1/chat/completions",
        "key": os.getenv("MISTRAL_API_KEY", ""),
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        "model_map": {
            "openai/gpt-4o-mini": "mistral-small-latest",
            "deepseek/deepseek-chat": "mistral-small-latest",
            "google/gemini-2.0-flash": "mistral-small-latest",
            "mistralai/mistral-small-2501": "mistral-small-latest",
            "meta-llama/llama-3.3-70b-instruct": "mistral-large-latest",
        },
    },
    "cohere": {
        "base": "https://api.cohere.ai/v1/chat",
        "key": os.getenv("COHERE_API_KEY", ""),
        "headers": lambda k: {"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
"model_map": {
            "openai/gpt-4o-mini": "command-r-plus",
            "deepseek/deepseek-chat": "command-r-plus",
            "google/gemini-2.0-flash": "command-r-plus",
            "mistralai/mistral-small-2501": "command-r",
            "meta-llama/llama-3.3-70b-instruct": "command-r-plus",
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
            keys.append({
                "id": f"{prov_name}_{k[:8]}",
                "key": k,
                "provider": prov_name,
                "source": "env",
                "created": "env",
                "hits": 0,
                "last_used": 0,
            })
    try:
        with open(KEYS_FILE) as f:
            data = json.load(f)
            for entry in data.get("keys", []):
                if entry.get("key"):
                    keys.append({
                        "id": entry.get("id", secrets.token_hex(8)),
                        "key": entry["key"],
                        "provider": entry.get("provider", "openrouter"),
                        "source": entry.get("source", "file"),
                        "created": entry.get("created", "unknown"),
                        "hits": entry.get("hits", 0),
                        "last_used": entry.get("last_used", 0),
                    })
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[WARN] Erreur chargement keys.json: {e}")
    return keys

def save_api_keys(keys):
    try:
        data_keys = [
            {k: v for k, v in entry.items() if k != "key"} | {"key_exists": True}
            for entry in keys if entry["source"] != "env"
        ]
        with open(KEYS_FILE, "w") as f:
            json.dump({"keys": data_keys, "updated": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Erreur sauvegarde keys.json: {e}")

ALL_KEYS = load_all_api_keys()
if not ALL_KEYS:
    print("[WARN] Aucune clé API trouvée !")
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

def hash_password(password, salt=None):
    if salt is None: salt = secrets.token_hex(8)
    return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"

def verify_password(password, stored):
    salt, h = stored.split("$", 1)
    return hash_password(password, salt) == stored

def create_session(nickname):
    token = "vzlom_" + secrets.token_hex(24)
    SESSIONS[token] = {"nickname": nickname, "created": time.time()}
    return token

def get_user_from_token(token):
    session = SESSIONS.get(token)
    if not session: return None
    if time.time() - session["created"] > 86400:
        del SESSIONS[token]
        return None
    return session["nickname"]

# ─── User memory ───
def get_user_memory_file(nickname): return os.path.join(DATA_DIR, f"memory_{nickname}.json")

def load_user_memory(nickname):
    path = get_user_memory_file(nickname)
    try:
        with open(path) as f: return json.load(f)
    except: return {"nickname": nickname, "entries": []}

def save_user_memory(nickname, data):
    with open(get_user_memory_file(nickname), "w") as f: json.dump(data, f, indent=2)

def add_user_memory_entry(nickname, content, source="user"):
    data = load_user_memory(nickname)
    data["entries"].append({"content": content[:2000], "source": source, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    if len(data["entries"]) > 10000: data["entries"] = data["entries"][-10000:]
    save_user_memory(nickname, data)
    return data["entries"][-1]

def get_user_memory_context(nickname, recent=30):
    data = load_user_memory(nickname)
    entries = data["entries"][-recent:]
    if not entries: return "Aucune mémoire."
    return "\n".join(f"[{e['timestamp']}] {e['source']}: {e['content'][:200] if len(e['content']) > 200 else e['content']}" for e in entries)

# ─── Workspace ───
def get_user_workspace(nickname):
    path = os.path.join(WORKSPACE, nickname)
    os.makedirs(path, exist_ok=True)
    return path

def get_user_github_token(nickname):
    user = load_users().get(nickname, {})
    return user.get("github_token") or user.get("github")

# ─── Bash ───
BLACKLIST = ["rm -rf /", "sudo", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]

def run_bash(command, nickname):
    for d in BLACKLIST:
        if d in command.lower(): return f"BLOCKED: Commande interdite ({d})", True
    cwd = get_user_workspace(nickname)
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd,
                           env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin", "VZLOM_USER": nickname})
        out = r.stdout + ("\n[STDERR]\n" + r.stderr if r.stderr else "")
        return out, (r.returncode != 0)
    except subprocess.TimeoutExpired: return "TIMEOUT: 30s", True
    except Exception as e: return f"ERROR: {e}", True

# ─── Tasks ───
def get_user_task_file(nickname): return os.path.join(DATA_DIR, f"tasks_{nickname}.json")

def load_user_tasks(nickname):
    path = get_user_task_file(nickname)
    try:
        with open(path) as f: return json.load(f)
    except: return {"tasks": []}

def save_user_tasks(nickname, data):
    with open(get_user_task_file(nickname), "w") as f: json.dump(data, f, indent=2)

def add_user_task(nickname, task):
    data = load_user_tasks(nickname)
    data["tasks"].append({"id": str(uuid.uuid4())[:8], "task": task[:500], "status": "pending",
                          "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "result": ""})
    save_user_tasks(nickname, data)
    return data["tasks"][-1]

# ─── Key rotation ───
def rotate_key():
    keys = load_all_api_keys()
    if not keys: return None
    keys_sorted = sorted(keys, key=lambda k: k.get("last_used", 0))
    chosen = keys_sorted[0]
    chosen["hits"] = chosen.get("hits", 0) + 1
    chosen["last_used"] = time.time()
    save_api_keys(keys)
    return chosen["key"], chosen["provider"], chosen["id"]

def rotate_key_handler(self):
    result = rotate_key()
    if not result:
        self._send_json({"error": "Aucune clé API disponible"}, 503)
        return
    key, prov, kid = result
    self._send_json({"status": "ok", "provider": prov, "key_masked": key[:8] + "••••" + key[-4:] if len(key) > 12 else "****"})

# ─── Resolve provider from client model prefix ───
def resolve_provider(model_id):
    if model_id.startswith("google/"): return "gemini"
    if model_id.startswith("deepseek/"): return "openrouter"
    if model_id.startswith("mistralai/") or model_id.startswith("mistral/"): return "mistral"
    if model_id.startswith("meta-llama/"): return "groq"
    if model_id.startswith("openai/"): return "openrouter"
    return "openrouter"

# ─── Map client model → provider native model ───
def map_model(prov_name, client_model):
    prov = PROVIDERS.get(prov_name)
    if not prov: return client_model
    return prov["model_map"].get(client_model, client_model)

# ─── Proxy calls ───
def call_openrouter_api(prov_name, api_key, model, msgs, max_tokens):
    """Appel OpenAI-compatible (OpenRouter, Groq, Cerebras, Mistral)."""
    prov = PROVIDERS[prov_name]
    payload = json.dumps({"model": model, "messages": msgs, "stream": True, "max_tokens": max_tokens}).encode()
    url = prov["base"]
    req = Request(url, data=payload, headers=prov["headers"](api_key), method="POST")
    return urlopen(req, timeout=120)

def call_gemini_api(api_key, model, msgs, max_tokens):
    """Appel Gemini API directe."""
    transformed = {
        "contents": [_gemini_msg(m) for m in msgs],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={api_key}"
    payload = json.dumps(transformed).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    return urlopen(req, timeout=120)

def call_cohere_api(api_key, model, msgs, max_tokens):
    """Appel Cohere API (format légèrement différent)."""
    cohere_msgs = []
    for m in msgs:
        role = m.get("role", "user")
        if role == "system": role = "system"
        elif role == "assistant": role = "assistant"
        else: role = "user"
        cohere_msgs.append({"role": role, "message": m.get("content", "")})
    payload = json.dumps({"model": model, "message": cohere_msgs[-1]["message"], "chat_history": cohere_msgs[:-1], "max_tokens": max_tokens, "stream": True}).encode()
    req = Request(f"{PROVIDERS['cohere']['base']}?model={model}", data=payload, headers=PROVIDERS["cohere"]["headers"](api_key), method="POST")
    return urlopen(req, timeout=120)

def proxy_chat(self, data):
    """Routeur principal : essaie les providers dans l'ordre, fallback automatique."""
    model = data.get("model", "openai/gpt-4o-mini")
    msgs = data.get("messages", [])
    max_tokens = data.get("max_tokens", 2048)

    target_provider = resolve_provider(model)
    # Ordre : cible → openrouter → gemini → groq → cerebras → mistral → cohere
    ordered = ["openrouter", "gemini", "groq", "cerebras", "mistral", "cohere"]
    providers_order = list(dict.fromkeys([target_provider] + ordered))

    last_err = ""
    for prov_name in providers_order:
        prov = PROVIDERS.get(prov_name)
        if not prov or not prov["key"]:
            continue

        try:
            native_model = map_model(prov_name, model)

            if prov_name == "gemini":
                resp = call_gemini_api(prov["key"], native_model, msgs, max_tokens)
            elif prov_name == "cohere":
                resp = call_cohere_api(prov["key"], native_model, msgs, max_tokens)
            else:
                resp = call_openrouter_api(prov_name, prov["key"], native_model, msgs, max_tokens)

            # Succès → stream SSE au client
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Provider", prov_name)
            self.send_header("X-Model", native_model)
            self._no_cache()
            self._cors()
            self.end_headers()

            is_gemini = (prov_name == "gemini")
            is_cohere = (prov_name == "cohere")

            for line in resp.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if is_gemini:
                        try:
                            j = json.loads(decoded)
                            text = j.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            finish = j.get("candidates", [{}])[0].get("finishReason", "")
                        except (IndexError, KeyError):
                            text = ""
                            finish = ""
                        if text:
                            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n".encode())
                        if finish:
                            self.wfile.write(b"data: [DONE]\n\n")
                            break
                    elif is_cohere:
                        try:
                            j = json.loads(decoded)
                            text = j.get("text", "")
                            is_final = j.get("is_finished", False)
                        except (json.JSONDecodeError, KeyError):
                            text = ""
                            is_final = False
                        if text:
                            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n".encode())
                        if is_final:
                            self.wfile.write(b"data: [DONE]\n\n")
                            break
                    else:
                        if decoded.strip() == "data: [DONE]":
                            self.wfile.write(b"data: [DONE]\n\n")
                            break
                        try:
                            d = json.loads(decoded.replace("data: ", ""))
                            if d.get("choices", [{}])[0].get("finish_reason"):
                                self.wfile.write(b"data: [DONE]\n\n")
                                break
                        except (json.JSONDecodeError, IndexError):
                            pass
                        self.wfile.write((decoded + "\n").encode())
                    try:
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
            return

        except HTTPError as e:
            body = e.read().decode()[:300]
            last_err = f"[{prov_name}] HTTP {e.code}: {body[:100]}"
            if e.code == 429:
                last_err += " (rate limit)"
            print(f"[PROXY] {prov_name} failed: {last_err}")
        except Exception as e:
            last_err = f"[{prov_name}] {str(e)[:120]}"
            print(f"[PROXY] {prov_name} error: {last_err}")
            continue

    print(f"[PROXY] All providers failed. Last error: {last_err}")
    self._send_json({"error": f"Aucun provider disponible. Dernière erreur: {last_err[:200]}"}, 429)

# ─── Handler HTTP ───
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
        raw = self.rfile.read(length).decode("utf-8")
        try: return json.loads(raw)
        except json.JSONDecodeError: return {}

    def serve_html(self, filename="mobile_index.html"):
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            self.send_error(404, "HTML not found")
            return
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

    # ── GET ──
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]

        if path in ("/", "/index.html", "/mobile.html"):
            self.serve_html("mobile_index.html")
            return

        if path == "/favicon.ico":
            favicon_path = os.path.join(BASE_DIR, "favicon.ico")
            if os.path.exists(favicon_path):
                with open(favicon_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(204)
                self.end_headers()
            return

        # ── API publiques ──
        if path == "/health":
            prov_status = {}
            for name, p in PROVIDERS.items():
                if p["key"]:
                    prov_status[name] = {"key_set": True, "masked": p["key"][:8] + "••••"}
                else:
                    prov_status[name] = {"key_set": False}
            self._send_json({
                "name": "Vzlom Bridge v2.5",
                "status": "ok",
                "version": "2.5",
                "providers": prov_status
            })
            return

        if path == "/api/config":
            available = []
            for name, p in PROVIDERS.items():
                if p["key"]:
                    available.append(name)
            self._send_json({
                "models": {
                    "default": "openai/gpt-4o-mini",
                    "fallbacks": [
                        "deepseek/deepseek-chat",
                        "mistralai/mistral-small-2501",
                        "meta-llama/llama-3.3-70b-instruct"
                    ],
                },
                "providers": available,
                "fallback_default": "groq",
            })
            return

        if path == "/api/keys/next":
            result = rotate_key()
            if not result:
                self._send_json({"error": "Aucune clé API disponible"}, 503)
                return
            key, prov, kid = result
            self._send_json({
                "status": "ok",
                "provider": prov,
                "key_masked": key[:8] + "••••" + key[-4:] if len(key) > 12 else "****",
                "id": kid
            })
            return

        # ── Admin (protégé) ──
        if path in ("/admin/keys", "/admin/users"):
            nickname = get_user_from_token(token) if token else None
            if not nickname:
                self._send_json({"error": "Unauthorized"}, 401)
                return

            if path == "/admin/keys":
                body = self._parse_body()
                if self.command == "POST":
                    raw_key = (body.get("key") or "").strip()
                    if len(raw_key) < 10:
                        self._send_json({"error": "Clé trop courte"}, 400)
                        return
                    if any(k["key"] == raw_key for k in ALL_KEYS):
                        self._send_json({"error": "Clé déjà existante"}, 409)
                        return
                    new_entry = {
                        "id": secrets.token_hex(8),
                        "key": raw_key,
                        "provider": "openrouter",
                        "source": "manual",
                        "created": datetime.now().isoformat(),
                        "hits": 0,
                        "last_used": 0,
                    }
                    ALL_KEYS.append(new_entry)
                    save_api_keys(ALL_KEYS)
                    self._send_json({"status": "ok", "id": new_entry["id"]})
                    return

                if self.command == "DELETE":
                    kid = (body.get("id") or "")
                    for i, k in enumerate(ALL_KEYS):
                        if k["id"] == kid and k["source"] != "env":
                            ALL_KEYS.pop(i)
                            save_api_keys(ALL_KEYS)
                            self._send_json({"status": "deleted", "id": kid})
                            return
                    self._send_json({"error": "Clé non trouvée"}, 404)
                    return

            if path == "/admin/users":
                users = load_users()
                safe = {n: {"created": u.get("created"), "github": bool(u.get("github_token"))}
                        for n, u in users.items()}
                self._send_json({"users": safe})
                return

        # Requête inconnue
        self._send_json({"error": "Not found"}, 404)

    # ── POST ──
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]
        data = self._parse_body()

        if path == "/auth/register":
            nickname = (data.get("nickname") or "").strip()
            password = (data.get("password") or "").strip()
            github_token = (data.get("github_token") or "").strip()
            if len(nickname) < 2 or len(password) < 2:
                self._send_json({"error": "Surnom (2+) et mot de passe (2+) requis"}, 400)
                return
            if nickname in ("admin", "root"):
                self._send_json({"error": "Ce surnom est réservé"}, 400)
                return
            users = load_users()
            if nickname in users:
                self._send_json({"error": "Ce surnom existe déjà"}, 409)
                return
            users[nickname] = {
                "password": hash_password(password),
                "created": datetime.now().isoformat(),
                "github_token": github_token
            }
            save_users(users)
            self._send_json({"status": "ok", "nickname": nickname, "token": create_session(nickname)})
            return

        if path == "/auth/login":
            nickname = (data.get("nickname") or "").strip()
            password = (data.get("password") or "").strip()
            users = load_users()
            user = users.get(nickname)
            if not user:
                self._send_json({"error": "Utilisateur inconnu"}, 401)
                return
            if not verify_password(password, user["password"]):
                self._send_json({"error": "Mot de passe incorrect"}, 401)
                return
            self._send_json({
                "status": "ok",
                "nickname": nickname,
                "token": create_session(nickname),
                "github_token": user.get("github_token", "")
            })
            return

        if path == "/auth/check":
            nick = get_user_from_token(token)
            self._send_json(
                {"status": "ok", "nickname": nick} if nick else {"error": "Token invalide"},
                401 if not nick else 200
            )
            return

        # ── Proxy LLM ──
        if path == "/api/chat":
            proxy_chat(self, data)
            return

        # ── Protégé ──
        nickname = get_user_from_token(token) if token else None
        if not nickname:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        if path == "/memory":
            entry = add_user_memory_entry(nickname, data.get("content", ""), data.get("source", "api"))
            self._send_json({"status": "saved", "nickname": nickname, "entry": entry})
            return

        if path == "/memory/context":
            self._send_json({"nickname": nickname, "context": get_user_memory_context(nickname)})
            return

        if path == "/bash":
            cmd = data.get("command", "")
            if not cmd:
                self._send_json({"error": "Commande requise"}, 400)
                return
            out, err = run_bash(cmd, nickname)
            self._send_json({"command": cmd, "output": out[:10000], "error": err, "nickname": nickname})
            return

        self._send_json({"error": "Not found"}, 404)

# ─── Main ───
if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    print(f"[BRIDGE] Vzlom Bridge v2.5 démarré sur le port {PORT}")
    print(f"[BRIDGE] Providers configurés: {sum(1 for p in PROVIDERS.values() if p['key'])}/6")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Arrêt...")
        server.server_close()