# piscine-ph

Outil en ligne de commande pour suivre une correction progressive du pH et du TAC d'une piscine.

## Installation et lancement

Sur macOS ou Linux, une seule commande installe `uv` si nécessaire, puis l'application :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/main/install.sh | sh
```

Sous Windows, ouvrir PowerShell et exécuter :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/main/install.ps1 | iex
```

Ensuite, depuis n'importe quel dossier :

```bash
piscine-ph start
piscine-ph status
piscine-ph menu
```

Le suivi est stocke dans `data/protocoles/` : chaque protocole est archive dans son propre fichier JSON date.

Voir le [guide utilisateur](docs/guide-utilisateur.md) pour l'utilisation pas a pas, la [documentation technique](docs/protocole_ph_tac.md) pour les calculs et limites scientifiques, et le [guide développeur](docs/guide-developpeur.md) pour l'architecture et la maintenance.
Les paramètres par défaut versionnés sont décrits dans la [documentation de configuration](docs/configuration.md).
La structure et la lecture des paramètres et archives sont détaillées dans la [référence des fichiers JSON](docs/fichiers-json.md).
Pour apprendre rapidement les bases pH/TAC, lire aussi le [guide de chimie](docs/comprendre-la-chimie.md).
Le cas temporaire « électrolyse arrêtée et galets stabilisés » est traité dans le [guide dédié](docs/traitement-chlore-stabilise.md).

## Commandes principales

```bash
piscine-ph start
piscine-ph dose
piscine-ph cancel-dose
piscine-ph cancel-tac-plan
piscine-ph correct-last-measurement --ph 4.5 --tac 50
piscine-ph cancel-protocol
piscine-ph measure --ph 5.2 --tac 50
piscine-ph plan-tac --tac 50
piscine-ph measure-tac --ph 6.1 --tac 80
piscine-ph treatment --electrolysis arretee --chlorine galets_stabilises
piscine-ph record-tablets --count 2 --unit-mass-g 200
piscine-ph measure-cya --cya 35
piscine-ph history
```

`piscine-ph start` reprend automatiquement le dernier protocole non terminé.
Utiliser `--force` uniquement pour créer une nouvelle archive malgré un protocole actif.
