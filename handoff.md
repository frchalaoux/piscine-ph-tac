# Handoff — `piscine-ph`

Mise à jour : 14 septembre 2026

## Ajustement local : largeur des archives

La page **Archives** utilise maintenant toute la largeur disponible du terminal,
au lieu de la limite de 72 colonnes des formulaires. Le tableau s'élargit avec
la fenêtre ; le défilement horizontal reste disponible sur les petits terminaux.
Modification locale dans le CSS de `src/piscine_ph/tui.py` (`#history-content`).

Validation : redimensionnement Textual à 80, 180 et 220 colonnes avec une ligne
contenant deux noms d'archives ; aucun défilement horizontal à 180 et 220.
Ruff et les deux tests ciblés de lecture/sélection des archives passent.
Aucun commit ni changement distant effectué pour cet ajustement.

## Ajustement local : action de désinfection visible

Le haut de la page désinfection présente maintenant un encadré avec un titre
gras et souligné, la mesure de chlore, les seuils, le dernier CYA et la suite
adaptée. `ProtocolService.disinfection_action()` fournit aussi ce message à
l'assistant guidé. Lorsque les galets sont consommés et le chlore trop bas,
un bouton ouvre le journal de recharge. Les galets en place, le CYA élevé et
le chlore dans/au-dessus de la plage ne déclenchent pas cette proposition.
Après une recharge postérieure à la mesure, le bandeau indique le nombre de
galets déjà ajoutés et propose un nouveau contrôle, sans demander un autre ajout.

Cas utilisateur vérifié sur une copie de l'archive du 14 septembre dans
`/Users/frchalaoux/Desktop/piscine-ph-test` : chlore 0,5 ppm, plage 1–4 ppm,
2 galets ajoutés après la mesure, CYA 20 ppm. Les données originales restent
inchangées. Cinq nouveaux cas de test couvrent le parcours par clic et les
conditions de non-recharge. Aucun changement distant.

## Reprise rapide

Le projet est une application locale Python (CLI Typer et TUI Textual) qui
archive les mesures d’une piscine et guide des corrections pH/TAC par lots
confirmés. La logique métier vit dans `ProtocolService` ; les interfaces ne
doivent pas recalculer leurs propres règles.

La version **0.2.5** est publiée depuis `staging` :
[release v0.2.5](https://github.com/frchalaoux/piscine-ph-tac/releases/tag/v0.2.5).

- Commit des évolutions : `9a5a750`, poussé sur `feat/sodium-carbonate-model`.
- Fusion dans `staging` : `e25c03a`.
- Commit de release et cible du tag annoté `v0.2.5` : `feba09e`.
- Branche de travail actuelle : `staging`. Les anciennes versions sont conservées.

La publication a été explicitement demandée par l'utilisateur le 13 septembre.
Toute autre publication exige une nouvelle demande explicite, distincte et
actuelle ; l'autorisation de v0.2.5 ne vaut pas pour une version suivante.

Préférence durable confirmée après la publication : **intégrer les branches
via une PR**, avec description des changements et des validations avant
fusion, notamment branche de travail → `staging` et `staging` → `main`.
La fusion locale suivie d'un push direct utilisée pour v0.2.5 ne doit pas
devenir le workflow habituel. Une demande générale de merge implique une PR,
sauf instruction explicite contraire. Cette préférence n'autorise aucune
opération distante à elle seule ; **keep cool** reste applicable.

L’installation Windows de `v0.2.4` a été validée par un utilisateur : aucun
travail Windows n’est attendu à ce stade.

## Fonctionnalités locales déjà ajoutées

### Parcours et archivage

- Quatre entrées métier sont disponibles dans le menu TUI **Protocoles** :
  **Mesurer l’eau**, **Corriger le pH**, **Corriger le TAC** et **Gérer la
  désinfection**.
- Les archives terminales ou annulées peuvent être enchaînées. La fille
  enregistre `parent_archive_name` et `parent_protocol_id`, et pH/TAC sont
  préremplis uniquement comme valeurs à recontrôler dans le bassin.
- En CLI, l’enchaînement s’effectue avec
  `piscine-ph start --follow-up-from NOM_ARCHIVE`.
- Un mode générique `surveillance_eau` a été ajouté. Il n’exige pas un pH
  supérieur à une cible et accepte le chlore libre facultatif ; il peut donc
  servir lorsque pH et TAC sont déjà aux valeurs de référence.

### Assistant guidé et règles déterministes

- L’Assistant guidé est la page initiale du TUI. La case **Mode manuel**
  conserve les mêmes validations mais empêche le retour automatique vers
  l’assistant.
- `ProtocolService.guided_action()` détermine une seule action suivante à
  partir de l’état archivé : préparer le lot, saisir la mesure de confirmation,
  surveiller, gérer la désinfection ou consulter l’historique. Il ne verse ni
  ne valide jamais un produit lui-même.
- Pour `surveillance_eau`, après une première mesure,
  `water_follow_up_action()` propose une suite déterministe, sans calculer de
  dose :
  1. TAC sous la référence : corriger le TAC en premier ;
  2. puis pH sous ou au-dessus de la référence : ouvrir le parcours pH adapté ;
  3. puis chlore hors des bornes déclarées : gérer la désinfection ;
  4. sinon : terminer et archiver le relevé.
- Un TAC trop haut n’entraîne volontairement aucune baisse automatique.
- Lorsqu’une suite est choisie, le relevé est terminé et la nouvelle archive
  est liée à son parent.

### Sécurité chimique

- Les lots de soude, bicarbonate et acide restent limités et demandent une
  nouvelle mesure après ajout.
- Le bouton d’acide prépare automatiquement le lot plafonné par la notice ;
  le champ de volume manuel, ambigu pour un utilisateur non averti, a été
  retiré.
- Le carbonate de sodium est une **étude sans dosage**, jamais une conversion
  de NaOH + bicarbonate. Elle archive le produit, sa pureté et la source de la
  pureté, borne mathématiquement le TAC et affiche le risque pH. Elle ne crée
  aucune dose à verser.
- Exemple CLI :

  ```bash
  piscine-ph start --no-guided --mode etude_carbonate_sodium \
    --initial-ph 6.8 --initial-tac 50 \
    --carbonate-product-label "pH+ de l'etiquette" \
    --carbonate-purity-percent 99 --carbonate-purity-source fds --disinfection chlore_non_stabilise --electrolysis non_installe --ph-regulator non_installe --tablets non_necessaires
  ```

### FDS et documentation

- La recherche et la lecture de FDS restent entièrement manuelles ; aucune IA
  n’est intégrée à ce parcours.
- `docs/rechercher-une-fds.md` explique où chercher la FDS officielle, comment
  vérifier le produit exact et quelles sections relever.
- `docs/choisir-un-protocole.md` explique le rôle, les entrées et les limites
  de chaque parcours.
- Les guides utilisateur, développeur, formats JSON et produits/sécurité ont
  été mis à jour et reliés depuis le README.

## Ajustement TUI : distinguer les mesures

Le panneau **Mesurer l’eau** mélangeait deux actions, ce qui créait une vraie
ambiguïté : « créer/archiver un relevé » et « enregistrer une mesure attendue ».

La correction est dans le working tree : les deux zones sont maintenant
**mutuellement exclusives**.

- Sans protocole actif : seule la carte **Nouveau relevé d’eau** est visible.
  Elle demande les mesures initiales et le bouton s’appelle
  **Enregistrer ce premier relevé**.
- Avec un relevé/protocole actif : cette carte est masquée. Seule une zone de
  suivi est visible, contextualisée comme **Ajouter une mesure au relevé**,
  **Mesure de confirmation après acide/soude/bicarbonate** ou **Nouvelle mesure
  de surveillance**.
- Le chlore libre est visible seulement s’il est pertinent : facultatif pour
  un relevé d’eau, requis dans les surveillances qui le demandent, absent des
  confirmations pH/TAC.

Les modifications concernent principalement
`PiscinePhTui._refresh_dashboard_and_forms()` dans `src/piscine_ph/tui.py`.
Un test de non-confusion a été ajouté :
`test_tui_measure_page_distinguishes_a_new_reading_from_a_follow_up`.

## Dernière correction TUI : boutons de parcours après clôture

Défaut reproduit après la confirmation d'une baisse de pH à la cible : les
boutons **Corriger le pH**, **Corriger le TAC** et **Désinfection** semblaient
inactifs sur l'accueil. Ils ouvraient leur page, mais le déplacement automatique
du focus lors du masquage de l'accueil déclenchait un `TabPane.Focused` qui
réactivait aussitôt l'accueil. **Mesurer l'eau** échappait à ce défaut grâce à
son transfert explicite du focus vers le formulaire.

La correction est centralisée dans `PiscinePhTui._open_page()` : libérer le
focus avec `self.set_focus(None)` avant de changer de page. Le premier soupçon
portait sur les notifications ; il a été écarté, le problème étant reproduit
sans notifications affichées. Aucun changement de leur présentation n'a été
conservé.

Le test `test_tui_guided_workflow_completes_an_acid_correction` couvre désormais
un vrai clic sur chacun des quatre boutons après clôture et vérifie la page
effectivement affichée. Avant correction : trois échecs sur quatre ; après
correction : quatre réussites. Les anciens tests s'arrêtaient au retour à
l'accueil et ne détectaient donc pas ce défaut. Le cas désinfection vérifie
aussi le démarrage du nouveau parcours par clic sur son bouton.

Deux assertions devenues obsolètes lors de l'ajustement précédent de la page
Mesurer l'eau ont été alignées sur le libellé de surveillance actuel : elles
attendaient encore « Surveillance pH haut » dans les instructions de mesure.

## Dernier ajustement : bilan et consultation de la désinfection

Le suivi de désinfection renvoyait toujours à une nouvelle mesure après chaque
enregistrement. Les valeurs étaient persistées, mais le guidage ne présentait
pas clairement le bilan ni les seuils déjà enregistrés.

- Après une mesure de désinfection, le mode guidé ouvre le bilan dans
  **Gérer la désinfection** ; `guided_action()` propose aussi ce bilan lors
  d'une reprise. Le mode manuel conserve la page courante.
- Le bilan et **Mesurer l'eau** affichent les valeurs initiales, les dernières
  valeurs, les seuils min/max et le chemin absolu du fichier. Les relevés datés
  sont consultables dans une section dépliable.
- **Archives** propose une lecture des valeurs et de tous les relevés sans
  ouvrir le JSON. La sélection est conservée lors d'une actualisation.
- L'accueil garde ses raccourcis pendant un suivi actif. L'accès à la mesure
  place désormais le focus sur le champ actif, sans viser la création masquée.
- **Terminer ce suivi et choisir la suite** appelle
  `complete_disinfection_monitoring()` : au moins une mesure est requise, aucun
  lot ne doit être en attente. La clôture ne vaut pas validation de l'eau.
  Elle prépare une suite liée, avec pH/TAC et seuils min/max à vérifier.
- Le formulaire de création est masqué pendant le suivi de désinfection actif.
- Le résumé JSON accepte maintenant un chlore non mesuré (`None`).

La persistance reste au même format JSON, dans `data/protocoles` relatif au
dossier de lancement. Aucun déplacement de données ni modification distante.

## Installation obligatoire avant tout nouveau protocole

Directive utilisateur du 13 septembre : **déclarer la désinfection et les
appareils en premier, avant tout protocole**, et pas seulement la désinfection.

- `ProtocolService.start()` refuse la création si l'un des quatre paramètres
  manque : source de désinfection, électrolyseur, régulateur pH, état des galets.
  Le contrôle est partagé entre CLI et TUI, y compris pour l'étude carbonate.
- `aucune` décrit une absence de désinfection active ; `non_installe` décrit
  l'absence d'électrolyseur ou de régulateur. Ces valeurs se distinguent de
  `inconnu`, qui ne permet pas de démarrer un nouveau protocole.
- Le TUI présente la déclaration en premier. Choisir pH, TAC ou Mesurer l'eau
  sans contexte ouvre cette section, puis la validation reprend la destination
  choisie. Le questionnaire CLI demande aussi le contexte avant le parcours.
- Les créations TUI utilisent les sélecteurs déclarés au lieu de fabriquer un
  `TreatmentContext()` vide. La fin d'une correction prépare une suite liée et
  reprend son contexte, y compris le profil des galets.
- Les archives anciennes restent lisibles. Le guidage signale les paramètres
  manquants. **Archives → Reprendre ce contexte de traitement…** prépare les
  champs depuis une archive choisie sans modifier le suivi actif avant leur
  enregistrement explicite.
- Une nouvelle création CLI non guidée exige les quatre options ; un
  `--follow-up-from` reprend le contexte parent, sauf options explicites.
- Avant le démarrage, le contexte TUI est préparé en mémoire ; il est persisté
  dans le nouveau protocole. Il n'existe pas de fichier global d'installation.

## Validation actuelle (contexte préalable)

- Suite complète : **113 passed**.
- `uv run ruff check .`, `uv build` et `git diff --check` : verts.
- L'utilisateur a demandé le commit, le push, l'intégration à `origin/staging`
  et la publication de **v0.2.5**. Cette autorisation est propre à cette opération.
- Publication terminée par `scripts/release.py 0.2.5 --publish` : tag annoté,
  branche `origin/staging` et release GitHub vérifiés au commit `feba09e`.
- Le script de publication a relancé les **113 tests** avec succès, puis Ruff,
  la construction et la vérification des différences sont verts.
- Installation isolée depuis l'archive GitHub du tag, sous Python 3.11 :
  `piscine-ph --help` fonctionne. Aucun outil global utilisateur n'a été remplacé.
- Les notes de release décrivent le contexte obligatoire et les nouveaux parcours.

## Validation précédente (bilan de désinfection)

- Suite complète : **93 passed**.
- Après activation de la sélection par ligne dans Archives : les deux tests
  ciblés de consultation/sélection et de reprise/clôture/enchaînement passent.
  Le test de sélection est nouveau (94 tests présents au total).
- `uv run ruff check .`, `uv build` et `git diff --check` : verts.
- Aucun commit ni publication.

## Validation précédente (après la correction des boutons)

- `uv run ruff check .` : vert.
- `uv run pytest -q` : **87 passed**.
- `uv build` : archive source et wheel `0.2.4` construites.
- `git diff --check` : vert.
- Aucun commit, tag ou changement distant effectué.

## Validation précédente (avant la correction des boutons)

- `uv run ruff check .` : vert après le dernier ajustement.
- Les deux tests TUI ciblés suivants sont verts après le dernier ajustement :

  ```bash
  uv run pytest \
    tests/test_tui.py::test_tui_measure_page_distinguishes_a_new_reading_from_a_follow_up \
    tests/test_tui.py::test_tui_starts_the_water_monitoring_from_its_dedicated_page -q
  ```

  Résultat : `2 passed`.

- Avant le tout dernier changement de libellés/visibilité, Ruff, la suite de
  tests et `uv build` avaient été exécutés avec succès. Relancer impérativement
  la validation complète avant tout commit :

  ```bash
  uv run ruff check .
  uv run pytest
  uv build
  git diff --check
  ```

## État Git

Les évolutions décrites ci-dessus sont commitées et publiées. La version déclarée
est `0.2.5`. `staging` contient aussi la mise à jour documentaire de reprise
postérieure au tag ; le code publié reste celui de `feba09e`.

## Suite recommandée

1. Faire confirmer dans le terminal utilisateur la navigation depuis l'accueil
   après une correction pH terminée, puis le bilan de désinfection après mesure,
   l'accès aux valeurs archivées et **Terminer ce suivi et choisir la suite**.
2. Vérifier manuellement le panneau **Mesurer l’eau** dans ces quatre états :
   aucun protocole, relevé d’eau actif, mesure après acide, mesure après
   bicarbonate.
3. Faire relire la terminologie du parcours guidé par un utilisateur novice
   avant tout nouveau chantier de calcul chimique.
4. Ne transformer l’étude carbonate en dose opérationnelle qu’après données
   de mesures réelles, limites de lots/attente/arrêt validées et documentation
   produit précise. Ne jamais dériver cette dose en combinant des doses de
   soude et de bicarbonate.
