# Guide utilisateur — piscine-ph

Ce guide explique comment suivre une correction de pH et de TAC avec l'application `piscine-ph`.

Pour comprendre les notions de pH, TAC, bicarbonate, CO2 et soude avant de commencer, consulter le [guide de chimie](comprendre-la-chimie.md).

## Avant de commencer

Préparer :

- un appareil de mesure de pH fiable ;
- un test TAC ;
- la soude liquide indiquée à 300 g/L ;
- du bicarbonate de sodium ;
- un seau compatible avec les produits, de 10 L par défaut ;
- les protections indiquées sur la fiche de données de sécurité du produit.

Ne pas utiliser la piscine pendant la correction. La soude est corrosive : ajouter la soude lentement dans l'eau, jamais l'eau dans la soude.

## Installer l'application

Le projet demande Python 3.11 ou plus récent et l'outil `uv`. Même si Python n'est pas installé sur l'ordinateur, `uv` peut télécharger et gérer une version de Python adaptée : il n'est donc pas nécessaire d'installer Python séparément dans le cas normal. [Documentation officielle uv](https://docs.astral.sh/uv/guides/install-python/)

### 1. Ouvrir un terminal dans le dossier du projet

Le dossier du projet doit contenir les fichiers `pyproject.toml`, `uv.lock` et le dossier `src`.

Sur macOS ou Linux, ouvrir **Terminal** puis, par exemple :

```bash
cd ~/Downloads/rectificationph
```

Sous Windows, ouvrir **PowerShell** puis, par exemple :

```powershell
cd "$HOME\Downloads\rectificationph"
```

Adapter le chemin si le projet a été enregistré ailleurs.

### 2. Vérifier ou installer uv

Commencer par vérifier si `uv` est déjà disponible :

```bash
uv --version
```

Si une version s'affiche, passer directement à l'étape 3.

Sinon, utiliser **une seule** des méthodes ci-dessous. Les commandes proposées proviennent de la [documentation officielle d'installation de uv](https://docs.astral.sh/uv/getting-started/installation/).

#### macOS

Dans Terminal :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Fermer puis rouvrir Terminal, puis vérifier :

```bash
uv --version
```

Si Homebrew est déjà installé, cette variante convient aussi :

```bash
brew install uv
```

#### Windows 10 ou 11

Dans PowerShell :

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Fermer puis rouvrir PowerShell, puis vérifier :

```powershell
uv --version
```

Si `winget` est déjà installé, cette variante convient aussi :

```powershell
winget install --id=astral-sh.uv -e
```

#### Linux

Dans un terminal :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Fermer puis rouvrir le terminal, puis vérifier :

```bash
uv --version
```

Avant d'exécuter un script téléchargé, il est possible de l'inspecter avec `curl -LsSf https://astral.sh/uv/install.sh | less`. Si l'ordinateur est administré par une organisation, demander d'abord l'autorisation ou utiliser la méthode de paquets approuvée.

### 3. Installer Python géré par uv

Le projet exige Python 3.11 au minimum. Installer Python 3.13, version stable compatible recommandée pour ce projet :

```bash
uv python install 3.13
```

Vérifier que la version est disponible :

```bash
uv python list --only-installed
```

`uv sync` peut aussi télécharger Python automatiquement s'il manque, mais cette étape explicite rend l'installation plus lisible. Pour ce projet, Python est donc installé et géré par `uv` ; aucune installation Python séparée n'est nécessaire.

### 4. Installer les dépendances du projet

Toujours dans le dossier du projet, lancer :

```bash
uv sync
```

Cette commande crée l'environnement isolé `.venv/` et installe les bibliothèques nécessaires ; elle ne modifie pas le Python global de l'ordinateur.

### 5. Vérifier et démarrer

Vérifier que l'application est disponible :

```bash
uv run piscine-ph --help
```

Puis créer ou reprendre le protocole :

```bash
uv run piscine-ph start
```

### En cas de problème

- `uv : commande introuvable` : fermer totalement le terminal, l'ouvrir à nouveau et refaire `uv --version`. L'installateur ajoute normalement `uv` au `PATH` du compte utilisateur.
- `Python introuvable` : lancer `uv python install 3.13`, puis `uv sync`.
- Erreur de réseau : reconnecter l'ordinateur puis relancer la même commande ; `uv` reprendra les téléchargements nécessaires.
- Erreur d'autorisation : ne pas utiliser `sudo` pour ce projet. Installer sous le compte utilisateur ou demander l'aide de l'administrateur de l'ordinateur.
- Le dossier n'est pas trouvé : revenir à l'étape 1 et vérifier son emplacement avec l'explorateur de fichiers.

## Modifier les valeurs proposées par défaut

Les valeurs affichées par défaut au démarrage — volume, pH de départ, objectifs pH/TAC, concentration de soude, volume du seau et tailles indicatives des apports — sont regroupées dans :

```text
src/piscine_ph/defaults.json
```

L'utilisateur peut modifier ce fichier avec un éditeur de texte avant de créer un nouveau protocole. Par exemple, pour un bassin de 35 m3 et un seau de 12 L, modifier seulement les nombres concernés :

```json
"pool_volume_m3": 35.0,
"bucket_volume_l": 12.0
```

Conserver impérativement la structure JSON : guillemets autour des noms, virgules entre les lignes et point pour les décimales. Ne pas modifier `schema_version`.

Les clés, unités et conséquences de chaque réglage sont expliquées dans la [documentation de configuration](configuration.md). Les constantes chimiques, tolérances et protections du seau ne se trouvent volontairement pas dans ce fichier ; elles ne doivent pas être modifiées pour adapter un bassin.

Après l'enregistrement, relancer la commande :

```bash
uv run piscine-ph start
```

La modification n'agit que sur un **nouveau** protocole. Chaque archive conserve ses propres paramètres dans son fichier JSON : elle n'est jamais réécrite par un changement de `defaults.json`.

Les options données directement à la commande `start`, par exemple `--volume-m3 46`, restent prioritaires sur les valeurs du fichier JSON.

Si un protocole est actif, `start` le reprend et n'applique donc pas les nouveaux réglages. Terminer ou annuler le protocole actif, puis lancer `start` ; ou utiliser explicitement `uv run piscine-ph start --force` pour créer une nouvelle archive sans supprimer l'ancienne.

## Démarrer un protocole

Pour utiliser les valeurs prévues pour le bassin de 46 m3 :

```bash
uv run piscine-ph start
```

Les valeurs par défaut sont : pH 4,1, palier pH 6,0, pH cible 7,2, TAC 50 ppm et seau 10 L.

Le test TAC utilisé ici se lit par paliers de 10 ppm. Saisir uniquement des valeurs comme 40, 50, 60, 70 ou 80 ppm ; l'application refuse une fausse précision telle que 52 ppm.

Pour fournir vos propres mesures :

```bash
uv run piscine-ph start --volume-m3 46 --initial-ph 4.1 --initial-tac 50 --bucket-l 10
```

Le programme crée un fichier de suivi daté dans `data/protocoles/`. Il conserve les mesures et reprend automatiquement le dernier protocole non terminé.

Dès la création, il affiche et archive un **approvisionnement indicatif** : stock prudent de soude à 300 g/L et quantité de bicarbonate calculée depuis le TAC initial, avec une marge d'achat. Ce n'est pas une instruction de verser ces quantités : chaque apport reste soumis aux mesures pH/TAC intermédiaires. La même information est visible ensuite avec `uv run piscine-ph status`.

### Cas particulier : électrolyse arrêtée et galets stabilisés

Si la cellule est arrêtée pour maintenance et que la désinfection temporaire est assurée par des galets stabilisés, déclarer ce contexte dès le début :

```bash
uv run piscine-ph start --electrolysis arretee --chlorine galets_stabilises
```

Si le protocole existe déjà, utiliser à la place `uv run piscine-ph treatment --electrolysis arretee --chlorine galets_stabilises`. L'estimation d'approvisionnement est alors actualisée et stockée à nouveau avec la marge spécifique aux galets stabilisés.

Le calcul théorique du TAC reste disponible, mais la prévision de pH devient indicative car les galets acidifient l'eau et apportent du CYA. Journaliser les galets et chaque mesure de stabilisant :

```bash
uv run piscine-ph record-tablets --count 2 --unit-mass-g 200 --product "galets trichlore 200 g"
uv run piscine-ph measure-cya --cya 35
```

La procédure complète, les seuils d'alerte, les contrôles à effectuer et le retour à l'électrolyse sont détaillés dans le [guide de traitement temporaire au chlore stabilisé](traitement-chlore-stabilise.md).

Le JSON enregistre aussi le cumul des produits effectivement versés : volume et moles de NaOH, masse et moles de bicarbonate, ainsi que leur contribution théorique cumulée au TAC. Une dose annulée n'est pas comptée.

Si un protocole est déjà en cours, `start` le reprend et affiche son étape actuelle. Pour créer volontairement un nouveau protocole, sans supprimer l'ancien :

```bash
uv run piscine-ph start --force
```

## Consulter l'étape en cours

À tout moment :

```bash
uv run piscine-ph status
```

La commande affiche le dernier pH, le dernier TAC, l'étape active et une éventuelle dose en attente.

Lancer à nouveau `uv run piscine-ph start` est également possible : la commande reprend le protocole actif, sans le recréer.

Après chaque commande, l'application affiche aussi `Commande suivante : ...` avec la commande adaptée à l'étape active.

## Mode guidé

Pour ne pas retenir les commandes, utiliser le menu :

```bash
uv run piscine-ph menu
```

Le menu affiche l'étape active et propose seulement l'action logique suivante. Il s'arrête lorsqu'une action physique doit être réalisée : ajout de soude ou bicarbonate, circulation, puis mesure dans le bassin. Relancer `menu` après la mesure pour continuer.

## Étape 1 — Remonter jusqu'à pH 6

Préparer une dose de soude :

```bash
uv run piscine-ph dose
```

Le programme affiche l'eau et le volume de soude à mettre dans le seau. Pour modifier la dose proposée :

```bash
uv run piscine-ph dose --naoh-ml 100
```

Avec un seau de 10 L et 250 mL de soude, le programme demande 7,75 L d'eau puis 250 mL de soude. Il garde 2 L de marge dans le seau.

Après mélange prudent :

1. verser près des buses, filtration en marche ;
2. attendre que l'eau soit homogène ;
3. mesurer le pH et le TAC **dans le bassin** ;
4. enregistrer les valeurs.

Exemple :

```bash
uv run piscine-ph measure --ph 5.20 --tac 50
```

Si la dose a ete preparee dans l'application mais **n'a pas ete versee** dans le bassin, l'annuler avant toute nouvelle dose :

```bash
uv run piscine-ph cancel-dose
```

La commande demande une confirmation, supprime uniquement la dose en attente et conserve les mesures precedentes. Ne jamais l'utiliser si la soude a deja ete versee : dans ce cas, mesurer pH et TAC puis utiliser `measure`.

## Corriger une mesure saisie par erreur

Si le produit a bien ete versé mais que le pH ou le TAC saisi est erroné, corriger la dernière mesure sans retirer le produit du cumul :

```bash
uv run piscine-ph correct-last-measurement --ph 4.5 --tac 50
```

Cette commande recalcule le contrôle de cohérence et replace le protocole à la bonne étape. Elle ne fonctionne pas si une dose suivante est déjà préparée : annuler d'abord cette dose avec `cancel-dose`.

## Annuler un protocole et en commencer un nouveau

Pour abandonner le protocole actif sans perdre son historique :

```bash
uv run piscine-ph cancel-protocol
```

La commande demande une confirmation, marque le protocole comme `annule` et conserve son fichier JSON dans `data/protocoles/`. Elle ne supprime aucune mesure.

Créer ensuite le nouveau protocole :

```bash
uv run piscine-ph start
```

Il est aussi possible d'utiliser `start --force`, mais `cancel-protocol` est préférable lorsqu'un protocole doit clairement être abandonné dans l'historique.

Répéter `dose`, puis `measure` jusqu'à atteindre pH 6,0. Les doses de 250, 100 ou 50 mL sont seulement des repères : adapter la dose à la remontée réellement observée.

## Étape 2 — Atteindre un TAC de 80 ppm

Lorsque pH 6 est atteint, mesurer le TAC et demander le calcul de bicarbonate :

```bash
uv run piscine-ph plan-tac --tac 50
```

Le programme indique le besoin total théorique, mais prépare **un seul lot de 1 kg maximum**. Ajouter uniquement ce lot en poudre près des buses, filtration en marche, selon les consignes du produit. Attendre au minimum **4 heures** de circulation avant de mesurer pH et TAC — davantage si le cycle complet de filtration de votre bassin est plus long. Ne pas ajouter un second lot avant cette mesure. Une fiche produit bicarbonate comparable indique elle aussi environ quatre heures pour une circulation complète. [Leslie’s Alkalinity Up](https://lesliespool.com/leslies-alkalinity-up-2-lbs/48051.html)

Après dissolution et circulation, mesurer à nouveau pH et TAC puis saisir :

```bash
uv run piscine-ph measure-tac --ph 6.15 --tac 80
```

Si le TAC est inférieur à 80 ppm, recommencer `plan-tac` avec la nouvelle mesure : le programme recalcule alors le besoin restant et prépare au plus 1 kg supplémentaire. Le programme ne passe pas à l'étape finale avant confirmation d'un TAC d'au moins 80 ppm.

## Étape 3 — Atteindre pH 7,2

Reprendre les petites doses de soude :

```bash
uv run piscine-ph dose --naoh-ml 50
uv run piscine-ph measure --ph 7.05 --tac 80
```

Continuer jusqu'à pH 7,2. Le programme marque alors le protocole comme terminé.

## Alertes de cohérence

Après chaque mesure, l'application compare les données saisies aux quantités de soude ou de bicarbonate ajoutées.

Une alerte signifie qu'il faut vérifier :

- le pH et le TAC mesurés ;
- la quantité réellement ajoutée ;
- le volume réel du bassin ;
- la présence d'acide, de CO2 ou d'autres produits.

Une alerte est un signal de contrôle : ne pas l'ignorer et ne pas ajouter une forte dose pour compenser immédiatement.

Si l'application indique que la prédiction de pH est indisponible, le couple pH/TAC de départ est hors du domaine utile du modèle carbonate fermé. Dans ce cas, ne pas utiliser un pH attendu théorique : utiliser la variation de pH réellement mesurée après chaque dose pour choisir la dose suivante.

## Voir les protocoles précédents

```bash
uv run piscine-ph history
```

Les fichiers JSON de suivi restent dans `data/protocoles/`. Ils ne sont pas ajoutés à Git.

## Aide

Pour connaître les options d'une commande :

```bash
uv run piscine-ph dose --help
uv run piscine-ph measure --help
uv run piscine-ph plan-tac --help
```

Pour les détails chimiques et l'architecture du projet, consulter [la documentation technique](protocole_ph_tac.md).
