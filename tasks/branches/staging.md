# Objective

Préserver le travail de reprise autour de la publication automatisée et de l'éventuelle prise en charge du carbonate de sodium (pH+).

# Current Status

- `scripts/release.py` publie vers `origin/<branche-courante>` plutôt que vers `origin/main` ; cette correction est validée dans `8ae7333`.
- La version `v0.1.1` a été publiée depuis `staging` (`8cb84de`) ; le HEAD courant est `a721f2d` et est en avance d'un commit sur `origin/staging` (`5b5bfd9`).
- `main` contient cet état après la fusion de la PR n° 6 (`f0ce158`).
- Une note technique de reprise sur le carbonate de sodium est dans `docs/evolution-carbonate-sodium.md`.
- Le programme ne prend pas encore en charge le carbonate : il ne faut pas l'utiliser comme équivalent direct de NaOH + bicarbonate.
- Les notes de reprise ont été commitées localement dans `a721f2d`, mais pas encore poussées sur `origin/staging`.
- Une release `v0.1.2` est interrompue après la mise à jour de ses six fichiers. `scripts/release.py` contient localement le correctif `uv.lock`/`--resume` ; voir `handoff.md`.

# Next Concrete Action

Commiter séparément le correctif de `scripts/release.py` et de sa documentation, puis reprendre `v0.1.2` avec `--publish --resume`. Dans un chantier distinct, concevoir et tester un calcul carbonate avant toute option CLI.

# Validation Snapshot

Après la correction de ciblage de branche : `uv run ruff check scripts/release.py` et `uv run pytest` passent (20 tests).

# Key Files

- `scripts/release.py`
- `docs/guide-developpeur.md`
- `docs/evolution-carbonate-sodium.md`
- `src/piscine_ph/chemistry.py`
- `src/piscine_ph/service.py`

# Watchouts

- Une release depuis `staging` doit pousser vers `origin/staging`, jamais automatiquement vers `origin/main`.
- Le carbonate de sodium augmente pH et TAC simultanément ; les doses NaOH et bicarbonate ne sont pas convertibles par simple règle de trois.
