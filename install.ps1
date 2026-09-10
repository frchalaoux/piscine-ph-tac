# Installe la branche de test piscine-ph pour le compte courant (Windows PowerShell).
# Ni Git ni un clone local ne sont nécessaires : uv construit l'archive de la branche.
$ErrorActionPreference = "Stop"

$testBranch = "test-cli-windows"
$sourceUrl = "https://github.com/frchalaoux/piscine-ph-tac/archive/refs/heads/$testBranch.tar.gz"

Write-Host "Installation de la version de TEST piscine-ph ($testBranch)..." -ForegroundColor Yellow

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

Write-Host "Installation de Python 3.11..."
& $uvCommand python install 3.11
if ($LASTEXITCODE -ne 0) {
    throw "L'installation de Python 3.11 a échoué (code $LASTEXITCODE)."
}

& $uvCommand tool install --python 3.11 --reinstall $sourceUrl
if ($LASTEXITCODE -ne 0) {
    throw "L'installation de piscine-ph a échoué (code $LASTEXITCODE)."
}

Write-Host ""
if (Get-Command piscine-ph -ErrorAction SilentlyContinue) {
    Write-Host "Version de TEST installee. Lancez : piscine-ph start"
}
else {
    Write-Host "Version de TEST installee. Fermez et rouvrez PowerShell, puis lancez : piscine-ph start"
}
