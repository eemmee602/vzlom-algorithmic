#!/usr/bin/env python3
"""
Vzlom Bridge v2.0 — Multi-user, auth, mémoire isolée, auto-agent loop
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
SESSIONS = {}  # {token: nickname, created_at} — en mémoire, pas persistant

# Charger .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Clés API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)

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
    # Session expire après 24h
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
    """Cherche le token GitHub stocké pour cet utilisateur."""
    data = load_users()
    user = data.get(nickname, {})
    return user.get("github_token") or user.get("github")

# ─── Bash (sandboxé par user) ───
BLACKLIST = ["rm -rf /", "sudo", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]

def run_bash(command, nickname):
    """Exécute une commande bash dans le workspace isolé de l'utilisateur."""
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

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = qs.get("token", [""])[0]

        # Auth check
        user = get_user_from_token(token) if token else None
        if not user and path not in ["/auth/login", "/auth/register", "/health", "/api/config"]:
            self._send_json({"error": "Unauthorized"}, 401)
            return

        # API Endpoints
        if path == "/api/config":
            self._send_json({
                "openrouter_api_key": OPENROUTER_API_KEY,
                "models": {
                    "default": "google/gemini-2.0-flash-lite",
                    "fallbacks": ["deepseek/deepseek-chat", "mistralai/mistral-small-2501"]
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
                self.end_headers()
                self.wfile.write(logs.encode())
            except FileNotFoundError:
                self._send_json({"error": "No logs found"}, 404)
            return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _parse_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(body)
        except:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        token = (params.get("token") or [None])[0]

        if path == "/":
            self._send_json({
                "name": "Vzlom Bridge v2.0",
                "endpoints": {
                    "POST /auth/register": "Créer un compte",
                    "POST /auth/login": "Se connecter",
                    "GET /health": "Test connexion",
                    "GET /memory?token=X": "Voir mémoire (auth)",
                    "POST /memory": "Ajouter mémoire (auth)",
                    "POST /bash": "Exécuter bash (auth)",
                    "GET /tasks?token=X": "Voir tâches (auth)",
                    "POST /tasks": "Ajouter une tâche (auth)",
                }
            })
        
        elif path == "/health":
            user_count = len(load_users())
            session_count = len(SESSIONS)
            self._send_json({
                "status": "ok", "version": "2.0",
                "users": user_count, "sessions": session_count,
                "time": datetime.now().isoformat()
            })

        elif path == "/memory":
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

        elif path == "/tasks":
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

        else:
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
                "github_token": data.get("github_token", ""),
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
            import base64, os
            # Accept base64 files in JSON
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
        
        # ── Upload list ──
        elif path == "/upload/list":
            upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            files = []
            for f in os.listdir(upload_dir):
                fp = os.path.join(upload_dir, f)
                if os.path.isfile(fp):
                    files.append({"name": f, "size": os.path.getsize(fp), "modified": os.path.getmtime(fp)})
            self._send_json({"files": files})

        else:
            self._send_json({"error": "Not found"}, 404)


# ─── Lancement ───
if __name__ == "__main__":
    print(f"╔═══════════════════════════════════════╗")
    print(f"║  Vzlom Bridge v2.0                    ║")
    print(f"║                                       ║")
    print(f"║  🔑 Auth     : POST /auth/register    ║")
    print(f"║  🔑         : POST /auth/login        ║")
    print(f"║  🌐 Mémoire  : /memory?token=X        ║")
    print(f"║  ⚡ Bash      : POST /bash?token=X    ║")
    print(f"║  📋 Tâches   : /tasks?token=X          ║")
    print(f"║  📂 Workspace: {WORKSPACE}/{{user}}        ║")
    print(f"║  🚫 ISOLÉ des projets MDT              ║")
    print(f"╚═══════════════════════════════════════╝")

    server = http.server.HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    server.serve_forever()
