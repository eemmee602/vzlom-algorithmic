<#
.SYNOPSIS
  Vzlom Updater v2.0 — Installation complète automatisée
.DESCRIPTION
  Vérifie Python, .NET 8, télécharge les sources GitHub,
  compile, installe et lance Vzlom Algorithmic.
  Nécessite : Windows 10+, internet.
  Fait TOUT tout seul.
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Vzlom Updater"

Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        Vzlom Algorithmic Updater v2.0        ║" -ForegroundColor White
Write-Host "║    Installation complète automatisée         ║" -ForegroundColor White
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) { $ScriptDir = Get-Location }
$InstallDir = $ScriptDir
Write-Host "  📂 Installation dans : $InstallDir" -ForegroundColor Gray

# ═══════════════════════════════════════════════════════
# 1/6 — VÉRIFIER / INSTALLER PYTHON
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [1/6] Python ───" -ForegroundColor Cyan

$python = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $v = & python --version 2>&1
    Write-Host "  ✅ Python : $v" -ForegroundColor Green
    $python = "python"
} else {
    Write-Host "  ⏳ Python non trouvé. Téléchargement..." -ForegroundColor Yellow
    $url = "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
    $exe = "$env:TEMP\python_installer.exe"
    try {
        Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
        Start-Process -Wait -FilePath $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1"
        # Rafraîchir le PATH
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
        Write-Host "  ✅ Python installé !" -ForegroundColor Green
        $python = "python"
    } catch {
        Write-Host "  ❌ Impossible de télécharger Python : $_" -ForegroundColor Red
        Write-Host "  Va sur https://www.python.org/downloads/, installe, puis relance"
        Read-Host "`nAppuie sur Entrée pour quitter"
        exit 1
    }
}

# ═══════════════════════════════════════════════════════
# 2/6 — VÉRIFIER .NET 8 SDK
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [2/6] .NET 8 SDK ───" -ForegroundColor Cyan

$dotnetOk = $false
try {
    $v = & dotnet --version 2>&1
    Write-Host "  ✅ .NET SDK : $v" -ForegroundColor Green
    $dotnetOk = $true
} catch {
    Write-Host "  ⏳ .NET 8 SDK non trouvé." -ForegroundColor Yellow
    Write-Host "  🔗 Télécharge depuis : https://dotnet.microsoft.com/en-us/download/dotnet/thank-you/sdk-8.0.404-windows-x64-installer" -ForegroundColor White
    Write-Host "     (SDK 8.0.404, pas Runtime)"
    Read-Host "  → Fais-le, puis appuie sur Entrée quand c'est installé"
    try {
        $v = & dotnet --version 2>&1
        Write-Host "  ✅ .NET SDK : $v" -ForegroundColor Green
        $dotnetOk = $true
    } catch {
        Write-Host "  ❌ Toujours pas trouvé. Relance le script après installation." -ForegroundColor Red
        Read-Host "Appuie sur Entrée pour quitter"
        exit 1
    }
}

# ═══════════════════════════════════════════════════════
# 3/6 — TÉLÉCHARGER LES SOURCES
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [3/6] Téléchargement des sources GitHub ───" -ForegroundColor Cyan

$tmpDir = "$env:TEMP\vzlom_$(Get-Random)"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$zipFile = "$tmpDir\source.zip"

try {
    # Token GitHub Emerick pour accès repo privé
    $headers = @{
        "Authorization" = "token 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"
        "Accept"        = "application/vnd.github+json"
        "User-Agent"    = "VzlomUpdater"
    }
    # Récupérer l'archive via l'API GitHub (fonctionne même avec repos privés)
    Invoke-WebRequest -Uri "https://api.github.com/repos/eemmee602/vzlom-algorithmic/zipball/main" `
                      -Headers $headers `
                      -OutFile $zipFile `
                      -UseBasicParsing
    
    Expand-Archive -Path $zipFile -DestinationPath $tmpDir -Force
    Remove-Item $zipFile -Force
    
    # Trouver le dossier racine (GitHub ajoute un sous-dossier)
    $rootDir = Get-ChildItem $tmpDir -Directory | Select-Object -First 1 -ExpandProperty FullName
    if (-not $rootDir) { throw "Archive vide" }
    
    # Trouver le .csproj
    $csproj = Get-ChildItem -Path $rootDir -Recurse -Filter "Vzlom.csproj" | Select-Object -First 1 -ExpandProperty FullName
    if (-not $csproj) { throw "Vzlom.csproj introuvable" }
    
    Write-Host "  ✅ Sources téléchargées (privé)"
    Write-Host "  📄 Projet : $csproj"
    
} catch {
    Write-Host "  ❌ Échec du téléchargement : $_" -ForegroundColor Red
    Write-Host "  Vérifie ta connexion internet ou le token GitHub."
    Read-Host "`nAppuie sur Entrée pour quitter"
    exit 1
}

# ═══════════════════════════════════════════════════════
# 4/6 — COMPILER
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [4/6] Compilation .NET 8 ───" -ForegroundColor Cyan

$publishDir = "$env:TEMP\vzlom_publish_$(Get-Random)"

try {
    Write-Host "  🔨 dotnet publish (Release, win-x64)..."
    $output = & dotnet publish $csproj -c Release -r win-x64 --self-contained false -o $publishDir 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ Erreur de compilation. Détails :" -ForegroundColor Red
        Write-Host $output
        throw "dotnet publish exit code: $LASTEXITCODE"
    }
    Write-Host "  ✅ Compilation réussie !" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Erreur : $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Astuce : essaie de compiler manuellement dans une console :"
    Write-Host "    cd `"$(Split-Path $csproj -Parent)`""
    Write-Host "    dotnet publish -c Release -r win-x64 --self-contained false"
    Read-Host "`nAppuie sur Entrée pour quitter"
    exit 1
}

# ═══════════════════════════════════════════════════════
# 5/6 — INSTALLER
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [5/6] Installation ───" -ForegroundColor Cyan

# Sauvegarder les fichiers de config existants
$configFiles = @("api_keys.json", "ssh_config.json", "vzlom_memory.md", "permissions.json")
$configBackups = @{}

foreach ($cf in $configFiles) {
    $cfPath = Join-Path $InstallDir $cf
    if (Test-Path $cfPath) {
        try {
            $configBackups[$cf] = Get-Content $cfPath -Raw
            Write-Host "  ♻ Config préservée : $cf"
        } catch {
            Write-Host "  ⚠ Impossible de lire : $cf"
        }
    }
}

# Copier les fichiers compilés
$fileCount = 0
Get-ChildItem $publishDir -File | ForEach-Object {
    $dest = Join-Path $InstallDir $_.Name
    Copy-Item $_.FullName $dest -Force
    $fileCount++
}

# Copier api_defaults.json et update.json
$sourceRoot = Split-Path $csproj -Parent
foreach ($extra in @("api_defaults.json", "update.json")) {
    $src = Join-Path $sourceRoot $extra
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $InstallDir $extra) -Force
        $fileCount++
    }
}

# Restaurer les configs
foreach ($cf in $configBackups.Keys) {
    Set-Content -Path (Join-Path $InstallDir $cf) -Value $configBackups[$cf] -NoNewline
}

Write-Host "  ✅ $fileCount fichiers copiés" -ForegroundColor Green
Write-Host "  📁 Destination : $InstallDir"

# ═══════════════════════════════════════════════════════
# 6/6 — NETTOYAGE + LANCEMENT
# ═══════════════════════════════════════════════════════
Write-Host "`n─── [6/6] Nettoyage ───" -ForegroundColor Cyan

Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $publishDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  ✅ Terminé"

# ─── Résumé ───
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "          ✅  VZLOM ALGORITHMIC  " -NoNewline -ForegroundColor Green
Write-Host "  ║" -ForegroundColor Cyan
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "                INSTALLÉ !             " -NoNewline -ForegroundColor White
Write-Host "  ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "  📂 $(Join-Path $InstallDir "Vzlom.exe")" -ForegroundColor White
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "  🔑 Ton compte :" -NoNewline -ForegroundColor Gray
Write-Host " Emerick / 2208" -NoNewline -ForegroundColor Cyan
Write-Host "          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$launch = Read-Host "  🚀 Lancer Vzlom maintenant ? (O/n)"
if ($launch -ne "n") {
    try {
        $exe = Join-Path $InstallDir "Vzlom.exe"
        Start-Process -FilePath $exe
        Write-Host "  🚀 Lancé !" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Lance-le manuellement : $(Join-Path $InstallDir 'Vzlom.exe')" -ForegroundColor Yellow
    }
}

Write-Host ""
Read-Host "Appuie sur Entrée pour fermer"
