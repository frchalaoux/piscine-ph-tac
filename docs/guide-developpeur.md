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

Le programme `scripts/release.py` remplace la version dans `pyproject.toml`, les deux installateurs et la documentation. Avec `--publish`, il lance les contrôles, construit le paquet, crée le commit, pousse `HEAD` vers la branche distante portant le même nom que la branche locale active, crée le tag annoté et publie la release GitHub. Une release lancée depuis `staging` met donc à jour `origin/staging`, jamais `origin/main`.

Depuis un répertoire de travail propre, simuler d'abord la version suivante :

```bash
uv run python scripts/release.py 0.1.1
```

Puis la publier :

```bash
uv run python scripts/release.py 0.1.1 --publish
```

Le programme exige `git`, `gh` authentifié et `uv`. Il refuse de publier si la branche distante correspondante n'est pas comprise dans le commit courant ou si le tag existe déjà.

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
tests/
  test_chemistry.py
  test_settings.py
  test_service.py
docs/              # Documentation versionnée
data/protocoles/   # Journaux opérationnels, ignorés par Git
```

Le sens des dépendances doit rester simple : `cli` appelle `service`, `service` utilise `repository`, `chemistry` et `models`. Les calculs chimiques ne doivent pas dépendre de Typer ou du système de fichiers. Cette séparation permet de tester les règles métier sans terminal ni fichiers réels.

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

Pour tester une commande manuellement sans toucher aux données d'exploitation, il est préférable de tester le service avec un répertoire temporaire, comme dans les tests. La fonction CLI `service()` utilise volontairement `data/protocoles/` en exécution normale.

## Tests et qualité

Les tests de chimie vérifient les conversions et les cas où le modèle pH doit être désactivé. Les tests de service vérifient les transitions, l'annulation, la reprise d'archive, la correction de mesure, les cumuls et la migration de l'ancien JSON.

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
