# piscine-ph

Outil en ligne de commande pour suivre une correction progressive du pH et du TAC d'une piscine.

## Installation et lancement

Sur macOS ou Linux, une seule commande installe `uv` si nécessaire, puis l'application :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.1.3/install.sh | sh
```

Sous Windows, ouvrir PowerShell et exécuter :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.1.3/install.ps1 | iex
```

Ensuite, depuis n'importe quel dossier (rouvrir le terminal après une première installation de `uv`) :

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
Le cas « pH haut, TAC à confirmer et chlore faible ou fort » est décrit dans le [guide de surveillance](docs/surveillance-ph-haut-chlore.md).

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
piscine-ph treatment --electrolysis arretee --disinfection galets_stabilises
piscine-ph record-tablets --count 2 --unit-mass-g 200
piscine-ph measure-cya --cya 35
piscine-ph tui
piscine-ph start --no-guided --force --mode surveillance_ph_haut --initial-ph 7.6 --target-ph 7.2 --initial-tac 70 --chlorine-min 1 --chlorine-max 4
piscine-ph record-water --ph 7.6 --tac 70 --free-chlorine 0.5
piscine-ph history
piscine-ph json
```

`piscine-ph start` reprend automatiquement le dernier protocole non terminé.
Utiliser `--force` uniquement pour créer une nouvelle archive malgré un protocole actif.

## Mises à jour

L'installation est figée sur la version `v0.1.3`. Pour installer une version ultérieure, reprendre la commande d'installation indiquée dans sa [release GitHub](https://github.com/frchalaoux/piscine-ph-tac/releases), qui utilisera son tag exact.
