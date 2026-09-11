#!/bin/sh
# Installe piscine-ph pour le compte courant (macOS ou Linux).
# Ni Git ni un clone local ne sont nécessaires : uv construit l'archive du tag publié.
set -eu

release_version="v0.2.4"
source_url="https://github.com/frchalaoux/piscine-ph-tac/archive/refs/tags/${release_version}.tar.gz"

if command -v uv >/dev/null 2>&1; then
    uv_command="uv"
elif [ -x "$HOME/.local/bin/uv" ]; then
    uv_command="$HOME/.local/bin/uv"
else
    echo "Installation de uv..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "Erreur : curl ou wget est necessaire pour installer uv." >&2
        exit 1
    fi
    uv_command="$HOME/.local/bin/uv"
fi

if [ ! -x "$uv_command" ] && ! command -v "$uv_command" >/dev/null 2>&1; then
    echo "Erreur : uv est introuvable apres son installation." >&2
    exit 1
fi

echo "Installation de Python 3.11..."
"$uv_command" python install 3.11
"$uv_command" tool install --python 3.11 --reinstall "$source_url"

echo
if command -v piscine-ph >/dev/null 2>&1; then
    echo "piscine-ph est installe. Lancez : piscine-ph start"
else
    echo "piscine-ph est installe. Fermez et rouvrez le terminal, puis lancez : piscine-ph start"
fi
