# Objective

Faire évoluer `piscine-ph` pour suivre le cas opposé au protocole historique :
pH au-dessus de la cible, TAC éventuellement différent de la cible et chlore
libre trop bas ou trop haut, avec électrolyse, régulateur de pH et galets dans
des états variables.

# Current Status

- Un parcours persistant `surveillance_ph_haut` a été ajouté, sans calcul de
  dose d'acide, de chlore ou de bicarbonate.
- Il archive pH, TAC et chlore libre via `record-water`, ainsi que les états de
  l'électrolyse, du régulateur pH et des galets stabilisés.
- Il émet des constats pour pH au-dessus de la cible/7,8, TAC différent de la
  cible, chlore hors bornes déclarées, électrolyse arrêtée et galets consommés.
- Une TUI Textual est désormais disponible via `piscine-ph tui` : menus par
  onglets (tableau de bord, mesures, traitement, historique, aide), avec les
  mêmes mutations de `ProtocolService` que la CLI.
- Les modifications sont locales et non committées à ce stade.

# Next Concrete Action

Relire le diff et la formulation des alertes, puis créer un commit dédié après
la validation complète si le comportement convient.

# Validation Snapshot

- `uv run ruff check .` : OK.
- `uv run pytest` : 25 passés, dont deux tests Textual.
- `uv build` et `git diff --check` : OK.
- Parcours CLI vérifié dans un répertoire temporaire : création de la
  surveillance, mesure pH 7,6 / TAC 70 / chlore libre 0,5, puis `status`.

# Key Files

- `src/piscine_ph/models.py`
- `src/piscine_ph/service.py`
- `src/piscine_ph/cli.py`
- `docs/surveillance-ph-haut-chlore.md`
- `docs/guide-utilisateur.md`
- `docs/guide-developpeur.md`
- `tests/test_service.py`

# Watchouts

- Les bornes de chlore sont archivées à partir de l'étiquette du produit ; le
  plancher de diagnostic passe à 2 ppm avec dichlore/trichlore stabilisé.
- Ne jamais convertir une alerte en dose d'acide ou de chlore : concentration,
  CYA, volume, appareil et notice sont indispensables.
- Les archives et le protocole historique de hausse pH/TAC restent lisibles et
  conservent leur comportement d'origine.
