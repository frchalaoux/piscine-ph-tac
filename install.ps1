# Installe piscine-ph pour le compte courant (Windows PowerShell).
$ErrorActionPreference = "Stop"

$repositoryUrl = "git+https://github.com/frchalaoux/piscine-ph-tac.git@main"

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

& $uvCommand tool install --reinstall $repositoryUrl
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
if (Get-Command piscine-ph -ErrorAction SilentlyContinue) {
    Write-Host "piscine-ph est installe. Lancez : piscine-ph start"
}
else {
    Write-Host "piscine-ph est installe. Fermez et rouvrez PowerShell, puis lancez : piscine-ph start"
}
