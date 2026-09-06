# Documentation du protocole pH / TAC

`piscine-ph` est un outil en ligne de commande qui journalise une correction progressive de pH et de TAC pour une piscine. Il utilise une solution de soude (NaOH) à 300 g/L et du bicarbonate de sodium (NaHCO3).

Le projet est géré avec `uv`, modélisé avec Pydantic et exposé par Typer.

> Ce programme est un outil de suivi et de vérification, pas une autorisation de verser une quantité calculée. Respecter l'étiquette et la FDS des produits.

## Installation

```bash
uv sync
```

Cette commande crée l'environnement `.venv/`, installe les dépendances et rend la commande disponible via `uv run`.

```bash
piscine-ph --help
```

Chaque commande affiche la commande suivante adaptée à l'état enregistré. Le mode guidé `piscine-ph menu` propose aussi une action à la fois et attend les mesures réelles avant toute transition.

## Paramètres par défaut

| Paramètre | Valeur | Signification |
| --- | ---: | --- |
| Volume du bassin | 46 m3 | Volume utilisé dans les bilans. |
| pH initial | 4,1 | Première mesure du bassin. |
| Palier pH | 6,0 | Seuil avant correction du TAC. |
| pH cible | 7,2 | Objectif final. |
| TAC initial | 50 ppm CaCO3 | Valeur initialement mesurée. |
| TAC cible | 80 ppm CaCO3 | Valeur minimale à confirmer avant l'étape finale. |
| Soude | 300 g/L | Soit environ 7,501 mol/L de NaOH. |
| Seau | 10 L | Volume nominal de préparation. |

Les mesures TAC sont saisies par paliers de 10 ppm. Les valeurs attendues sont donc 40, 50, 60, 70, 80 ppm, etc. Une valeur telle que 52 ppm est volontairement refusée : le programme ne doit pas inventer une précision que le test ne fournit pas.

Créer un protocole avec ces valeurs :

```bash
piscine-ph start
```

La création affiche un plan d'approvisionnement archivé dans le JSON : volume prudent de soude à acheter et bicarbonate théorique calculé depuis le TAC initial, complété par une marge d'achat. Le repère de soude n'est pas une prédiction de consommation, car le pH ne permet pas à lui seul de connaître la demande acide réelle du bassin. La commande `status` réaffiche ce plan.

Avant la création d'une nouvelle archive, `start` ouvre un questionnaire guidé. Il transforme la concentration de soude lue sur l'étiquette ou la FDS en g/L, qui est l'unité requise par les calculs. Une concentration exprimée en `% m/m` exige aussi la densité : par exemple 30 % m/m et 1,33 g/mL donnent 399 g/L. Une concentration `% m/v` se convertit directement : 30 % m/v donnent 300 g/L. Le poids du bidon plein ne permet pas cette conversion sans tare et volume.

Ou renseigner des valeurs mesurées différentes :

```bash
piscine-ph start \
  --no-guided \
  --volume-m3 46 \
  --initial-ph 4.1 \
  --intermediate-ph 6.0 \
  --target-ph 7.2 \
  --initial-tac 50 \
  --bucket-l 10 \
  --naoh-g-l 400
```

Un seul protocole non terminé est repris automatiquement. Lancer de nouveau `piscine-ph start` ne crée donc pas de doublon : la commande affiche et reprend le protocole actif. Pour commencer volontairement un nouveau protocole malgré un protocole actif, utiliser `--force`.

Si l'unité de soude d'un protocole existant a été mal déclarée, ne pas lancer `start --force`. Après avoir confirmé ou annulé une éventuelle dose de NaOH en attente, exécuter `piscine-ph configure-naoh`. La commande redemande l'unité et corrige la concentration pour le même produit employé depuis le début ; elle conserve les volumes et mesures, recalcule le cumul et ajoute un événement au journal. Elle ne convient pas à un changement de produit en cours de protocole.

Pour arrêter explicitement le protocole actif tout en conservant son journal JSON, utiliser `piscine-ph cancel-protocol`, puis lancer `piscine-ph start`.

## Vue d'ensemble du protocole

```text
pH initial
   |
   |  doses de NaOH + mesures pH/TAC
   v
pH 6,0 atteint
   |
   |  mesure TAC, bicarbonate, mesure pH/TAC
   v
TAC >= 80 ppm confirme
   |
   |  doses finales de NaOH + mesures pH/TAC
   v
pH 7,2 atteint
```

Chaque transition dépend d'une mesure réelle. Aucune étape ne progresse sur une estimation seule.

## Étape 1 : pH initial vers pH 6

Vérifier l'état en cours :

```bash
piscine-ph status
```

Préparer une dose de soude. Sans option, le programme propose une dose indicative (250, 100 ou 50 mL selon l'écart au palier) ; elle reste modifiable :

```bash
piscine-ph dose
piscine-ph dose --naoh-ml 150
```

Le programme affiche l'eau et le NaOH à mettre dans le seau. Pour un seau de 10 L, il limite la préparation à 8 L, afin de laisser 20 % de marge libre. Il limite également le volume de NaOH à 10 % du volume utile.

Exemple pour une dose de 250 mL :

```text
Mettre 7,75 L d'eau dans le seau, puis 250 mL de NaOH.
```

Ajouter lentement la soude dans l'eau, jamais l'inverse. Mélanger avec précaution, verser près des buses avec filtration en marche, attendre l'homogénéisation, puis mesurer **le pH et le TAC du bassin**. Le pH du seau ne pilote pas le protocole.

Enregistrer la mesure :

```bash
piscine-ph measure --ph 5.20 --tac 50
```

Le programme conserve la dose, les valeurs avant/après et leur variation. Tant que le pH est sous 6,0, refaire `dose`, puis `measure`.

## Étape 2 : atteindre et confirmer le TAC de 80 ppm

Lorsque le palier pH 6 est atteint, mesurer le TAC réel puis calculer l'apport de bicarbonate :

```bash
piscine-ph plan-tac --tac 50
```

Le programme calcule la masse de NaHCO3 nécessaire, mais ne prépare qu'un **lot de 1 kg maximum**. Pour 46 m3, de 50 à 80 ppm, le besoin théorique initial est d'environ **2,32 kg** ; cette valeur n’autorise pas à verser les 2,32 kg sans contrôle.

Ajouter uniquement le lot affiché en poudre devant les buses, avec filtration, selon l'étiquette du produit. Attendre au minimum **4 heures** de circulation avant de mesurer pH et TAC :

```bash
piscine-ph measure-tac --ph 6.15 --tac 80
```

Si le TAC mesuré est sous 80 ppm, le programme reste à l'étape TAC. Refaire `plan-tac` avec la nouvelle mesure : il recalcule le besoin restant et prépare un nouveau lot de 1 kg maximum. Ne jamais confirmer un lot partiellement versé comme s'il avait été versé en totalité.

Le passage à l'ajustement final n'est autorisé que lorsque le TAC saisi est supérieur ou égal à 80 ppm.

## Étape 3 : pH vers 7,2

Une fois le TAC confirmé, reprendre le cycle :

```bash
piscine-ph dose --naoh-ml 50
piscine-ph measure --ph 7.05 --tac 80
```

Les doses 250/100/50 mL sont seulement indicatives. Le choix réel doit tenir compte de la remontée de pH mesurée lors de la dose précédente. Lorsque le pH mesuré atteint ou dépasse 7,2, le protocole est marqué terminé et archivé.

## pH, TAC et bilans chimiques

Le pH et le TAC sont deux grandeurs différentes :

- le pH indique l'acidité ou la basicité instantanée ;
- le TAC mesure la capacité de l'eau à neutraliser un acide ;
- bicarbonates, carbonates et hydroxydes contribuent au TAC.

Le pH ne modifie pas, à lui seul, le TAC. En revanche, les produits ajoutés modifient le bilan :

| Action | pH | TAC |
| --- | --- | --- |
| NaOH | Hausse | Hausse d'un équivalent par mole de NaOH. |
| NaHCO3 | Hausse légère ou variable | Hausse d'un équivalent par mole de NaHCO3. |
| Acide fort | Baisse | Baisse. |
| Échange de CO2 avec l'air | Peut varier | Généralement peu de changement direct. |

Pour 46 m3, 250 mL de NaOH à 300 g/L représentent environ 1,875 mole de NaOH, soit une hausse théorique de TAC d'environ **2,04 ppm CaCO3**.

## Contrôle de cohérence scientifique

Après chaque `measure` ou `measure-tac`, le programme compare les valeurs saisies à un modèle carbonate fermé à 25 °C :

```text
CO2 + H2O <-> H2CO3 <-> H+ + HCO3-
HCO3- <-> H+ + CO3--
```

Il affiche :

- pH et TAC théoriques après le produit ajouté ;
- écart pH et TAC entre mesure et modèle ;
- alertes si l'écart dépasse +/- 0,40 unité pH ou +/- 10 ppm de TAC.

Une alerte ne doit pas être ignorée, mais ne bloque pas mécaniquement le protocole. Les causes possibles sont une mesure imprécise, un volume de bassin inexact, un dosage réel différent, un ajout d'acide, un échange de CO2 ou d'autres produits dans l'eau.

Le TAC théorique peut être affiché avec une décimale pour le bilan chimique, mais le TAC réellement saisi reste un résultat par paliers de 10 ppm. La tolérance de comparaison de +/- 10 ppm tient compte de cette résolution.

### Limite supplémentaire : chlore stabilisé et électrolyse

Le modèle ne représente ni l'électrolyse, ni le trichlore/dichlore, ni le CYA. Le sel résiduel n'affecte pas les bilans NaOH/NaHCO3 du programme ; l'arrêt de la cellule retire cependant une source habituelle de hausse de pH. Les galets stabilisés peuvent en parallèle acidifier l'eau, diminuer le TAC et introduire du CYA. Dans ce contexte, le programme conserve ses bilans théoriques de TAC mais marque la prévision de pH comme indicative.

Utiliser `treatment`, `record-tablets` et `measure-cya` pour archiver ce contexte et les observations réelles. Le nombre de galets n'est jamais converti automatiquement en CYA : une mesure est nécessaire. Consulter le [guide dédié au traitement temporaire](traitement-chlore-stabilise.md) avant d'employer des galets stabilisés sur plusieurs semaines.

Le contrôle initial peut signaler pH 4,1 et TAC 50 ppm comme peu compatibles avec le modèle fermé. Un TAC total est généralement titré vers pH 4,2–4,5 ; une valeur positive à pH 4,1 mérite donc une vérification du test et de l'origine de l'acidité.

Dans ce cas, l'application n'affiche plus de pH théorique : cette prédiction serait trompeuse. Le bilan de TAC reste affiché, mais la remontée de pH réellement mesurée après chaque dose est la référence pour choisir la dose suivante.

## Archivage JSON

Chaque protocole crée un fichier daté :

```text
data/protocoles/protocole_YYYYMMDD_HHMMSS.json
```

Le fichier contient la configuration, l'étape active, toutes les doses, les mesures, les contrôles de cohérence et les événements horodatés. Afficher toutes les archives :

```bash
piscine-ph history
```

Le champ `cumulative_additions` récapitule les produits effectivement enregistrés : `naoh_solution_ml`, `naoh_moles`, `bicarbonate_kg`, `bicarbonate_moles` et les contributions théoriques correspondantes au TAC. Une dose préparée puis annulée n'est pas incluse.

En cas de pH ou TAC saisi incorrectement après un produit réellement versé, la commande `correct-last-measurement --ph ... --tac ...` corrige la dernière mesure sans modifier ce cumul. Elle recalcule également l'étape active.

Si l'ancien fichier `suivi_protocole_naoh_tac.json` existe encore, la première commande l'archive automatiquement dans ce nouveau dossier sans supprimer le fichier original.

Le dossier est ignoré par Git afin de ne pas versionner les mesures d'exploitation. Les sources du programme restent versionnées.

## Architecture du projet

```text
src/piscine_ph/
  models.py       # modèles Pydantic et état JSON
  chemistry.py    # calculs de bilan et modèle carbonate
  repository.py   # archivage JSON atomique
  service.py      # transitions du protocole
  cli.py          # commandes Typer
tests/            # tests pytest
pyproject.toml    # dépendances uv et script CLI
```

Exécuter les tests et les contrôles de style :

```bash
uv run pytest
uv run ruff check .
```

## Sécurité

La soude à 300 g/L est corrosive. Porter les équipements indiqués par la FDS, ne pas mélanger soude et acide, et ne pas utiliser un seau contenant des résidus de produits incompatibles. Éviter projections et aérosols.

Toujours suivre la FDS et les indications du fabricant avant ce protocole. En cas de contact avec la peau ou les yeux, appliquer immédiatement les mesures de premiers secours prévues par la FDS.

## Références

- [USGS — Calculation of Alkalinity, Hydroxide, Carbonate, and Bicarbonate](https://or.water.usgs.gov/alk/methods.html)
- [EPA — Total Alkalinity](https://archive.epa.gov/water/archive/web/html/vms510.html)
- [University of Illinois — Bases / Hydroxides safety guidance](https://www.drs.illinois.edu/Page/SafetyLibrary/BasesHydroxides)
