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

### macOS ou Linux

Ouvrir **Terminal**, puis exécuter une seule commande :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.2/install.sh | sh
```

Elle installe `uv` et Python si nécessaire, puis `piscine-ph`. Si `uv` vient d'être installé, fermer puis rouvrir le terminal. Démarrer ensuite l'application depuis n'importe quel dossier :

```bash
piscine-ph start
```

### Windows 10 ou 11

Ouvrir **PowerShell**, puis exécuter une seule commande :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.2/install.ps1 | iex
```

Elle installe `uv`, puis Python 3.11 même si un Python plus ancien est déjà présent, et enfin `piscine-ph`. Windows 10 et 11 incluent déjà Windows PowerShell ; Git n'est pas nécessaire, car l'application est téléchargée depuis l'archive de la version publiée. Si `uv` vient d'être installé, fermer puis rouvrir PowerShell. Démarrer ensuite l'application :

```powershell
piscine-ph start
```

### En cas de problème

- `uv : commande introuvable` : relancer la commande d'installation ci-dessus. Elle installe `uv` pour le compte utilisateur.
- `piscine-ph : commande introuvable` : fermer totalement le terminal, l'ouvrir à nouveau, puis réessayer. L'installateur ajoute normalement le répertoire des outils au `PATH`.
- `Python introuvable` : relancer la commande d'installation ; `uv` téléchargera une version compatible.
- `PowerShell introuvable` : sur Windows 10/11, rechercher **Windows PowerShell** dans le menu Démarrer. Sur une installation Windows inhabituelle où il serait absent, l'installer d'abord depuis Microsoft ou demander l'aide de l'administrateur : le script ne peut pas installer le terminal qui l'exécute.
- `git : commande introuvable` : aucun problème ; Git n'est pas requis pour installer ou utiliser l'application.
- Erreur de réseau : reconnecter l'ordinateur puis relancer la même commande ; `uv` reprendra les téléchargements nécessaires.
- Erreur d'autorisation : ne pas utiliser `sudo` pour ce projet. Installer sous le compte utilisateur ou demander l'aide de l'administrateur de l'ordinateur.
- L'application ne nécessite pas de dossier de projet local.

L'installation est liée à la version `v0.2.2`. Pour une mise à jour, reprendre la commande fournie dans la [release GitHub](https://github.com/frchalaoux/piscine-ph-tac/releases) de la version voulue ; elle utilisera un tag précis.

## Modifier les valeurs proposées par défaut

Les valeurs proposées au démarrage servent seulement de repères. À la création d'un nouveau protocole, le questionnaire permet de les remplacer par les mesures et caractéristiques réelles du bassin. Chaque archive conserve ses propres paramètres ; elle n'est jamais modifiée par une future mise à jour de l'application.

Pour une exécution sans questionnaire, les options de `start`, comme `--volume-m3 46`, remplacent les valeurs proposées. Les réglages internes fournis avec l'application sont documentés dans la [documentation de configuration](configuration.md) et concernent le développement du projet.

Si un protocole est actif, `start` le reprend et n'applique donc pas de nouveaux paramètres. Terminer ou annuler le protocole actif, puis lancer `start` ; ou utiliser explicitement `piscine-ph start --force` pour créer une nouvelle archive sans supprimer l'ancienne.

## Démarrer un protocole

Pour utiliser les valeurs prévues pour le bassin de 46 m3 :

```bash
piscine-ph start
```

Pour tout **nouveau** protocole, cette commande ouvre un questionnaire. Il demande et archive : volume, pH et TAC réellement mesurés, paliers pH, concentration de soude, traitement de désinfection et, si utile, le CYA. Valider une valeur proposée n'est approprié que si elle correspond bien au bassin et au produit du jour.

Pour la soude, le questionnaire ne demande jamais le poids total du bidon : ce poids est inutilisable sans tare et volume. Il guide selon l'étiquette ou la FDS :

- concentration indiquée directement en `g/L` ;
- `% m/m` et densité en `g/mL` : `g/L = % × densité × 10` ; par exemple 30 % m/m à 1,33 g/mL donne 399 g/L ;
- `% m/v` : `g/L = % × 10` ; par exemple 30 % m/v donne 300 g/L.

La concentration ne possède pas de réponse par défaut dans le questionnaire : elle doit être saisie depuis l'étiquette ou la FDS. Le programme rappelle à l'écran les exemples `300 g/L`, `30 % m/m` avec une densité de `1,33 g/mL` (soit `399 g/L`) et `30 % m/v` (soit `300 g/L`). Ces exemples servent à reconnaître l'unité ; ils ne doivent pas être repris si l'étiquette indique autre chose. En cas d'unité ou de densité absente, arrêter le questionnaire et consulter la FDS du produit. Les réponses sont figées dans l'archive, notamment `config.naoh_concentration_g_l` et son origine. Cela évite de confondre une soude à 30 % massique avec une solution à 300 g/L.

### Corriger la soude d'un protocole déjà commencé

Ne lancez ni `start --force`, ni un nouveau protocole pour cela : les mesures et apports précédents seraient séparés de leur historique. Vérifiez d'abord l'état avec :

```bash
piscine-ph status
```

S'il existe une **dose de NaOH en attente**, confirmez-la avec sa mesure si elle a été versée, ou annulez-la seulement si elle n'a pas été versée. Ensuite, pour le même bidon employé depuis le début, lancez :

```bash
piscine-ph configure-naoh
```

Le questionnaire de cette commande demande de nouveau l'unité. Pour la lessive de soude du FDS étudié ici, choisir `% m/m`, saisir `30` puis la densité `1,33` : l'application archive et emploie `399 g/L` (soit environ `400 g/L`). Les volumes déjà versés et les mesures restent intacts ; le cumul en moles de NaOH et les contrôles théoriques sont recalculés avec cette concentration, et la modification est inscrite dans le journal JSON.

N'utilisez pas cette commande si les premiers apports ont été faits avec un produit différent : elle suppose une même concentration pour tous les apports confirmés. Conservez alors l'archive telle quelle et commencez un nouveau protocole pour le nouveau produit.

Un lot de bicarbonate en attente n'empêche pas cette correction, car le bicarbonate est calculé à partir du TAC mesuré, pas de la concentration de soude.

Le test TAC utilisé ici se lit par paliers de 10 ppm. Saisir uniquement des valeurs comme 40, 50, 60, 70 ou 80 ppm ; l'application refuse une fausse précision telle que 52 ppm.

Pour une exécution automatisée ou sans questionnaire, utiliser `--no-guided` et fournir explicitement les paramètres, en particulier la concentration de soude :

```bash
piscine-ph start --no-guided --volume-m3 46 --initial-ph 4.0 --initial-tac 30 --bucket-l 10 --naoh-g-l 400
```

Le programme crée un fichier de suivi daté dans `data/protocoles/`. Il conserve les mesures et reprend automatiquement le dernier protocole non terminé.

Dès la création, il affiche et archive un **approvisionnement indicatif** : stock prudent de soude à la concentration confirmée dans le questionnaire et quantité de bicarbonate calculée depuis le TAC initial, avec une marge d'achat. Ce n'est pas une instruction de verser ces quantités : chaque apport reste soumis aux mesures pH/TAC intermédiaires. La même information est visible ensuite avec `piscine-ph status`.

### Cas particulier : électrolyse arrêtée et galets stabilisés

Si la cellule est arrêtée pour maintenance et que la désinfection temporaire est assurée par des galets stabilisés, déclarer ce contexte dès le début :

```bash
piscine-ph start --electrolysis arretee --disinfection galets_stabilises
```

Si le protocole existe déjà, utiliser à la place `piscine-ph treatment --electrolysis arretee --disinfection galets_stabilises`. L'estimation d'approvisionnement est alors actualisée et stockée à nouveau avec la marge spécifique aux galets stabilisés.

Le calcul théorique du TAC reste disponible, mais la prévision de pH devient indicative car les galets acidifient l'eau et apportent du CYA. Journaliser les galets et chaque mesure de stabilisant :

```bash
piscine-ph record-tablets --count 2 --unit-mass-g 200 --product "galets trichlore 200 g"
piscine-ph measure-cya --cya 35
```

La procédure complète, les seuils d'alerte, les contrôles à effectuer et le retour à l'électrolyse sont détaillés dans le [guide de traitement temporaire au chlore stabilisé](traitement-chlore-stabilise.md).

Le JSON enregistre aussi le cumul des produits effectivement versés : volume et moles de NaOH, masse et moles de bicarbonate, ainsi que leur contribution théorique cumulée au TAC. Une dose annulée n'est pas comptée.

Si un protocole est déjà en cours, `start` le reprend et affiche son étape actuelle. Pour créer volontairement un nouveau protocole, sans supprimer l'ancien :

```bash
piscine-ph start --force
```

## Consulter l'étape en cours

À tout moment :

```bash
piscine-ph status
```

La commande affiche le dernier pH, le dernier TAC, l'étape active et une éventuelle dose en attente.

Lancer à nouveau `piscine-ph start` est également possible : la commande reprend le protocole actif, sans le recréer.

Après chaque commande, l'application affiche aussi `Commande suivante : ...` avec la commande adaptée à l'étape active.

## Mode guidé

Pour ne pas retenir les commandes, utiliser le menu :

```bash
piscine-ph menu
```

Le menu affiche l'étape active et propose seulement l'action logique suivante. Il s'arrête lorsqu'une action physique doit être réalisée : ajout de soude ou bicarbonate, circulation, puis mesure dans le bassin. Relancer `menu` après la mesure pour continuer.

## Étape 1 — Remonter jusqu'à pH 6

Préparer une dose de soude :

```bash
piscine-ph dose
```

Le programme affiche l'eau et le volume de soude à mettre dans le seau. Pour modifier la dose proposée :

```bash
piscine-ph dose --naoh-ml 100
```

Avec un seau de 10 L et 250 mL de soude, le programme demande 7,75 L d'eau puis 250 mL de soude. Il garde 2 L de marge dans le seau.

Après mélange prudent :

1. verser près des buses, filtration en marche ;
2. attendre que l'eau soit homogène ;
3. mesurer le pH et le TAC **dans le bassin** ;
4. enregistrer les valeurs.

Exemple :

```bash
piscine-ph measure --ph 5.20 --tac 50
```

Si la dose a ete preparee dans l'application mais **n'a pas ete versee** dans le bassin, l'annuler avant toute nouvelle dose :

```bash
piscine-ph cancel-dose
```

La commande demande une confirmation, supprime uniquement la dose en attente et conserve les mesures precedentes. Ne jamais l'utiliser si la soude a deja ete versee : dans ce cas, mesurer pH et TAC puis utiliser `measure`.

## Corriger une mesure saisie par erreur

Si le produit a bien ete versé mais que le pH ou le TAC saisi est erroné, corriger la dernière mesure sans retirer le produit du cumul :

```bash
piscine-ph correct-last-measurement --ph 4.5 --tac 50
```

Cette commande recalcule le contrôle de cohérence et replace le protocole à la bonne étape. Elle ne fonctionne pas si une dose suivante est déjà préparée : annuler d'abord cette dose avec `cancel-dose`.

## Annuler un protocole et en commencer un nouveau

Pour abandonner le protocole actif sans perdre son historique :

```bash
piscine-ph cancel-protocol
```

La commande demande une confirmation, marque le protocole comme `annule` et conserve son fichier JSON dans `data/protocoles/`. Elle ne supprime aucune mesure.

Créer ensuite le nouveau protocole :

```bash
piscine-ph start
```

Il est aussi possible d'utiliser `start --force`, mais `cancel-protocol` est préférable lorsqu'un protocole doit clairement être abandonné dans l'historique.

Répéter `dose`, puis `measure` jusqu'à atteindre pH 6,0. Les doses de 250, 100 ou 50 mL sont seulement des repères : adapter la dose à la remontée réellement observée.

## Étape 2 — Atteindre un TAC de 80 ppm

Lorsque pH 6 est atteint, mesurer le TAC et demander le calcul de bicarbonate :

```bash
piscine-ph plan-tac --tac 50
```

Le programme indique le besoin total théorique, mais prépare **un seul lot de 1 kg maximum**. Ajouter uniquement ce lot en poudre près des buses, filtration en marche, selon les consignes du produit. Attendre au minimum **4 heures** de circulation avant de mesurer pH et TAC — davantage si le cycle complet de filtration de votre bassin est plus long. Ne pas ajouter un second lot avant cette mesure. Une fiche produit bicarbonate comparable indique elle aussi environ quatre heures pour une circulation complète. [Leslie’s Alkalinity Up](https://lesliespool.com/leslies-alkalinity-up-2-lbs/48051.html)

Après dissolution et circulation, mesurer à nouveau pH et TAC puis saisir :

```bash
piscine-ph measure-tac --ph 6.15 --tac 80
```

Si le TAC est inférieur à 80 ppm, recommencer `plan-tac` avec la nouvelle mesure : le programme recalcule alors le besoin restant et prépare au plus 1 kg supplémentaire. Le programme ne passe pas à l'étape finale avant confirmation d'un TAC d'au moins 80 ppm.

## Étape 3 — Atteindre pH 7,2

Reprendre les petites doses de soude :

```bash
piscine-ph dose --naoh-ml 50
piscine-ph measure --ph 7.05 --tac 80
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

## Cas distinct : pH haut et chlore à surveiller

Quand le pH est déjà au-dessus de la cible, ne démarrez pas le protocole de
soude/bicarbonate : il sert uniquement à remonter un pH bas. Créez plutôt une
archive de surveillance ; elle journalise le pH, le TAC, le chlore libre et
l'état des équipements sans calculer de dose d'acide ou de chlore :

```bash
piscine-ph start --no-guided --force \
  --mode surveillance_ph_haut --initial-ph 7.6 --target-ph 7.2 --initial-tac 70 \
  --chlorine-min 1 --chlorine-max 4 \
  --electrolysis arretee --ph-regulator arrete \
  --disinfection galets_stabilises --tablets consommes
piscine-ph record-water --ph 7.6 --tac 70 --free-chlorine 0.5
```

Les bornes de chlore doivent être celles de l'étiquette du désinfectant. Le
programme alerte si le chlore est sous ou au-dessus de ces bornes, mais ne
propose jamais une dose. Il signale aussi les galets consommés, l'électrolyse ou
le régulateur de pH arrêté. Le [guide de surveillance](surveillance-ph-haut-chlore.md)
explique le parcours, les limites et les précautions.

## Interface à menus

La commande suivante lance une interface Textual destinée à la consultation et
aux opérations courantes :

```bash
piscine-ph tui
```

La barre de menus en haut donne accès à **Accueil**, **Protocole**,
**Mesures**, **Traitement**, **Archives** et **Aide**. L'item actif est mis en
évidence et chaque page défile indépendamment. Les actions d'une page sont
regroupées dans des items dépliables : aucun champ prérempli n'est affiché sans
son libellé. `⌘R` sur macOS (`Ctrl+R` sur les autres systèmes) actualise
l'affichage, et `q` quitte l'application ; `⌘↓` et `⌘↑` sur macOS (`Ctrl+↓` et
`Ctrl+↑` sur les autres systèmes) font défiler la page
active. Le menu **Protocole** couvre `start`, `configure-naoh`, `dose`,
`plan-tac`, les annulations et la correction de mesure. Le menu **Mesures** enregistre les
mesures attendues par le protocole actif : après une dose de soude ou de
bicarbonate dans un parcours pH bas, il demande pH et TAC ; pour la
surveillance pH haut, il demande aussi le chlore libre. L'onglet
**Traitement** ne pilote aucun appareil : il distingue la **désinfection
active** (une seule source) de l'état de l'électrolyseur au sel, du doseur de
galets stabilisés et du régulateur pH.

Le bouton **Arrêter le protocole…** du tableau de bord ouvre une confirmation.
Après validation, le protocole est marqué `annule` et reste dans l'historique ;
les éventuelles préparations non confirmées sont retirées, comme avec
`piscine-ph cancel-protocol`.

Le bouton **Voir le JSON actif** ouvre le fichier du protocole en lecture seule.
Dans **Archives**, choisir une archive puis **Voir le JSON sélectionné**. Le
contenu et son chemin sont sélectionnables pour être copiés, sans possibilité de
modifier les données depuis le TUI.

L'onglet **Commandes CLI** liste la correspondance de chaque commande Typer :
aucune règle métier n'est dupliquée, les deux interfaces enregistrent les mêmes
archives et appliquent les mêmes contrôles. Les commandes Typer restent utiles
pour les scripts et l'automatisation.

### Installation publiée ou version locale

La commande globale `piscine-ph` exécute la version installée depuis un tag de
release. Elle ne connaît donc pas une commande ajoutée seulement dans le dépôt
de développement. Si `piscine-ph tui` répond `No such command 'tui'`, la
version installée est antérieure à l'ajout de la TUI.

Pour essayer la version locale du projet sans modifier l'installation globale :

```bash
cd /Users/frchalaoux/Documents/Developpement/rectificationph
uv run piscine-ph tui
```

Pour installer une seule fois la version locale en mode développement et lancer
ensuite `piscine-ph` directement après chaque modification Python :

```bash
cd /Users/frchalaoux/Documents/Developpement/rectificationph
uv tool install --editable --reinstall .
piscine-ph tui
```

`--editable` fait pointer l'outil global vers le dépôt ; `--reinstall` remplace
une éventuelle installation publiée existante. Les changements de code sont
ensuite visibles sans réinstallation. Refaire l'installation seulement après
une modification de dépendance, de `pyproject.toml` ou de l'entrée de commande :
`uv tool install --editable --reinstall .`. Pour revenir à une version publiée,
relancer la commande d'installation associée au tag voulu sur la page des
releases.

## Voir les protocoles précédents

```bash
piscine-ph history
```

Les fichiers JSON de suivi restent dans `data/protocoles/`. Ils ne sont pas ajoutés à Git.
Pour consulter et copier le JSON du protocole actif, sans le modifier :

```bash
piscine-ph json
```

Pour consulter une archive précise, utiliser son nom affiché par `history` :

```bash
piscine-ph json protocole_20260910_102222.json
```

## Aide

Pour connaître les options d'une commande :

```bash
piscine-ph dose --help
piscine-ph measure --help
piscine-ph plan-tac --help
```

Pour les détails chimiques et l'architecture du projet, consulter [la documentation technique](protocole_ph_tac.md).
