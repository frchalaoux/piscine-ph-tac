# Installe piscine-ph pour le compte courant (Windows PowerShell).
# Ni Git ni un clone local ne sont nécessaires : uv construit l'archive du tag publié.
$ErrorActionPreference = "Stop"

$releaseVersion = "v0.2.0"
$sourceUrl = "https://github.com/frchalaoux/piscine-ph-tac/archive/refs/tags/$releaseVersion.tar.gz"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvCommand = "uv"
}
else {
    Write-Host "Installation de uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $uvPath = Join-Path $HOME ".local\\bin\\uv.exe"
    if (-not (Test-Path $uvPath)) {
        throw "uv est introuvable apres son installation."
    }
    $uvCommand = $uvPath
}

& $uvCommand tool install --reinstall $sourceUrl
if ($LASTEXITCODE -ne 0) {
    throw "L'installation de piscine-ph a échoué (code $LASTEXITCODE)."
}

Write-Host ""
if (Get-Command piscine-ph -ErrorAction SilentlyContinue) {
    Write-Host "piscine-ph est installe. Lancez : piscine-ph start"
}
else {
    Write-Host "piscine-ph est installe. Fermez et rouvrez PowerShell, puis lancez : piscine-ph start"
}
