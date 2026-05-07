<#
.SYNOPSIS
  Vzlom Updater — Télécharge, compile et installe Vzlom Algorithmic
.DESCRIPTION
  Script PowerShell autonome. Vérifie Python + .NET 8, télécharge
  les sources GitHub, compile, installe et lance Vzlom.
.NOTES
  Auteur : Hermès pour Emerick
  Date   : 2026-05-07
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Vzlom Updater"

Write-Host "╔" -NoNewline
Write-Host "══════════════════════════════════════" -NoNewline -ForegroundColor Cyan
Write-Host "╗" -NoNewline
Write-Host ""
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "    Vzlom Updater v2.0" -ForegroundColor White
Write-Host "║" -NoNewline -ForegroundColor Cyan
Write-Host "    Installation automatique PC" -ForegroundColor White
Write-Host "╚" -NoNewline
Write-Host "══════════════════════════════════════" -NoNewline -ForegroundColor Cyan
Write-Host "╝" -NoNewline
Write-Host ""
Write-Host ""

# ─── Dossier d'installation (là où est le script) ───
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = "." }
$InstallDir = $ScriptDir
Write-Host "📍 Dossier d'installation : $InstallDir" -ForegroundColor Gray

# ─── 1. Vérifier Python ───
Write-Host ""
Write-Host "─── 1/5  Python ───" -ForegroundColor Cyan

$python = (Get-Command "python" -ErrorAction SilentlyContinue) -or (Get-Command "python3" -ErrorAction SilentlyContinue)
$pythonPath = ""

if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $v = & python --version 2>&1
    Write-Host "  ✅ Python trouvé : $v" -ForegroundColor Green
    $pythonPath = "python"
}
elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $v = & python3 --version 2>&1
    Write-Host "  ✅ Python trouvé : $v" -ForegroundColor Green
    $pythonPath = "python3"
}
else {
    Write-Host "  ⏳ Python non trouvé. Téléchargement..." -ForegroundColor Yellow
    $pythonUrl = "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
    $installer = "$env:TEMP\python_installer.exe"
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing
        Write-Host "  📦 Installation de Python (silencieuse)..." -ForegroundColor Yellow
        Start-Process -Wait -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1"
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
        Write-Host "  ✅ Python installé !" -ForegroundColor Green
        $pythonPath = "python"
    }
    catch {
        Write-Host "  ❌ Échec du téléchargement de Python. Télécharge-le manuellement :" -ForegroundColor Red
        Write-Host "     https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "     (coche 'Add Python to PATH' pendant l'install)"
        Read-Host "     Appuie sur Entrée après avoir installé Python"
        $pythonPath = "python"
    }
}

# ─── 2. Vérifier .NET 8 SDK ───
Write-Host ""
Write-Host "─── 2/5  .NET 8 ───" -ForegroundColor Cyan

$dotnetVersion = ""
try {
    $dotnetVersion = & dotnet --version 2>&1
    Write-Host "  ✅ .NET trouvé : $dotnetVersion" -ForegroundColor Green
}
catch {
    Write-Host "  ⏳ .NET 8 SDK non trouvé." -ForegroundColor Yellow
    Write-Host "  🔗 Télécharge-le ici : https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor White
    Write-Host "     (prend le SDK, pas le Runtime)"
    Read-Host "     Appuie sur Entrée APRÈS avoir installé .NET 8 SDK"
    try {
        $dotnetVersion = & dotnet --version 2>&1
        Write-Host "  ✅ .NET $dotnetVersion OK" -ForegroundColor Green
    }
    catch {
        Write-Host "  ❌ .NET toujours pas trouvé. Installe-le puis relance le script." -ForegroundColor Red
        Read-Host "Appuie sur Entrée pour quitter"
        exit 1
    }
}

# ─── 3. Télécharger les sources ───
Write-Host ""
Write-Host "─── 3/5  Téléchargement des sources GitHub ───" -ForegroundColor Cyan

$srcDir = "$env:TEMP\vzlom_src"
if (Test-Path $srcDir) { Remove-Item -Recurse -Force $srcDir }
New-Item -ItemType Directory -Path $srcDir -Force | Out-Null

# Télécharger l'archive ZIP du repo
$zipUrl = "https://api.github.com/repos/eemmee602/vzlom-algorithmic/zipball/main"
$zipFile = "$env:TEMP\vzlom_src.zip"

try {
    $headers = @{ "Accept" = "application/vnd.github+json" }
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing -Headers $headers
    Expand-Archive -Path $zipFile -DestinationPath $srcDir -Force
    Remove-Item $zipFile -Force
    Write-Host "  ✅ Sources téléchargées" -ForegroundColor Green
}
catch {
    # Fallback: cloner avec git
    Write-Host "  ⏳ Téléchargement direct échoué, tentative avec git..." -ForegroundColor Yellow
    try {
        & git clone --depth 1 https://github.com/eemmee602/vzlom-algorithmic.git "$srcDir\repo" 2>&1
        $srcDir = "$srcDir\repo"
        Write-Host "  ✅ Clone git réussi" -ForegroundColor Green
    }
    catch {
        Write-Host "  ❌ Impossible de télécharger les sources : $_" -ForegroundColor Red
        Read-Host "Appuie sur Entrée pour quitter"
        exit 1
    }
}

# Trouver le dossier racine (GitHub zip ajoute un sous-dossier)
$rootDir = Get-ChildItem $srcDir -Directory | Select-Object -First 1 -ExpandProperty FullName
if (-not $rootDir) { $rootDir = $srcDir }

$csproj = Get-ChildItem -Path $rootDir -Recurse -Filter "Vzlom.csproj" | Select-Object -First 1 -ExpandProperty FullName
if (-not $csproj) {
    Write-Host "  ❌ Vzlom.csproj introuvable dans les sources" -ForegroundColor Red
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}
Write-Host "  📄 Projet : $csproj" -ForegroundColor Gray

# ─── 4. Compiler ───
Write-Host ""
Write-Host "─── 4/5  Compilation ───" -ForegroundColor Cyan

$publishDir = "$env:TEMP\vzlom_publish"
if (Test-Path $publishDir) { Remove-Item -Recurse -Force $publishDir }

try {
    Write-Host "  🔨 dotnet publish Release win-x64..." -ForegroundColor Yellow
    & dotnet publish $csproj -c Release -r win-x64 --self-contained false -o $publishDir
    if ($LASTEXITCODE -ne 0) { throw "dotnet publish a échoué (code $LASTEXITCODE)" }
    Write-Host "  ✅ Compilation réussie !" -ForegroundColor Green
}
catch {
    Write-Host "  ❌ Erreur de compilation : $_" -ForegroundColor Red
    Write-Host "  Essaie de compiler manuellement :" -ForegroundColor White
    Write-Host "     dotnet publish `"$csproj`" -c Release -r win-x64" -ForegroundColor White
    Read-Host "Appuie sur Entrée pour quitter"
    exit 1
}

# ─── 5. Installer ───
Write-Host ""
Write-Host "─── 5/5  Installation ───" -ForegroundColor Cyan

# Sauvegarder les configs existantes
$configFiles = @("api_keys.json", "ssh_config.json", "vzlom_memory.md", "permissions.json")
$backups = @{}
foreach ($cf in $configFiles) {
    $cfPath = Join-Path $InstallDir $cf
    if (Test-Path $cfPath) {
        $backups[$cf] = Get-Content $cfPath -Raw
        Write-Host "  ♻ Config préservée : $cf"
    }
}

# Copier les fichiers compilés
Get-ChildItem $publishDir | ForEach-Object {
    $dest = Join-Path $InstallDir $_.Name
    Copy-Item $_.FullName $dest -Force
}

# Copier aussi les fichiers auxiliaires
foreach ($extra in @("update.json", "api_defaults.json")) {
    $extraSrc = Join-Path (Split-Path $csproj -Parent) "..\$extra"
    if (Test-Path $extraSrc) {
        Copy-Item $extraSrc (Join-Path $InstallDir $extra) -Force
    }
}

# Restaurer les configs
foreach ($cf in $backups.Keys) {
    Set-Content -Path (Join-Path $InstallDir $cf) -Value $backups[$cf]
}

# Supprimer le dossier temporaire
Remove-Item -Recurse -Force $publishDir -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $srcDir -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ Vzlom installé dans :" -ForegroundColor Green
Write-Host "     $InstallDir" -ForegroundColor White
Write-Host "" -ForegroundColor White
Write-Host "  🚀 Pour lancer :" -ForegroundColor Green
Write-Host "     $(Join-Path $InstallDir 'Vzlom.exe')" -ForegroundColor White
Write-Host "══════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Proposer de lancer
$choice = Read-Host "  Lancer Vzlom maintenant ? (O/n)"
if ($choice -ne "n") {
    try {
        Start-Process (Join-Path $InstallDir "Vzlom.exe")
        Write-Host "  🚀 Vzlom lancé !" -ForegroundColor Green
    }
    catch {
        Write-Host "  Lance-le manuellement : $(Join-Path $InstallDir 'Vzlom.exe')" -ForegroundColor Yellow
    }
}

Read-Host "`nAppuie sur Entrée pour fermer"
