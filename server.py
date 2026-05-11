#!/usr/bin/env python3
"""
Vzlom Bridge v2.1 — Multi-user, auth, mémoire isolée, auto-agent loop
Serveur API REST minimal (zéro dépendance).
Port : 3456
"""
import http.server, json, subprocess, os, hashlib, uuid, secrets, time
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import importlib
import sys
from dotenv import load_dotenv

# ─── Config ───
PORT = 3456
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WORKSPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
KEYS_FILE = os.path.join(DATA_DIR, "keys.json")
SESSIONS = {}  # {token: nickname, created_at} — en mémoire, pas persistant

# Charger .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Clés API — chargement depuis .env (clé unique) + keys.json (multi-clés)
def load_all_api_keys():
    """Charge toutes les clés API disponibles. Retourne une liste de {id, key, source, created, hits, last_used}."""
    keys = []
    # Clé .env principale
    env_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if env_key:
        keys.append({"id": "env", "key": env_key, "source": "env", "created": "env", "hits": 0, "last_used": 0})
    # Clés depuis keys.json
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
    """Sauvegarde les clés dans keys.json (sans la clé env)."""
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

# Initialiser keys.json si inexistant
if not os.path.exists(KEYS_FILE):
    save_api_keys(ALL_KEYS)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# ─── Users DB ───
def load_users():
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password, stored):
    salt, h = stored.split("$", 1)
    return hash_password(password, salt) == stored

def create_session(nickname):
    token = "vzlom_" + secrets.token_hex(24)
    SESSIONS[token] = {"nickname": nickname, "created": time.time()}
    return token

def get_user_from_token(token):
    """Retourne le nickname ou None si token invalide."""
    session = SESSIONS.get(token)
    if not session:
        return None
    if time.time() - session["created"] > 86400:
        del SESSIONS[token]
        return None
    return session["nickname"]

# ─── Per-user memory ───
def get_user_memory_file(nickname):
    return os.path.join(DATA_DIR, f"memory_{nickname}.json")

def load_user_memory(nickname):
    path = get_user_memory_file(nickname)
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {"nickname": nickname, "entries": []}

def save_user_memory(nickname, data):
    path = get_user_memory_file(nickname)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_user_memory_entry(nickname, content, source="user"):
    data = load_user_memory(nickname)
    data["entries"].append({
        "content": content[:2000],
        "source": source,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    if len(data["entries"]) > 10000:
        data["entries"] = data["entries"][-10000:]
    save_user_memory(nickname, data)
    return data["entries"][-1]

def get_user_memory_context(nickname, recent=30):
    data = load_user_memory(nickname)
    entries = data["entries"][-recent:]
    if not entries:
        return "Aucune mémoire."
    lines = [f"[{e['timestamp']}] {e['source']}: {e['content'][:200]}" if len(e['content']) > 200 else f"[{e['timestamp']}] {e['source']}: {e['content']}" for e in entries]
    return "\n".join(lines)

# ─── Per-user workspace ───
def get_user_workspace(nickname):
    path = os.path.join(WORKSPACE, nickname)
    os.makedirs(path, exist_ok=True)
    return path

def get_user_github_token(nickname):
    data = load_users()
    user = data.get(nickname, {})
    return user.get("github_token") or user.get("github")

# ─── Bash (sandboxé par user) ───
BLACKLIST = ["rm -rf /", "sudo", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]

def run_bash(command, nickname):
    import subprocess
    for d in BLACKLIST:
        if d in command.lower():
            return f"BLOCKED: Commande interdite ({d})", True
    cwd = get_user_workspace(nickname)
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd,
            env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin",
                 "VZLOM_USER": nickname}
        )
        output = result.stdout
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        return output, (result.returncode != 0)
    except subprocess.TimeoutExpired:
        return "TIMEOUT: 30s", True
    except Exception as e:
        return f"ERROR: {e}", True

# ─── Task queue (auto-agent loop) ───
def get_user_task_file(nickname):
    return os.path.join(DATA_DIR, f"tasks_{nickname}.json")

def load_user_tasks(nickname):
    path = get_user_task_file(nickname)
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {"tasks": []}

def save_user_tasks(nickname, data):
    path = get_user_task_file(nickname)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_user_task(nickname, task):
    data = load_user_tasks(nickname)
    data["tasks"].append({
        "id": str(uuid.uuid4())[:8],
        "task": task[:500],
        "status": "pending",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "result": "",
    })
    save_user_tasks(nickname, data)
    return data["tasks"][-1]

# ─── Serveur HTTP ───
class BridgeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _parse_body(self):
        """Parse le body JSON d'une requête POST/PUT."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]

        # Favicon — éviter le 404 bruyant
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # Auth check
        user = get_user_from_token(token) if token else None
        if not user and path not in ["/auth/login", "/auth/register", "/health", "/api/config", "/api/keys/public"]:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        # API config (accessible sans auth)
        if path == "/api/config":
            self._send_json({
                "openrouter_api_key": OPENROUTER_API_KEY,
                "models": {
                    "default": "google/gemini-2.0-flash-lite",
                    "fallbacks": [
                        "deepseek/deepseek-chat",
                        "mistralai/mistral-small-2501",
                        "meta-llama/llama-3.2-3b-instruct",
                    ]
                }
            })
            return

        # Clés publiques (sans la clé elle-même)
        if path == "/api/keys/public":
            keys = load_all_api_keys()
            self._send_json({
                "count": len(keys),
                "ids": [k["id"] for k in keys],
                "models": {
                    "default": "google/gemini-2.0-flash-lite",
                    "fallbacks": [
                        "deepseek/deepseek-chat",
                        "mistralai/mistral-small-2501",
                        "meta-llama/llama-3.2-3b-instruct",
                    ]
                }
            })
            return

        if path == "/api/logs":
            if not user:
                self._send_json({"error": "Unauthorized"}, 401)
                return
            log_file = os.path.join(get_user_workspace(user), "vzlom.log")
            try:
                with open(log_file, "r") as f:
                    logs = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(logs.encode())
            except FileNotFoundError:
                self._send_json({"error": "No logs found"}, 404)
            return

        # ── Routes standard ──
        if path == "/" or path == "/health":
            self._send_json({
                "name": "Vzlom Bridge v2.1",
                "status": "ok",
                "version": "2.1",
                "endpoints": {
                    "POST /auth/register": "Créer un compte",
                    "POST /auth/login": "Se connecter",
                    "GET /health": "Test connexion",
                    "GET /api/config": "Config API (sans auth)",
                    "GET /api/keys/public": "Liste clés publiques (sans auth)",
                    "GET /api/logs?token=X": "Voir logs (auth)",
                    "GET /memory?token=X": "Voir mémoire (auth)",
                    "POST /memory": "Ajouter mémoire (auth)",
                    "POST /bash": "Exécuter bash (auth)",
                    "GET /tasks?token=X": "Voir tâches (auth)",
                    "POST /tasks": "Ajouter une tâche (auth)",
                    "POST /admin/keys?token=X": "Ajouter une clé API (admin)",
                    "GET /admin/keys?token=X": "Lister les clés API (admin)",
                }
            })
            return

        if path == "/memory":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide ou expiré. Re-login."}, 401)
                return
            data = load_user_memory(nickname)
            recent = data["entries"][-50:]
            self._send_json({
                "nickname": nickname,
                "count": len(data["entries"]),
                "entries": recent
            })
            return

        if path == "/tasks":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            data = load_user_tasks(nickname)
            self._send_json({
                "nickname": nickname,
                "count": len(data["tasks"]),
                "tasks": data["tasks"]
            })
            return

        self._send_json({"error": "Not found"}, 404)

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
                self._send_json({"error": "Surnom (2+) et mot de passe (2+) requis"}, 400)
                return
            if nickname == "admin" or nickname == "root":
                self._send_json({"error": "Ce surnom est réservé"}, 400)
                return
            users = load_users()
            if nickname in users:
                self._send_json({"error": "Ce surnom existe déjà"}, 409)
                return
            users[nickname] = {
                "password": hash_password(password),
                "created": datetime.now().isoformat(),
                "github_token": github_token,
            }
            save_users(users)
            token = create_session(nickname)
            self._send_json({"status": "ok", "nickname": nickname, "token": token})

        elif path == "/auth/login":
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
            token = create_session(nickname)
            self._send_json({
                "status": "ok", "nickname": nickname, "token": token,
                "github_token": user.get("github_token", ""),
            })

        elif path == "/auth/check":
            """Vérifie si un token est toujours valide."""
            nickname = get_user_from_token(token)
            if nickname:
                self._send_json({"status": "ok", "nickname": nickname})
            else:
                self._send_json({"status": "expired", "error": "Token expiré ou invalide"}, 401)

        # ── Memory ──
        elif path == "/memory":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            content = data.get("content", "")
            source = data.get("source", "api")
            entry = add_user_memory_entry(nickname, content, source)
            self._send_json({"status": "saved", "nickname": nickname, "entry": entry})

        elif path == "/memory/context":
            """Récupère le contexte mémoire formaté pour le system prompt."""
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            context = get_user_memory_context(nickname)
            self._send_json({"nickname": nickname, "context": context})

        # ── Bash ──
        elif path == "/bash":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            command = data.get("command", "")
            if not command:
                self._send_json({"error": "Commande requise"}, 400)
                return
            output, is_error = run_bash(command, nickname)
            self._send_json({
                "command": command, "output": output[:10000],
                "error": is_error, "nickname": nickname
            })

        # ── Tasks (auto-agent) ──
        elif path == "/tasks":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            task = data.get("task", "")
            if not task:
                self._send_json({"error": "Description de tâche requise"}, 400)
                return
            entry = add_user_task(nickname, task)
            self._send_json({"status": "created", "nickname": nickname, "task": entry})

        elif path == "/tasks/complete":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            task_id = data.get("id", "")
            result = data.get("result", "")
            tasks_data = load_user_tasks(nickname)
            for t in tasks_data["tasks"]:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    t["result"] = result[:2000]
                    break
            save_user_tasks(nickname, tasks_data)
            self._send_json({"status": "ok"})

        elif path == "/logout":
            """Déconnecter (supprimer la session)."""
            if token and token in SESSIONS:
                del SESSIONS[token]
            self._send_json({"status": "ok", "message": "Déconnecté"})

        # ── Upload ──
        elif path == "/upload":
            import base64
            upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            files_uploaded = data.get("files", {})
            if not files_uploaded:
                self._send_json({"error": "Aucun fichier. Envoie {files: {nom: base64, ...}}"})
                return
            results = []
            for name, b64_content in files_uploaded.items():
                try:
                    raw = base64.b64decode(b64_content)
                    safe_name = os.path.basename(name.replace("\\", "/"))
                    dest = os.path.join(upload_dir, safe_name)
                    with open(dest, "wb") as f:
                        f.write(raw)
                    results.append(f"{safe_name} ({len(raw)} bytes)")
                except Exception as e:
                    results.append(f"{name}: {e}")
            self._send_json({"status": "ok", "files": results, "total": len(files_uploaded)})

        elif path == "/upload/list":
            upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            files = []
            for f in os.listdir(upload_dir):
                fp = os.path.join(upload_dir, f)
                if os.path.isfile(fp):
                    files.append({"name": f, "size": os.path.getsize(fp), "modified": os.path.getmtime(fp)})
            self._send_json({"files": files})

        # ── Admin: Gestion des clés API ──
        elif path == "/admin/keys":
            nickname = get_user_from_token(token)
            if not nickname:
                self._send_json({"error": "Token invalide"}, 401)
                return
            if nickname != "admin":
                self._send_json({"error": "Accès admin requis"}, 403)
                return
            # GET /admin/keys — lister
            if self.command == "GET":
                keys = load_all_api_keys()
                safe_keys = []
                for k in keys:
                    safe_keys.append({
                        "id": k["id"],
                        "source": k["source"],
                        "created": k["created"],
                        "hits": k["hits"],
                        "last_used": k["last_used"],
                        "masked": k["key"][:8] + "••••" + k["key"][-4:] if len(k["key"]) > 12 else "****"
                    })
                self._send_json({"count": len(safe_keys), "keys": safe_keys})
                return
            # POST /admin/keys — ajouter
            elif self.command == "POST":
                new_key = (data.get("key") or "").strip()
                if not new_key:
                    self._send_json({"error": "Clé API requise"}, 400)
                    return
                if len(new_key) < 10:
                    self._send_json({"error": "Clé trop courte"}, 400)
                    return
                keys = load_all_api_keys()
                # Vérifier doublon
                for k in keys:
                    if k["key"] == new_key:
                        self._send_json({"error": "Clé déjà existante"}, 409)
                        return
                keys.append({
                    "id": secrets.token_hex(8),
                    "key": new_key,
                    "source": "admin",
                    "created": datetime.now().isoformat(),
                    "hits": 0,
                    "last_used": 0,
                })
                save_api_keys(keys)
                ALL_KEYS.clear()
                ALL_KEYS.extend(keys)
                self._send_json({"status": "ok", "count": len(keys)})
                return

        # ── Upload list legacy ──
        else:
            self._send_json({"error": "Not found"}, 404)

# ─── Lancement ───
if __name__ == "__main__":
    print(f"╔═══════════════════════════════════════╗")
    print(f"║  Vzlom Bridge v2.1                    ║")
    print(f"║                                       ║")
    print(f"║  🔑 Auth     : POST /auth/register    ║")
    print(f"║  🔑         : POST /auth/login        ║")
    print(f"║  🌐 Mémoire  : /memory?token=X        ║")
    print(f"║  ⚡ Bash      : POST /bash?token=X    ║")
    print(f"║  📋 Tâches   : /tasks?token=X          ║")
    print(f"║  📂 Workspace: {WORKSPACE}/{{user}}        ║")
    print(f"║  🔑 Clés API : /admin/keys             ║")
    print(f"║  🚫 ISOLÉ des projets MDT              ║")
    print(f"╚═══════════════════════════════════════╝")

    server = http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    server.serve_forever()