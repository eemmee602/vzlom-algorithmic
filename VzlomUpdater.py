#!/usr/bin/env python3
"""
Vzlom Updater — Récupère les sources du repo, compile, crée un release .zip
Télécharge ce script sur le PC, double-clique, c'est fait.
"""
import urllib.request, json, base64, os, sys, subprocess, zipfile, shutil, tempfile, hashlib

REPO = "eemmee602/vzlom-algorithmic"
RELEASES_REPO = "eemmee602/vzlom-releases"
TOKEN = "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"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())

def get_file(path):
    data = get(f"https://api.github.com/repos/{REPO}/contents/{path}")
    if isinstance(data, dict) and data.get("type") == "file":
        req = urllib.request.Request(data["download_url"], headers=HEADERS)
        return urllib.request.urlopen(req, timeout=15).read()
    return None

def walk_tree(prefix, into_dir):
    items = get(f"https://api.github.com/repos/{REPO}/contents/{prefix}")
    if not isinstance(items, list):
        return
    for item in items:
        local_path = os.path.join(into_dir, item["path"])
        if item["type"] == "dir":
            os.makedirs(local_path, exist_ok=True)
            walk_tree(item["path"], into_dir)
        elif item["type"] == "file":
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            req = urllib.request.Request(item["download_url"], headers=HEADERS)
            content = urllib.request.urlopen(req, timeout=15).read()
            with open(local_path, "wb") as f:
                f.write(content)
            print(f"  ✓ {item['path']}")

def check_dotnet():
    try:
        r = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
        return r.returncode == 0 and r.stdout.strip()
    except:
        return None

def download_dotnet_instructions():
    print("\n⚠ .NET 8 n'est pas installé.")
    print("→ Télécharge-le ici : https://dotnet.microsoft.com/download/dotnet/8.0")
    print("→ Installe, puis relance ce script.\n")

def get_current_version(install_dir):
    path = os.path.join(install_dir, "version.txt")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return "none"

def save_version(install_dir, version):
    with open(os.path.join(install_dir, "version.txt"), "w") as f:
        f.write(version)

def get_latest_remote_version():
    try:
        releases = get(f"https://api.github.com/repos/{RELEASES_REPO}/releases")
        if releases and isinstance(releases, list):
            return releases[0].get("tag_name", "unknown")
    except:
        pass
    # Fallback: read from repo
    try:
        data = get(f"https://api.github.com/repos/{REPO}/contents/update.json")
        req = urllib.request.Request(data["download_url"], headers=HEADERS)
        content = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return content.get("version", "unknown")
    except:
        return "unknown"

def main():
    print("╔══════════════════════════════════════╗")
    print("║   Vzlom Updater v2.0                 ║")
    print("║   Mise à jour / installation auto    ║")
    print("╚══════════════════════════════════════╝\n")

    # Install dir = same folder as this script
    install_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    # Check .NET
    dotnet_ver = check_dotnet()
    if not dotnet_ver:
        download_dotnet_instructions()
        input("Appuie sur Entrée pour quitter...")
        sys.exit(1)
    print(f"✓ .NET {dotnet_ver} trouvé\n")

    # Check versions
    current = get_current_version(install_dir)
    latest = get_latest_remote_version()
    print(f"Version installée : {current}")
    print(f"Version disponible: {latest}\n")

    if current == latest and os.path.exists(os.path.join(install_dir, "Vzlom.exe")):
        print("✅ Vzlom est déjà à jour !")
        print(f"→ Lance : {os.path.join(install_dir, 'Vzlom.exe')}")
        input("\nAppuie sur Entrée pour quitter...")
        return

    print("📥 Téléchargement des sources depuis GitHub...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir, exist_ok=True)
        
        # Download all source files
        walk_tree("", tmpdir)
        
        # Build
        print("\n🔨 Compilation .NET 8...\n")
        csproj = os.path.join(tmpdir, "src", "Vzlom", "Vzlom.csproj")
        if not os.path.exists(csproj):
            print("❌ Vzlom.csproj introuvable")
            input("Appuie sur Entrée pour quitter...")
            sys.exit(1)
        
        result = subprocess.run(
            ["dotnet", "publish", csproj,
             "-c", "Release",
             "-r", "win-x64",
             "--self-contained", "false",
             "-o", os.path.join(tmpdir, "publish")],
            capture_output=False,
        )
        
        if result.returncode != 0:
            print("\n❌ Compilation échouée. Vérifie les erreurs ci-dessus.")
            input("Appuie sur Entrée pour quitter...")
            sys.exit(1)
        
        # Copy published files to install dir
        publish_dir = os.path.join(tmpdir, "publish")
        print(f"\n📦 Installation dans {install_dir}...")
        
        # Backup existing api_keys.json and user config
        config_files = ["api_keys.json", "ssh_config.json", "vzlom_memory.md", "permissions.json"]
        backups = {}
        for cf in config_files:
            path = os.path.join(install_dir, cf)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    backups[cf] = f.read()

        # Copy new files
        for item in os.listdir(publish_dir):
            src = os.path.join(publish_dir, item)
            dst = os.path.join(install_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
        
        # Also copy update.json and api_defaults.json
        for extra in ["update.json", "api_defaults.json"]:
            src = os.path.join(tmpdir, extra)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(install_dir, extra))
        
        # Restore config files
        for cf, content in backups.items():
            with open(os.path.join(install_dir, cf), "wb") as f:
                f.write(content)
            print(f"  ♻ Config préservée: {cf}")
        
        # Save version
        save_version(install_dir, latest)
    
    exe_path = os.path.join(install_dir, "Vzlom.exe")
    print(f"\n✅ Vzlom {latest} installé !")
    
    # Launch?
    launch = input("\nLancer Vzlom maintenant ? (O/n): ").strip().lower()
    if launch != "n":
        subprocess.Popen([exe_path])
        print("🚀 Lancé !")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAnnulé.")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback; traceback.print_exc()
        input("Appuie sur Entrée pour quitter...")
