# piscine-ph

Application de suivi du pH, du TAC et de la désinfection d'une piscine. Elle propose deux interfaces pour les mêmes protocoles et les mêmes archives :

- **TUI** : interface à menus dans le terminal, avec un assistant guidé, des formulaires de mesure et l'accès aux archives.
- **CLI** : commandes à saisir dans le terminal, utiles pour suivre les étapes une à une ou automatiser des opérations.

L'application enregistre les mesures et les ajouts confirmés. Elle ne verse aucun produit et ne remplace ni les mesures du bassin, ni l'étiquette ou la fiche de données de sécurité du produit utilisé.

## Installation

Sur macOS ou Linux, une seule commande installe `uv` si nécessaire, puis l'application :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.6/install.sh | sh
```

Sous Windows 10 ou 11, ouvrir Windows PowerShell et exécuter (Git n'est pas nécessaire) :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.6/install.ps1 | iex
```

Après une première installation de `uv`, rouvrir le terminal avant de lancer `piscine-ph`.

## Utiliser l'interface à menus (TUI)

```bash
piscine-ph tui
```

La page **Accueil** ouvre l'**Assistant guidé** : il affiche la prochaine action adaptée au protocole actif et conduit au formulaire correspondant. Le menu **Protocoles** permet de mesurer l'eau, corriger le pH ou le TAC et gérer la désinfection. **Archives** permet de retrouver les suivis précédents ; **Aide** présente les commandes et les raccourcis.

L'assistant attend une mesure réelle après chaque lot préparé. Le **Mode manuel** donne un accès direct aux parcours sans retour automatique à l'assistant. Le [guide utilisateur](docs/guide-utilisateur.md) détaille les écrans et leur fonctionnement.

## Utiliser les commandes (CLI)

Pour démarrer ou reprendre un protocole, consulter son état et suivre la prochaine étape dans le menu guidé de la CLI :

```bash
piscine-ph start
piscine-ph status
piscine-ph menu
```

`piscine-ph menu` est un menu pas à pas dans la CLI ; l'interface à menus complète se lance avec `piscine-ph tui`. Selon le parcours en cours, l'application indique la commande suivante. Exemples :

```bash
piscine-ph protocols
piscine-ph dose
piscine-ph measure --ph 5.2 --tac 50
piscine-ph plan-tac --tac 50
piscine-ph measure-tac --ph 6.1 --tac 80
piscine-ph dose-acid
piscine-ph measure-acid --ph 7.4 --tac 80
piscine-ph treatment --electrolysis arretee --disinfection galets_stabilises
piscine-ph record-tablets --count 2 --unit-mass-g 200
piscine-ph plan-tablets
piscine-ph measure-cya --cya 35
piscine-ph history
```

`start` reprend le dernier protocole non terminé. L'option `--force` crée une nouvelle archive malgré un protocole actif ; à utiliser seulement si c'est voulu. Le [guide utilisateur](docs/guide-utilisateur.md) explique les parcours, les commandes de correction et les annulations.

Pour une baisse de pH avec l'IRRIPOOL PH- LIQUIDE 15 %, l'application prépare un seul lot plafonné à 0,1 unité de pH, à confirmer par une mesure pH/TAC avant tout autre lot. Pour les galets, `plan-tablets` propose une quantité issue de l'étiquette ; seul `record-tablets` enregistre un ajout réellement effectué.

Les deux interfaces enregistrent les suivis dans `data/protocoles/`, relativement au dossier depuis lequel l'application est lancée. Relancer l'application depuis ce même dossier permet de retrouver les mêmes archives.

## Documentation

Le [sommaire général](DOCUMENTATION.md) présente tous les documents de `docs/` avec un résumé et un lien HTTP vers chacun. Pour commencer, consulter le [guide de choix des protocoles](docs/choisir-un-protocole.md), le [guide de chimie pH/TAC](docs/comprendre-la-chimie.md) et le [guide utilisateur](docs/guide-utilisateur.md).

La [documentation technique](docs/protocole_ph_tac.md) décrit les calculs et leurs limites ; le [guide développeur](docs/guide-developpeur.md) couvre l'architecture et la maintenance. Les [produits et consignes de sécurité](docs/produits-et-securite.md) ainsi que la [recherche manuelle d'une FDS](docs/rechercher-une-fds.md) sont documentés séparément.

## Mises à jour

L'installation est figée sur la version `v0.2.6`. Pour installer une version ultérieure, reprendre la commande d'installation indiquée dans sa [release GitHub](https://github.com/frchalaoux/piscine-ph-tac/releases), qui utilisera son tag exact.
