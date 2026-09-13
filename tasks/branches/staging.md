# Objective

Fiabiliser les parcours TUI et conserver un contexte d'installation explicite
avant tout nouveau protocole pH, TAC, désinfection, mesure ou étude carbonate.

# Current Status

- **v0.2.5 publiée le 13 septembre 2026**, à la demande explicite de l'utilisateur.
- Commit fonctionnel `9a5a750`, branche distante `feat/sodium-carbonate-model`.
- Fusion dans `staging` : `e25c03a` ; commit de release `feba09e`, tag annoté `v0.2.5`.
- La source de désinfection et les trois états d'appareils sont obligatoires
  avant toute création. Le contexte est repris lors des enchaînements et les
  anciennes archives restent consultables.
- Les boutons de navigation après correction sont corrigés. La désinfection
  affiche le bilan enregistré et permet de clôturer le suivi pour choisir la suite.
- Les archives affichent mesures, seuils min/max et chemin du fichier.
- L'étude carbonate et la recherche manuelle de FDS sont documentées ; aucune
  dose opérationnelle de carbonate n'est créée.

# Next Concrete Action

Recueillir le retour utilisateur sur le parcours publié : déclaration initiale,
correction pH, bilan de désinfection et consultation des archives.
Lire `handoff.md` pour les détails et les limites des parcours.

# Validation Snapshot

- `uv run ruff check .` : vert.
- Suite complète au moment de publier : **113 passed**.
- `uv build` et `git diff --check` : verts ; distributions `0.2.5` construites.
- Installation isolée depuis l'archive du tag `v0.2.5` sous Python 3.11 :
  lancement de `piscine-ph --help` réussi.
- Aucun nouveau test Windows manuel effectué ; l'installation Windows de
  v0.2.4 avait été validée par un utilisateur.

# Watchouts

- **Keep cool** : aucune nouvelle publication distante sans une demande
  explicite, séparée et actuelle. L'autorisation de publier v0.2.5 est exécutée.
- Ne pas modifier ni supprimer les tags existants, notamment v0.2.0 à v0.2.2.
- Les données restent dans `data/protocoles`, relatif au dossier de lancement.
- Ne pas déduire une dose de carbonate de doses de soude et de bicarbonate.
- Ne jamais proposer de mélange entre acide sulfurique et galets au trichlore.
