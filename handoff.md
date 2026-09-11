# Handoff — `piscine-ph`

Date de mise à jour : 11 septembre 2026

## Objectif du projet

`piscine-ph` est une CLI Python/Typer qui journalise une correction progressive du pH et du TAC d'une piscine. Le protocole actuellement implémenté distingue :

- la soude NaOH pour les étapes de relèvement du pH ;
- le bicarbonate de sodium (`NaHCO3`) pour la remontée contrôlée du TAC ;
- les mesures intermédiaires et les lots limités comme garde-fous.

Le dépôt public est [frchalaoux/piscine-ph-tac](https://github.com/frchalaoux/piscine-ph-tac).

## État Git à reprendre

- Branche locale active : `staging`.
- `staging` et `origin/staging` pointent sur `66d6c26`, tagué `v0.2.3`.
- `test-cli-windows` et `origin/test-cli-windows` pointent sur `866a01a`
  (« ajouter le parcours CLI pH bas et galets »). Ce commit a été intégré à
  `staging` par avance rapide le 10 septembre 2026, avant la préparation de
  `v0.2.3`.
- `main` et `origin/main` pointent sur `663f9d4` (PR n° 8) et ne contiennent
  pas encore `866a01a` ni `v0.2.3`.
- Les tags/releases publiés vont de `v0.1.0` à `v0.2.3`. La release de travail
  la plus récente est [v0.2.3](https://github.com/frchalaoux/piscine-ph-tac/releases/tag/v0.2.3).

## Installation utilisateur

L'installation est versionnée et ne dépend pas de `main` :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.3/install.sh | sh
```

Sous PowerShell :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.2.3/install.ps1 | iex
```

Les scripts installent `uv` seulement s'il est absent du `PATH`, puis installent
le paquet depuis le tag. Ils installent ensuite Python 3.11 afin de ne pas
réutiliser un Python 3.10 incompatible avec la version d'`uv` utilisée. Après
une première installation de `uv`, l'utilisateur peut devoir rouvrir son
terminal avant d'exécuter `piscine-ph start`.

## Publication de versions

Le programme `scripts/release.py` automatise une release depuis **la branche locale active**.

```bash
# Simulation, sans modifier de fichier
uv run python scripts/release.py X.Y.Z

# Publication complète — seulement après demande explicite de l'utilisateur
uv run python scripts/release.py X.Y.Z --publish
```

Avec `--publish`, le programme :

1. exige un répertoire Git propre et les outils `git`, `gh` authentifié et `uv` ;
2. vérifie que `origin/<branche-active>` est un ancêtre de `HEAD` ;
3. change la version dans `pyproject.toml`, `install.sh`, `install.ps1`, `README.md` et `docs/guide-utilisateur.md` ;
4. lance Ruff, Pytest, puis `uv build` ;
5. crée un commit de release ;
6. pousse `HEAD` vers `origin/<branche-active>` ;
7. crée/pousse le tag `vX.Y.Z` et publie la release GitHub.

Point crucial : lancé depuis `staging`, il fait `git push origin HEAD:staging` et **ne touche pas `origin/main`**. La mise à jour de `main` doit continuer à passer par une pull request puis une fusion GitHub, conformément au workflow souhaité. La commande `--publish` crée des modifications distantes ; ne jamais l'exécuter sans demande explicite, distincte et actuelle de l'utilisateur.

## Déclaration de concentration NaOH

Le questionnaire de soude ne propose volontairement aucune valeur par défaut : une étiquette à `30 % m/m` avec densité `1,33 g/mL` correspond à `399 g/L`, alors que `30 % m/v` correspond à `300 g/L`.

Le prompt de `src/piscine_ph/cli.py` a été enrichi d'exemples de lecture d'étiquette/FDS et avertit de ne jamais deviner l'unité ou la densité. Les données réellement saisies sont archivées dans le protocole.

## Piste de travail : carbonate de sodium / pH+

Lire impérativement [docs/evolution-carbonate-sodium.md](docs/evolution-carbonate-sodium.md) avant toute modification de la chimie ou de la CLI.

Décision actuelle : ne pas traiter le pH+ carbonate comme une substitution directe de NaOH + bicarbonate.

- Le carbonate de sodium (`Na2CO3`) relève simultanément pH et TAC.
- Le bicarbonate est à privilégier quand il faut augmenter le TAC avec un effet limité sur le pH.
- Le carbonate peut être pertinent quand pH et TAC sont tous deux bas, mais le calcul dépend du pH, du TAC, du CO2 dissous et de la dureté ; aucune règle de trois entre doses existantes n'est valable.
- Le programme ne doit proposer cette alternative qu'après ajout d'un produit archivé, d'un calcul spécifique validé, d'un parcours CLI dédié et de tests sur les trois cas pH/TAC listés dans la note.

La note conserve aussi les références de prix France relevées le 6 septembre 2026. Elles sont indicatives, non pérennes et ne constituent pas une recommandation d'achat ou de dosage.

## Commandes de validation

```bash
uv run ruff check .
uv run pytest
uv build
git diff --check
```

Le 11 septembre 2026, `uv run ruff check .` est vert et `uv run pytest -q`
réussit avec 53 tests. Relancer les commandes ci-dessus avant tout commit qui
modifie le code ou les scripts de publication.

## Prochaine action recommandée

1. Recueillir le retour d'installation Windows de `v0.2.3`, qui contient le
   parcours auparavant porté par `test-cli-windows`.
2. Intégrer `staging` dans `main` via une pull request lorsque le périmètre est
   validé ; ne pas effectuer cette opération distante sans instruction.
3. Ne commencer l'implémentation du carbonate que dans un chantier distinct,
   avec des mesures/attentes chimiques explicites et des tests dédiés.
