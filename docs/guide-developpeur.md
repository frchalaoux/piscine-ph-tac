# Guide développeur — piscine-ph

Ce document décrit comment installer, modifier et vérifier `piscine-ph`. Il complète le [guide utilisateur](guide-utilisateur.md) et la [documentation du protocole](protocole_ph_tac.md).

## Pré-requis et environnement

Le projet nécessite Python 3.11 ou plus récent et [uv](https://docs.astral.sh/uv/). Depuis la racine du dépôt :

```bash
uv sync
```

Cette commande crée ou met à jour `.venv/`, installe les dépendances de production et de développement, puis verrouille leurs versions dans `uv.lock` si nécessaire.

Les commandes utiles pendant le développement sont :

```bash
uv run piscine-ph --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Pour appliquer le formatage :

```bash
uv run ruff format .
```

Ne pas modifier `uv.lock` à la main : utiliser `uv add`, `uv remove` ou `uv lock`.

## Publier une version

Une version se prépare et se publie depuis la branche de travail courante, normalement `staging`. Le script ne modifie jamais la branche locale `main` et une publication depuis `staging` cible exclusivement `origin/staging`. Le tag Git est commun au dépôt, mais il pointe sur le commit de `staging` publié ; il ne fusionne pas cette branche dans `main`. La mise à jour de `main` se fait ensuite par une pull request sur GitHub.

Le programme exige `git`, `gh` authentifié et `uv`. Il refuse de publier si la branche distante correspondante n'est pas comprise dans le commit courant ou si le tag existe déjà.

### Cas normal : laisser `--publish` faire toute la release

Ne modifier, n'indexer ni ne committer aucun des fichiers de version à la main. Partir d'un répertoire de travail propre sur la branche visée, par exemple `staging` :

```bash
git status --short
git switch staging
git pull --ff-only origin staging
uv run python scripts/release.py X.Y.Z
# Exécuter seulement après la demande explicite et actuelle de l'utilisateur.
uv run python scripts/release.py X.Y.Z --publish
```

La première commande Python est une simulation : elle ne modifie aucun fichier.
La seconde exécute, dans cet ordre, les contrôles, la mise à jour des fichiers,
la construction, le commit `release: preparer la version X.Y.Z`, le push vers
`origin/staging`, le tag annoté `vX.Y.Z`, son push, puis la release GitHub.
Elle modifie l'état distant : ne jamais l'exécuter sans une demande explicite,
distincte et actuelle de l'utilisateur.

### Fichiers inclus et journal attendu

Le script commence avec un répertoire de travail propre. Il modifie et indexe **uniquement** les fichiers suivants :

```text
pyproject.toml
uv.lock
install.sh
install.ps1
README.md
docs/guide-utilisateur.md
```

`uv.lock` est inclus parce que `uv run` peut le mettre à jour après le changement de version. Les archives construites dans `dist/` restent ignorées par Git. Les notes de travail, handoffs et autres fichiers de documentation ne sont jamais ajoutés automatiquement : leur inclusion doit rester une décision explicite.

Après `git diff --check`, la sortie doit impérativement afficher, dans cet ordre, `git add`, `git diff --cached --check`, `git commit`, les pushes, le tag puis `gh release create`. Si le journal s'arrête avant `git add`, la release n'a pas été committée ni publiée ; vérifier `git status`, `git log` et les tags avant toute nouvelle tentative.

### Cas de reprise : commit et push effectués, mais aucun tag

Ce cas arrive si les six fichiers ont été commités et poussés manuellement (par exemple depuis l'interface de VS Code), ou si le script s'est arrêté après ce commit. Ne créez pas manuellement le tag avec `git tag` ni la release avec `gh release create` : laissez le script terminer les étapes restantes.

Vérifier d'abord que l'arbre est propre, que le commit courant contient bien la version visée et qu'aucun tag n'existe :

```bash
git status --short
git log -1 --oneline
git ls-remote --tags origin vX.Y.Z
```

Si la première commande ne produit rien et que la dernière ne produit aucune ligne, reprendre ainsi :

```bash
uv run python scripts/release.py X.Y.Z --publish --resume
```

`--resume` exige que `pyproject.toml` porte déjà `X.Y.Z`. Il relance les
contrôles et distingue deux situations :

- les six fichiers sont encore modifiés : il les indexe et crée le commit de release ;
- ils sont déjà committés : il ne crée pas de deuxième commit et reprend depuis `HEAD`.

Dans les deux cas, il pousse `HEAD` vers la branche distante active (même s'il
est déjà à jour), crée et pousse `vX.Y.Z`, puis publie la release GitHub. Il
refuse tout fichier modifié hors de la liste de release. Cette reprise reste
soumise à la même demande explicite de publication.

## Évolutions en attente

La note [sur le carbonate de sodium (pH+)](evolution-carbonate-sodium.md) conserve la comparaison avec la lessive de soude et le bicarbonate, les prix de référence, les limites de sécurité et le plan d'implémentation. Ne pas ajouter ce produit au calcul actuel sans suivre les prérequis listés dans cette note.

## Tester une commande avant publication

L'entrée de script `piscine-ph` installée globalement par un utilisateur pointe
sur le tag qu'il a installé. Elle ne reflète pas les modifications non publiées
du répertoire de travail. Tester les commandes, dont la TUI, depuis le dépôt :

```bash
uv run piscine-ph tui
uv run piscine-ph tui --help
```

Pour tester le comportement d'une installation globale avec le code local :

```bash
uv tool install --editable --reinstall .
piscine-ph tui
```

Cette commande modifie l'environnement d'outils global de la machine, mais le
lie au répertoire local : les changements de code Python sont visibles sans
réinstallation. Après un changement de dépendance, de `pyproject.toml` ou de
l'entrée de script, relancer `uv tool install --editable --reinstall .`. Ce
mode est réservé au développement ou aux tests ; il ne remplace ni les tests,
ni le build, ni la publication. Après une release, l'utilisateur doit installer
le tag publié avec le script d'installation de cette release ; ne lui demandez
pas d'installer directement une branche ou un répertoire de développement.

Lorsque `piscine-ph tui` est ajouté, vérifier explicitement les trois niveaux :

1. `uv run piscine-ph tui --help` depuis le dépôt ;
2. les tests Textual automatisés ;
3. l'installation depuis le tag de release publié dans un environnement propre.

## Organisation du code

```text
src/piscine_ph/
  models.py       # Contrat des données JSON avec Pydantic
  defaults.json   # Valeurs opérationnelles versionnées par défaut
  settings.py     # Lecture et validation de defaults.json
  chemistry.py    # Bilans de matière et contrôle carbonate
  repository.py   # Lecture/écriture atomique et recherche des archives
  service.py      # Règles métier et transitions entre étapes
  cli.py          # Commandes et affichage Typer
  tui.py          # Menus et formulaires Textual, sans règle métier propre
tests/
  test_chemistry.py
  test_settings.py
  test_service.py
  test_tui.py
docs/              # Documentation versionnée
data/protocoles/   # Journaux opérationnels, ignorés par Git
```

Le sens des dépendances doit rester simple : `cli` et `tui` appellent `service`,
et `service` utilise `repository`, `chemistry` et `models`. La TUI ne doit
jamais appeler une commande Typer ou interpréter son texte : elle appelle les
méthodes du service directement. Les calculs chimiques ne doivent pas dépendre
de Typer, Textual ou du système de fichiers. Cette séparation permet de tester
les règles métier sans terminal ni fichiers réels.

## Documentation du code source

Chaque module de `src/piscine_ph/` porte un docstring décrivant sa responsabilité et ses limites. Chaque classe, fonction et méthode publique doit également expliciter :

- les unités d'entrée et de sortie lorsqu'il y en a (`mL`, `L`, `kg`, `mol/L`, `ppm CaCO3`) ;
- l'effet sur l'état et le journal, pour une méthode du service ;
- les préconditions qui protègent une mesure ou un cumul ;
- les limites scientifiques lorsqu'un résultat est théorique.

Les commentaires dans le code sont réservés à une décision qui ne se lit pas directement dans l'instruction — par exemple, une tolérance, une incompatibilité d'archive ou une limite du modèle carbonate. Ils ne doivent pas répéter le code. Lorsqu'une modification rend un docstring faux, corriger le docstring dans le même changement.

## Paramètres et constantes

Les valeurs opérationnelles par défaut sont dans `src/piscine_ph/defaults.json` : volume de bassin, objectifs pH/TAC, seau, concentration déclarée de la soude et portions indicatives. Elles sont lues et validées par `settings.py`. Le détail de chaque clé et son unité sont dans la [documentation de configuration](configuration.md).

Les constantes physico-chimiques, les limites de préparation du seau, les tolérances du modèle et les bornes du solveur restent dans `chemistry.py`. Elles sont nommées, typées, commentées et testées : une modification doit être justifiée scientifiquement, testée et documentée. Les déplacer dans un fichier éditable faciliterait un changement non contrôlé du modèle ou de ses protections.

## Modèle d'état et persistance

`ProtocolState` dans `models.py` est le format de référence sérialisé dans chaque archive JSON. Toute modification compatible de ce modèle doit conserver des valeurs par défaut pour les nouveaux champs afin que les anciennes archives restent lisibles.

Les étapes possibles sont définies par `ProtocolStep` :

```text
naoh_vers_palier -> tac_vers_80 -> naoh_final -> termine
                     \-> annule
```

Les transitions ne sont effectuées que dans `ProtocolService` :

| Méthode | Effet principal |
| --- | --- |
| `start` | Crée une archive, ou reprend le protocole actif. |
| `prepare_naoh` | Crée une dose de NaOH en attente. |
| `record_naoh_measurement` | Confirme la dose avec une mesure et actualise l'étape. |
| `plan_bicarbonate` | Crée un apport de bicarbonate en attente. |
| `record_bicarbonate_measurement` | Confirme l'apport et vérifie le TAC cible. |
| `cancel_pending_naoh` | Retire seulement une dose de soude non versée. |
| `correct_last_measurement` | Corrige une lecture, sans retirer le produit comptabilisé. |
| `cancel_protocol` | Archive le protocole comme annulé sans effacer son historique. |

`JsonProtocolRepository` recrée `data/protocoles/` à son initialisation si le dossier est absent, ce qui rend un clone GitHub immédiatement utilisable. `save()` écrit ensuite d'abord un fichier `.tmp`, puis le remplace : cette écriture atomique évite normalement une archive partiellement écrite si le programme est interrompu.

Une archive est active tant que son étape n'est ni `termine` ni `annule`. `start` reprend la plus récente archive active ; `start --force` crée une nouvelle archive sans modifier la précédente.

## Invariants à préserver

Ces règles sont importantes car elles évitent de fausser le suivi réel du bassin :

- Une dose de NaOH en attente doit être mesurée ou annulée avant d'en préparer une autre.
- Une dose annulée n'est jamais ajoutée à `cumulative_additions`.
- Une mesure confirmant un ajout crée un enregistrement immuable de produit (`NaOHDoseRecord` ou `BicarbonateRecord`). Une correction ne modifie que ses valeurs de mesure et de cohérence.
- Les cumuls sont recalculés depuis les doses enregistrées par `refresh_cumulative_additions`, jamais incrémentés à partir des saisies de l'interface.
- Le TAC manuel est validé par rapport à `tac_measurement_step_ppm`, actuellement 10 ppm. Ne pas accepter une précision absente du test utilisé.
- Seul un TAC mesuré supérieur ou égal à la cible autorise le passage à la phase finale de pH.
- Toutes les mutations de `ProtocolState` passent par le service puis sont immédiatement sauvegardées par le dépôt.

Si une nouvelle commande modifie l'état, ajouter son événement avec `state.add_event(...)`, mettre à jour `updated_at` par cette méthode et écrire un test de transition.

## Calculs chimiques et limites

`ChemistryCalculator` contient les valeurs physiques, les bilans d'ajout et le modèle carbonate fermé à 25 °C.

- La concentration de NaOH est configurable dans `ProtocolConfig` et vaut 300 g/L par défaut.
- Le bicarbonate est calculé en équivalents de TAC exprimés en ppm CaCO3.
- La préparation du seau conserve 20 % de garde libre et limite le NaOH à 10 % du volume utile.
- Les propositions 250/100/50 mL sont des repères opérationnels dans `suggested_naoh_ml`, pas une prédiction de dose suffisante.

La fonction `verify()` est un contrôle de cohérence, non un pilote automatique. Lorsque le carbone dissous inféré dépasse 0,01 mol/L, elle ne retourne volontairement pas de pH théorique : le modèle fermé est hors de son domaine utile. Dans ce cas, conserver l'alerte, le bilan TAC et privilégier les mesures réelles.

Avant de changer une constante, une tolérance, une formule ou l'unité d'une valeur, mettre à jour à la fois :

1. les tests concernés ;
2. `docs/protocole_ph_tac.md` ;
3. le guide utilisateur si cela change une commande ou le protocole appliqué.

## Ajouter ou modifier une commande CLI

1. Placer la règle métier dans `ProtocolService`, pas dans `cli.py`.
2. Ajouter une commande Typer mince qui valide les options, appelle le service et affiche le résultat.
3. Déterminer la prochaine commande avec `show_next_command(state)` lorsqu'une étape est terminée.
4. Ajouter ou adapter les tests de service ; ajouter un test chimique si une formule évolue.
5. Documenter la commande dans le guide utilisateur, le README si elle est principale, et ce guide si elle change l'architecture.

Toute commande CLI doit avoir une entrée TUI fonctionnelle, ou être explicitement
représentée comme l'interface déjà ouverte (`tui`) ou comme le guide de
navigation (`menu`). CLI et TUI appellent exclusivement `ProtocolService` : ne
jamais porter une validation, un calcul ou une écriture JSON dans une seule des
deux interfaces. Mettre à jour l'onglet **Commandes CLI** et son test à chaque
ajout ou suppression de commande.

Pour tester une commande manuellement sans toucher aux données d'exploitation, il est préférable de tester le service avec un répertoire temporaire, comme dans les tests. La fonction CLI `service()` utilise volontairement `data/protocoles/` en exécution normale.

## Tests et qualité

Les tests de chimie vérifient les conversions et les cas où le modèle pH doit être désactivé. Les tests de service vérifient les transitions, l'annulation, la reprise d'archive, la correction de mesure, les cumuls et la migration de l'ancien JSON. Les tests Textual vérifient que l'interface peut enregistrer les mesures des deux parcours et qu'elle nomme explicitement la désinfection active et chaque appareil.

### Contexte de traitement

`TreatmentContext.disinfection_method` est la **source active unique** de chlore :
`electrolyse_au_sel`, `galets_stabilises`, `dichlore_stabilise`,
`chlore_non_stabilise` ou `inconnu`. Les états de l'électrolyseur au sel, du
doseur de galets stabilisés et du régulateur pH sont des données séparées ; ils
décrivent les appareils installés sans constituer une seconde désinfection
active. La CLI accepte `--disinfection`; `--chlorine` demeure un alias de
compatibilité.

La migration Pydantic de `TreatmentContext` lit l'ancien champ
`chlorine_treatment` des archives v1–v3. Si cette ancienne valeur est
`chlore_non_stabilise` et qu'un état d'électrolyseur est déclaré, elle devient
`electrolyse_au_sel`; sinon la valeur est reprise telle quelle. Toute évolution
de ce contrat doit préserver cette lecture, compléter les tests de migration et
mettre à jour `docs/fichiers-json.md`.

Avant un commit, exécuter :

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Ajouter au minimum un test de non-régression pour tout bug corrigé. Les tests ne doivent jamais dépendre d'un fichier dans `data/protocoles/` : utiliser le fixture `tmp_path` de pytest.

## Données et Git

Les journaux de bassin sont des données opérationnelles, pas du code. Ils sont enregistrés dans `data/protocoles/` et ignorés par Git. Ne pas ajouter ces fichiers, `.venv/`, les fichiers `.tmp` ou des résultats de tests au dépôt.

Les documents de `docs/`, les fichiers de `src/`, les tests, `pyproject.toml` et `uv.lock` doivent en revanche être versionnés. Vérifier le contenu avant chaque commit :

```bash
git status --short
git diff --check
```

## Compatibilité des archives

Le dépôt tente une migration unique de l'ancien fichier `suivi_protocole_naoh_tac.json` lorsqu'il est présent. Cette migration crée une nouvelle archive et laisse toujours le fichier source intact.

Pour toute évolution incompatible du JSON, augmenter `ProtocolState.version`, conserver un chemin de migration explicite dans `repository.py` et ajouter un échantillon d'archive ancienne dans les tests. Ne jamais supprimer ou réécrire silencieusement une archive utilisateur existante.
