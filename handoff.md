# Handoff — `piscine-ph`

Date de préparation : 9 septembre 2026

## Objectif du projet

`piscine-ph` est une CLI Python/Typer qui journalise une correction progressive du pH et du TAC d'une piscine. Le protocole actuellement implémenté distingue :

- la soude NaOH pour les étapes de relèvement du pH ;
- le bicarbonate de sodium (`NaHCO3`) pour la remontée contrôlée du TAC ;
- les mesures intermédiaires et les lots limités comme garde-fous.

Le dépôt public est [frchalaoux/piscine-ph-tac](https://github.com/frchalaoux/piscine-ph-tac).

## État Git à reprendre

- Branche locale active : `staging`.
- `staging` pointe sur `a721f2d` (`docs: ajouter le handoff et la piste carbonate`) et est en avance d'un commit sur `origin/staging`, qui pointe sur `5b5bfd9` (`version adjustement`).
- `main` locale et `origin/main` pointent sur `f0ce158`, merge de la PR n° 6 depuis `staging` ; `main` contient donc l'état publié de `staging` à ce moment.
- Tags/releases publiés : `v0.1.0` et `v0.1.1`.
- La release actuelle est [v0.1.1](https://github.com/frchalaoux/piscine-ph-tac/releases/tag/v0.1.1).

### Release `v0.1.2` interrompue

Une première tentative de `uv run python scripts/release.py 0.1.2 --publish` a mis à jour les six fichiers de release, puis s'est arrêtée après `git diff --check`, avant le `git add` et le commit. Aucun tag `v0.1.2` ni release n'a été créé.

Les six modifications attendues restent locales :

- `pyproject.toml` ;
- `uv.lock` ;
- `install.sh` et `install.ps1` ;
- `README.md` et `docs/guide-utilisateur.md`.

`scripts/release.py` et `docs/guide-developpeur.md` contiennent aussi une correction locale : le script indexe désormais `uv.lock`, contrôle l'index et propose `--resume`. Commiter ce correctif séparément avant de reprendre la release, sans ajouter les six fichiers de release, puis lancer :

```bash
uv run python scripts/release.py 0.1.2 --publish --resume
```

## Installation utilisateur

L'installation est versionnée et ne dépend pas de `main` :

```bash
curl -LsSf https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.1.1/install.sh | sh
```

Sous PowerShell :

```powershell
irm https://raw.githubusercontent.com/frchalaoux/piscine-ph-tac/v0.1.1/install.ps1 | iex
```

Les scripts installent `uv` seulement s'il est absent du `PATH`, puis installent le paquet depuis le tag. Ils ne réinstallent pas `uv` ou Python lorsqu'une installation compatible existe ; `uv` peut télécharger un Python compatible si nécessaire. Après une première installation de `uv`, l'utilisateur peut devoir rouvrir son terminal avant d'exécuter `piscine-ph start`.

## Publication de versions

Le programme `scripts/release.py` automatise une release depuis **la branche locale active**.

```bash
# Simulation, sans modifier de fichier
uv run python scripts/release.py 0.1.2

# Publication complète
uv run python scripts/release.py 0.1.2 --publish
```

Avec `--publish`, le programme :

1. exige un répertoire Git propre et les outils `git`, `gh` authentifié et `uv` ;
2. vérifie que `origin/<branche-active>` est un ancêtre de `HEAD` ;
3. change la version dans `pyproject.toml`, `install.sh`, `install.ps1`, `README.md` et `docs/guide-utilisateur.md` ;
4. lance Ruff, Pytest, puis `uv build` ;
5. crée un commit de release ;
6. pousse `HEAD` vers `origin/<branche-active>` ;
7. crée/pousse le tag `vX.Y.Z` et publie la release GitHub.

Point crucial : lancé depuis `staging`, il fait `git push origin HEAD:staging` et **ne touche pas `origin/main`**. La mise à jour de `main` doit continuer à passer par une pull request puis une fusion GitHub, conformément au workflow souhaité.

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

La dernière validation fonctionnelle enregistrée a donné : Ruff OK et 20 tests Pytest passants. Relancer les commandes ci-dessus avant tout commit qui modifie le code ou les scripts de publication.

## Prochaine action recommandée

1. Commiter/pousser le correctif de `scripts/release.py` et de la documentation développeur, en laissant les six fichiers de `v0.1.2` non indexés.
2. Reprendre `v0.1.2` avec `--publish --resume` ; vérifier le journal jusqu'à `gh release create`.
3. Ne commencer l'implémentation du carbonate que dans un chantier distinct, avec des mesures/attentes chimiques explicites et des tests dédiés.
