# Objective

Préserver le travail de reprise autour de la publication automatisée et de l'éventuelle prise en charge du carbonate de sodium (pH+).

# Current Status

- `scripts/release.py` publie vers `origin/<branche-courante>` plutôt que vers `origin/main` ; cette correction est validée dans `8ae7333`.
- La version `v0.1.1` a été publiée depuis `staging` (`8cb84de`) ; le HEAD courant est `5b5bfd9` (`version adjustement`).
- `main` contient cet état après la fusion de la PR n° 6 (`f0ce158`).
- Une note technique de reprise sur le carbonate de sodium est dans `docs/evolution-carbonate-sodium.md`.
- Le programme ne prend pas encore en charge le carbonate : il ne faut pas l'utiliser comme équivalent direct de NaOH + bicarbonate.
- Les notes de reprise `docs/evolution-carbonate-sodium.md`, `docs/guide-developpeur.md`, `tasks/branches/staging.md` et `handoff.md` sont locales et non commitées.

# Next Concrete Action

Décider si les notes locales de documentation/reprise doivent être validées sur `staging`, puis, dans un chantier distinct, concevoir et tester un calcul carbonate avant toute option CLI.

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
