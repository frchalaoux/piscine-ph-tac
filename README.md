# piscine-ph

Outil en ligne de commande pour suivre une correction progressive du pH et du TAC d'une piscine.

## Installation et lancement

Sur une machine sans Python ni `uv`, suivre d'abord le [protocole d'installation complet](docs/guide-utilisateur.md#installer-lapplication) : `uv` installe ensuite une version de Python pour le projet.

```bash
uv sync
uv run piscine-ph start
uv run piscine-ph status
uv run piscine-ph menu
```

Le suivi est stocke dans `data/protocoles/` : chaque protocole est archive dans son propre fichier JSON date.

Voir le [guide utilisateur](docs/guide-utilisateur.md) pour l'utilisation pas a pas, la [documentation technique](docs/protocole_ph_tac.md) pour les calculs et limites scientifiques, et le [guide développeur](docs/guide-developpeur.md) pour l'architecture et la maintenance.
Les paramètres par défaut versionnés sont décrits dans la [documentation de configuration](docs/configuration.md).
La structure et la lecture des paramètres et archives sont détaillées dans la [référence des fichiers JSON](docs/fichiers-json.md).
Pour apprendre rapidement les bases pH/TAC, lire aussi le [guide de chimie](docs/comprendre-la-chimie.md).
Le cas temporaire « électrolyse arrêtée et galets stabilisés » est traité dans le [guide dédié](docs/traitement-chlore-stabilise.md).

## Commandes principales

```bash
uv run piscine-ph start
uv run piscine-ph dose
uv run piscine-ph cancel-dose
uv run piscine-ph correct-last-measurement --ph 4.5 --tac 50
uv run piscine-ph cancel-protocol
uv run piscine-ph measure --ph 5.2 --tac 50
uv run piscine-ph plan-tac --tac 50
uv run piscine-ph measure-tac --ph 6.1 --tac 80
uv run piscine-ph treatment --electrolysis arretee --chlorine galets_stabilises
uv run piscine-ph record-tablets --count 2 --unit-mass-g 200
uv run piscine-ph measure-cya --cya 35
uv run piscine-ph history
```

`uv run piscine-ph start` reprend automatiquement le dernier protocole non terminé.
Utiliser `--force` uniquement pour créer une nouvelle archive malgré un protocole actif.
