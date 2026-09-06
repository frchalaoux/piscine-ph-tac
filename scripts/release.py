"""Prépare et publie une version taguée de piscine-ph.

Exemple : ``uv run python scripts/release.py 0.1.1 --publish``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
VERSION_FILES = (
    ROOT / "install.sh",
    ROOT / "install.ps1",
    ROOT / "README.md",
    ROOT / "docs/guide-utilisateur.md",
)


def run(*command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Exécute une commande depuis la racine du dépôt et l'affiche."""
    print("+", " ".join(command))
    return subprocess.run(command, cwd=ROOT, text=True, check=check)


def output(*command: str) -> str:
    """Retourne la sortie standard d'une commande Git."""
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def project_version() -> str:
    """Lit la version PEP 621 déclarée dans pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    match = re.search(r'^version = "(\d+\.\d+\.\d+)"$', pyproject.read_text(), re.MULTILINE)
    if not match:
        raise RuntimeError("Version introuvable ou non conforme dans pyproject.toml.")
    return match.group(1)


def replace_exactly_once(path: Path, old: str, new: str) -> None:
    """Remplace une valeur unique et échoue si le fichier n'est pas celui attendu."""
    content = path.read_text()
    if content.count(old) != 1:
        raise RuntimeError(f"{path.relative_to(ROOT)} doit contenir une seule fois {old!r}.")
    path.write_text(content.replace(old, new), encoding="utf-8")


def update_version_files(previous: str, current: str) -> None:
    """Met à jour les métadonnées et toutes les références au tag de release."""
    replace_exactly_once(ROOT / "pyproject.toml", f'version = "{previous}"', f'version = "{current}"')
    for path in VERSION_FILES:
        content = path.read_text()
        previous_tag = f"v{previous}"
        if previous_tag not in content:
            raise RuntimeError(f"Référence {previous_tag!r} absente de {path.relative_to(ROOT)}.")
        path.write_text(content.replace(previous_tag, f"v{current}"), encoding="utf-8")


def require_tools() -> None:
    """Vérifie que les outils requis sont accessibles avant toute modification."""
    missing = [tool for tool in ("git", "gh", "uv") if shutil.which(tool) is None]
    if missing:
        raise RuntimeError("Outil(s) manquant(s) : " + ", ".join(missing))


def ensure_release_is_possible(tag: str, *, require_clean_tree: bool) -> None:
    """Contrôle l'état Git et évite d'écraser main ou un tag existant."""
    if require_clean_tree and output("git", "status", "--porcelain"):
        raise RuntimeError("Le répertoire de travail doit être propre avant une release.")
    run("git", "fetch", "origin", "main", "--tags")
    merged = run("git", "merge-base", "--is-ancestor", "origin/main", "HEAD", check=False)
    if merged.returncode:
        raise RuntimeError("HEAD doit contenir origin/main avant de publier.")
    local_tag = run("git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False)
    remote_tag = run("git", "ls-remote", "--exit-code", "--tags", "origin", tag, check=False)
    if not local_tag.returncode or not remote_tag.returncode:
        raise RuntimeError(f"Le tag {tag} existe déjà.")


def release_notes(version: str) -> str:
    """Construit les notes courtes et les commandes d'installation de la release."""
    tag = f"v{version}"
    base = f"https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/{tag}"
    return (
        f"Version {version}.\n\n"
        "Installation macOS/Linux :\n"
        f"`curl -LsSf {base}/install.sh | sh`\n\n"
        "Installation Windows PowerShell :\n"
        f"`irm {base}/install.ps1 | iex`"
    )


def publish(version: str) -> None:
    """Modifie, vérifie et publie la version demandée."""
    previous = project_version()
    if version == previous:
        raise RuntimeError(f"La version demandée est déjà {version}.")
    tag = f"v{version}"
    ensure_release_is_possible(tag, require_clean_tree=True)
    update_version_files(previous, version)
    run("uv", "run", "ruff", "check", ".")
    run("uv", "run", "pytest")
    run("uv", "build")
    run("git", "diff", "--check")
    run("git", "add", "pyproject.toml", "install.sh", "install.ps1", "README.md", "docs/guide-utilisateur.md")
    run("git", "commit", "-m", f"release: preparer la version {version}")
    run("git", "push", "origin", "HEAD:main")
    run("git", "tag", "-a", tag, "-m", f"Version {version}")
    run("git", "push", "origin", tag)
    run("gh", "release", "create", tag, "--title", f"piscine-ph {tag}", "--notes", release_notes(version))
    print(f"Release publiée : https://github.com/frchalaoux/piscine-ph-tac/releases/tag/{tag}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version cible au format X.Y.Z, par exemple 0.1.1.")
    parser.add_argument(
        "--publish", action="store_true", help="Applique les modifications et publie la release."
    )
    args = parser.parse_args()
    if not VERSION_PATTERN.fullmatch(args.version):
        parser.error("La version doit respecter le format X.Y.Z, par exemple 0.1.1.")
    try:
        require_tools()
        if args.publish:
            publish(args.version)
        else:
            print("Simulation uniquement : aucune modification ni publication.")
            print(f"La publication créerait le tag v{args.version} depuis le commit courant.")
            ensure_release_is_possible(f"v{args.version}", require_clean_tree=False)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
