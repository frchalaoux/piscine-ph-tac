# Objective

Faire évoluer `piscine-ph` vers des protocoles CLI distincts pour le pH, le
TAC et le désinfectant, sans transformer les FDS en consignes de dosage.

# Current Status

- Les modes `correction_hausse_tac`, `correction_baisse_ph` et
  `surveillance_desinfectant` complètent le parcours historique et restent
  persistés dans le JSON v6.
- Les galets au trichlore `GCCHL4EC` et `GCCHLLEC` sont des profils séparés.
  L'application conserve l'incompatibilité avec l'acide sulfurique et ne
  calcule jamais de quantité d'acide ou de galets sans notice de dosage.
- L'installateur Windows force désormais Python 3.11 afin de ne pas réutiliser
  un Python 3.10 incompatible.
- La branche `test-cli-windows` a été intégrée à `staging` par avance rapide au
  commit `866a01a` le 10 septembre 2026.
- Les releases `v0.2.0` à `v0.2.3` ont été publiées. La version `v0.2.3`,
  disponible sur `staging` et `origin/staging`, contient le parcours CLI pH bas
  et galets issu de `test-cli-windows`.

# Next Concrete Action

Recueillir le retour d'installation Windows de `v0.2.3`. Corriger localement,
tester et montrer le résultat à l'utilisateur ; ne publier qu'après son accord
explicite.

# Validation Snapshot

- Le 11 septembre 2026 : `uv run ruff check .` est vert et
  `uv run pytest -q` réussit avec 53 tests.
- `sh -n install.sh` est valide.

# Key Files

- `install.ps1`, `install.sh`
- `src/piscine_ph/cli.py`
- `src/piscine_ph/models.py`
- `src/piscine_ph/service.py`
- `docs/produits-et-securite.md`
- `docs/fichiers-json.md`

# Watchouts

- **Directive utilisateur prioritaire — « keep cool » : ne jamais créer,
  déplacer ou publier un tag, une release ou une mise à jour distante sans une
  demande explicite et distincte de l'utilisateur.** Préparer et tester est
  autorisé ; s'arrêter avant toute publication et demander confirmation.
- Ne pas supprimer les tags `v0.2.0`, `v0.2.1` ou `v0.2.2` : l'utilisateur a
  explicitement demandé de les conserver.
- Ne jamais proposer de mélange entre l'acide sulfurique et les galets au
  trichlore. Une FDS renseigne la sécurité, pas une posologie.
