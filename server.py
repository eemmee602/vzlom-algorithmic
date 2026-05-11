#!/usr/bin/env python3
"""
Vzlom Bridge v2.2 — Single server, single port (3456).
Sert l'API REST + l'interface mobile sur le même port.
Zéro dépendance externe.
"""
import http.server, json, subprocess, os, hashlib, uuid, secrets, time
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import importlib, sys, mimetypes
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

# ─── API Keys ───
def load_all_api_keys():
    keys = []
    env_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if env_key:
        keys.append({"id": "env", "key": env_key, "source": "env", "created": "env", "hits": 0, "last_used": 0})
    try:
        with open(KEYS_FILE) as f:
            data = json.load(f)
            for entry in data.get("keys", []):
                if entry.get("key"):
                    keys.append({
                        "id": entry.get("id", secrets.token_hex(8)),
                        "key": entry["key"],
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
if not os.path.exists(KEYS_FILE):
    save_api_keys(ALL_KEYS)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

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
    """Retourne la prochaine clé API active (round-robin basé sur last_used)."""
    keys = load_all_api_keys()
    if not keys: return None
    # Trier par last_used ascendant → utiliser la moins récemment utilisée
    keys_sorted = sorted(keys, key=lambda k: k.get("last_used", 0))
    chosen = keys_sorted[0]
    chosen["hits"] = chosen.get("hits", 0) + 1
    chosen["last_used"] = time.time()
    # Sauvegarder le compteur mis à jour (uniquement les clés non-env)
    save_api_keys(keys)
    return chosen["key"]

def rotate_key_handler(self):
    """Répond avec la prochaine clé API pour le client (sans exposer la clé en clair dans les logs)."""
    key = rotate_key()
    if not key:
        self._send_json({"error": "Aucune clé API disponible"}, 503)
        return
    # Ne renvoyer que les métadonnées, jamais la clé brute
    self._send_json({"status": "ok", "key_masked": key[:8] + "••••" + key[-4:] if len(key) > 12 else "****"})

# ─── Handler HTTP ───
class BridgeHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

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

    # ── Service du HTML (interface mobile) ──
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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]

        # ── Pages HTML (interface mobile) ──
        if path in ("/", "/index.html", "/mobile.html"):
            self.serve_html("mobile_index.html")
            return

        # Favicon
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

        # ── API publique (sans auth) ──
        if path == "/health":
            self._send_json({"name": "Vzlom Bridge v2.2", "status": "ok", "version": "2.2"})
            return

        if path == "/api/config":
            self._send_json({
                "openrouter_api_key": OPENROUTER_API_KEY,
                "models": {
                    "default": "google/gemini-2.0-flash-lite",
                    "fallbacks": ["deepseek/deepseek-chat", "mistralai/mistral-small-2501", "meta-llama/llama-3.2-3b-instruct"],
                }
            })
            return

        if path == "/api/keys/public":
            keys = load_all_api_keys()
            self._send_json({
                "count": len(keys),
                "ids": [k["id"] for k in keys],
                "models": {"default": "google/gemini-2.0-flash-lite",
                           "fallbacks": ["deepseek/deepseek-chat", "mistralai/mistral-small-2501", "meta-llama/llama-3.2-3b-instruct"]}
            })
            return

        # Rotation de clé (endpoint public, nécessaire pour mobile)
        if path == "/api/keys/next":
            rotate_key_handler(self)
            return

        # ── Routes protégées (auth) ──
        user = get_user_from_token(token) if token else None
        if not user:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        if path == "/api/logs":
            log_file = os.path.join(get_user_workspace(user), "vzlom.log")
            try:
                with open(log_file, "r") as f:
                    logs = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(logs.encode())
            except FileNotFoundError:
                self._send_json({"error": "No logs found"}, 404)
            return

        if path == "/memory":
            data = load_user_memory(user)
            self._send_json({"nickname": user, "count": len(data["entries"]), "entries": data["entries"][-50:]})
            return

        if path == "/tasks":
            data = load_user_tasks(user)
            self._send_json({"nickname": user, "count": len(data["tasks"]), "tasks": data["tasks"]})
            return

        if path == "/admin/keys":
            self.do_GET_admin_keys(user)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_GET_admin_keys(self, nickname):
        """GET /admin/keys — admin seulement."""
        if nickname != "admin":
            self._send_json({"error": "Admin required"}, 403)
            return
        safe_keys = []
        for k in load_all_api_keys():
            safe_keys.append({"id": k["id"], "source": k["source"], "created": k["created"],
                              "hits": k["hits"], "last_used": k["last_used"],
                              "masked": k["key"][:8] + "••••" + k["key"][-4:] if len(k["key"]) > 12 else "****"})
        self._send_json({"count": len(safe_keys), "keys": safe_keys})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        token = (params.get("token") or [None])[0]
        data = self._parse_body()

        # ── Auth ──
        if path == "/auth/register":
            nickname = (data.get("nickname") or "").strip()
            password = (data.get("password") or "").strip()
            github_token = (data.get("github_token") or "").strip()
            if len(nickname) < 2 or len(password) < 2:
                self._send_json({"error": "Surnom (2+) et mot de passe (2+) requis"}, 400); return
            if nickname in ("admin", "root"):
                self._send_json({"error": "Ce surnom est réservé"}, 400); return
            users = load_users()
            if nickname in users:
                self._send_json({"error": "Ce surnom existe déjà"}, 409); return
            users[nickname] = {"password": hash_password(password), "created": datetime.now().isoformat(), "github_token": github_token}
            save_users(users)
            self._send_json({"status": "ok", "nickname": nickname, "token": create_session(nickname)})
            return

        if path == "/auth/login":
            nickname = (data.get("nickname") or "").strip()
            password = (data.get("password") or "").strip()
            users = load_users()
            user = users.get(nickname)
            if not user: self._send_json({"error": "Utilisateur inconnu"}, 401); return
            if not verify_password(password, user["password"]): self._send_json({"error": "Mot de passe incorrect"}, 401); return
            self._send_json({"status": "ok", "nickname": nickname, "token": create_session(nickname), "github_token": user.get("github_token", "")})
            return

        if path == "/auth/check":
            nick = get_user_from_token(token)
            self._send_json({"status": "ok", "nickname": nick} if nick else {"status": "expired", "error": "Token invalide"}, 401 if not nick else 200)
            return

        # Protégé
        nickname = get_user_from_token(token) if token else None
        if not nickname:
            self._send_json({"error": "Unauthorized"}, 401); return

        if path == "/memory":
            entry = add_user_memory_entry(nickname, data.get("content", ""), data.get("source", "api"))
            self._send_json({"status": "saved", "nickname": nickname, "entry": entry}); return

        if path == "/memory/context":
            self._send_json({"nickname": nickname, "context": get_user_memory_context(nickname)}); return

        if path == "/bash":
            cmd = data.get("command", "")
            if not cmd: self._send_json({"error": "Commande requise"}, 400); return
            out, err = run_bash(cmd, nickname)
            self._send_json({"command": cmd, "output": out[:10000], "error": err, "nickname": nickname}); return

        if path == "/tasks":
            task = data.get("task", "")
            if not task: self._send_json({"error": "Description requise"}, 400); return
            self._send_json({"status": "created", "nickname": nickname, "task": add_user_task(nickname, task)}); return

        if path == "/tasks/complete":
            tid = data.get("id", "")
            tasks = load_user_tasks(nickname)
            for t in tasks["tasks"]:
                if t["id"] == tid: t["status"], t["result"] = "completed", (data.get("result", ""))[:2000]
            save_user_tasks(nickname, tasks)
            self._send_json({"status": "ok"}); return

        if path == "/logout":
            if token and token in SESSIONS: del SESSIONS[token]
            self._send_json({"status": "ok", "message": "Déconnecté"}); return

        if path == "/upload":
            import base64
            up = os.path.join(BASE_DIR, "uploads")
            os.makedirs(up, exist_ok=True)
            for name, b64 in (data.get("files") or {}).items():
                try:
                    with open(os.path.join(up, os.path.basename(name)), "wb") as f: f.write(base64.b64decode(b64))
                except: pass
            self._send_json({"status": "ok"}); return

        if path == "/admin/keys":
            if nickname != "admin": self._send_json({"error": "Admin required"}, 403); return
            new_key = (data.get("key") or "").strip()
            if not new_key: self._send_json({"error": "Clé requise"}, 400); return
            keys = load_all_api_keys()
            if any(k["key"] == new_key for k in keys): self._send_json({"error": "Doublon"}, 409); return
            keys.append({"id": secrets.token_hex(8), "key": new_key, "source": "admin", "created": datetime.now().isoformat(), "hits": 0, "last_used": 0})
            save_api_keys(keys)
            ALL_KEYS.clear(); ALL_KEYS.extend(keys)
            self._send_json({"status": "ok", "count": len(keys)}); return

        self._send_json({"error": "Not found"}, 404)

# ─── Lancement ───
if __name__ == "__main__":
    print(f"╔═══════════════════════════════════════╗")
    print(f"║  Vzlom Bridge v2.2 — Tout-en-un       ║")
    print(f"║  API + Mobile  sur le même port       ║")
    print(f"║  Port : {PORT:<31}║")
    print(f"║  🌐 http://0.0.0.0:{PORT}/             ║")
    print(f"╚═══════════════════════════════════════╝")
    http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler).serve_forever()