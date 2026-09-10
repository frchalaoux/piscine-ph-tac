# Surveillance : pH haut, TAC imparfait et chlore à ajuster

Ce parcours sert lorsqu'un bassin a un pH au-dessus de la cible — par exemple
au-dessus de 7,2 — et que le TAC, le chlore et les appareils ne sont pas dans
leur situation habituelle. Il enregistre les mesures et produit des alertes de
conduite à tenir. Il ne calcule **aucune dose d'acide ni de chlore**.

Cette séparation est volontaire : la quantité d'acide dépend notamment du
produit, de sa concentration, du TAC, de la régulation et des consignes du
fabricant. La quantité de désinfectant dépend aussi du produit, du CYA et du
mode de traitement. Une mesure ou une borne incomplète ne doit jamais être
transformée en dose par l'application.

## Créer une surveillance

Créer une nouvelle archive avec le pH réel, la cible et les bornes de chlore
libre indiquées par l'étiquette du désinfectant :

```bash
piscine-ph start --no-guided --force \
  --mode surveillance_ph_haut \
  --initial-ph 7.6 --target-ph 7.2 --initial-tac 70 \
  --chlorine-min 1 --chlorine-max 4 \
  --electrolysis arretee --ph-regulator arrete \
  --disinfection galets_stabilises --tablets consommes
```

Pour un chlore stabilisé (trichlore ou dichlore), l'application applique au
minimum un plancher de 2 ppm dans son diagnostic, même si une borne plus basse
a été saisie. Les bornes entrées restent une copie de l'étiquette : elles sont
à adapter au produit réellement utilisé. Pour une piscine utilisant du CYA, le
CDC indique au moins 2 ppm de chlore libre et un pH de 7,0 à 7,8 ; sans CYA, le
plancher indiqué est 1 ppm. La notice du fabricant et les règles locales
restent prioritaires. [CDC — traitement et tests d'une piscine privée](https://www.cdc.gov/healthy-swimming/about/home-pool-and-hot-tub-water-treatment-and-testing.html)

Le mode guidé permet de choisir ce même parcours. Il demande aussi l'état de
l'électrolyse, du régulateur de pH et, pour les galets stabilisés, leur état
observé : `en_place`, `consommes`, `suspendus` ou `non_necessaires`.

### Référence complète de la commande `start`

| Option | Valeur attendue | Défaut | Effet précis |
| --- | --- | --- | --- |
| `--no-guided` | drapeau, sans valeur | le questionnaire est actif | Désactive les questions interactives ; les valeurs fournies et les défauts sont employés directement. |
| `--force` | drapeau, sans valeur | désactivé | Crée une nouvelle archive même si une archive active existe ; l'ancienne n'est ni modifiée ni supprimée. |
| `--mode` | `surveillance_ph_haut` | `correction_hausse_ph_tac` | Sélectionne le parcours sans dosage. Il exige un `initial-ph` strictement supérieur à `target-ph`, désactive les commandes de soude/bicarbonate et propose `record-water`. |
| `--initial-ph` | nombre entre 0,01 et 13,99 | 4,0 | pH mesuré à la création de l'archive. En surveillance, il doit être supérieur à la cible. |
| `--target-ph` | nombre entre 0,01 et 13,99 | 7,2 | Cible pH de référence utilisée pour signaler un pH trop haut ; ce n'est pas une instruction de dosage. |
| `--initial-tac` | TAC positif, multiple du pas du test (10 ppm par défaut) | 30 ppm | TAC mesuré à la création. Il est comparé à la cible TAC archivée (80 ppm par défaut), sans planifier de bicarbonate dans ce parcours. |
| `--chlorine-min` | chlore libre positif ou nul, en ppm | 1 ppm | Borne basse lue sur l'étiquette. Avec dichlore ou trichlore stabilisé, le diagnostic retient au moins 2 ppm. |
| `--chlorine-max` | chlore libre positif, en ppm, supérieur ou égal au minimum | 4 ppm | Borne haute lue sur l'étiquette ; au-dessus, le programme indique de ne pas ajouter de chlore et de re-mesurer. |
| `--electrolysis` | `inconnu`, `en_marche`, `arretee` | `inconnu` | État déclaré de la cellule. `arretee` ajoute une alerte : le chlore ne doit pas être supposé remonter automatiquement. |
| `--ph-regulator` | `inconnu`, `en_marche`, `arrete` | `inconnu` | État déclaré du régulateur, sans le piloter. `arrete` indique qu'aucune correction automatique du pH n'est attendue. |
| `--disinfection` | `inconnu`, `electrolyse_au_sel`, `galets_stabilises`, `dichlore_stabilise`, `chlore_non_stabilise` | `inconnu` | Source active unique de désinfection. Les deux valeurs stabilisées appliquent le plancher de 2 ppm et affichent les limites liées au CYA. `--chlorine` reste accepté comme alias historique. |
| `--tablets` | `inconnu`, `en_place`, `consommes`, `suspendus`, `non_necessaires` | `inconnu` | État observé du doseur de galets. `consommes` est signalé lorsque le chlore est bas ; aucune recharge n'est calculée. |

`--volume-m3`, `--intermediate-ph`, `--bucket-l` et `--naoh-g-l` restent
visibles dans l'aide pour préserver le parcours historique de hausse pH/TAC,
mais ne sont pas utilisés pour calculer une dose dans
`surveillance_ph_haut`.

## Enregistrer une mesure

Après homogénéisation, mesurer dans le bassin puis consigner les trois valeurs :

```bash
piscine-ph record-water --ph 7.6 --tac 70 --free-chlorine 0.5
```

Le TAC doit respecter le pas de lecture choisi pour le test (10 ppm par défaut).
Le programme conserve chaque mesure dans le JSON, actualise le dernier pH/TAC
et affiche une alerte adaptée à la situation.

| Constat | Réponse affichée par le programme |
| --- | --- |
| pH au-dessus de la cible | Vérifier la mesure, la consigne et l'état du régulateur ; aucune dose d'acide n'est calculée. |
| pH au-dessus de 7,8 | Alerte : le pH sort de la plage usuelle 7,0–7,8 et le chlore devient moins efficace. |
| TAC différent de la cible archivée | Le constat est journalisé ; aucun bicarbonate n'est planifié dans ce parcours pH haut. |
| Chlore libre bas | Restaurer la désinfection seulement selon l'étiquette, puis re-mesurer. Un électrolyseur arrêté ou des galets consommés sont signalés. |
| Chlore libre haut | Ne pas ajouter de chlore ; suivre la notice avant la baignade et re-mesurer. L'application ne propose pas de neutralisant. |
| Mesure supérieure à 10 ppm | Vérifier le test : un DPD peut se décolorer et donner artificiellement une valeur basse ou zéro. |

Le programme ne déduit jamais le CYA du nombre de galets. L'enregistrer après
un test réel :

```bash
piscine-ph measure-cya --cya 55
```

À partir de 75 ppm de CYA, il alerte déjà de ne plus ajouter de chlore stabilisé
et d'évaluer un renouvellement partiel d'eau. Consultez aussi le
[guide sur le traitement stabilisé](traitement-chlore-stabilise.md).

## Mettre à jour l'état des appareils

La commande suivante documente un changement d'état sans faire fonctionner un
appareil :

```bash
piscine-ph treatment \
  --electrolysis arretee --disinfection galets_stabilises \
  --ph-regulator arrete --tablets consommes
```

Les options `--ph-regulator` et `--tablets` peuvent être omises pour conserver
leur dernière valeur. Les changements physiques (remettre l'électrolyse, régler
le régulateur ou recharger un doseur) doivent suivre les notices de leurs
fabricants. Ne jamais mélanger des produits chlorés, un acide ou un correcteur
de pH : les mélanges incompatibles peuvent dégager du chlore gazeux toxique.
[EPA — stockage et manipulation des produits de piscine](https://www.epa.gov/chemical-safety-and-pollution-prevention/chemical-safety-alert-safe-storage-and-handling-swimming-pool-chemicals)

Après une recharge réellement effectuée, `record-tablets` conserve aussi cet
événement et remet l'état des galets à `en_place` :

```bash
piscine-ph record-tablets --count 2 --unit-mass-g 200 --product "galets trichlore 200 g"
```
