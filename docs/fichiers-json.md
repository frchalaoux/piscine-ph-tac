# Référence des fichiers JSON

L’application emploie deux familles de fichiers JSON : un fichier de **paramètres versionnés** livré avec le code et une archive JSON par **protocole de correction**. Cette page décrit leur rôle, leurs champs et les règles de lecture. Elle est utile pour consulter un historique ou pour développer l’application ; l’utilisation courante passe par les commandes `piscine-ph`, sans modification manuelle des archives.

## Emplacements et cycle de vie

| Famille | Emplacement | Rôle | Versionné avec Git |
| --- | --- | --- | --- |
| Paramètres par défaut | `src/piscine_ph/defaults.json` | Valeurs proposées pour les nouveaux protocoles. | Oui |
| Archives de protocole | `data/protocoles/protocole_YYYYMMDD_HHMMSS.json` | Mesures, doses, contexte de traitement et journal d’un bassin. | Non |
| Ancien suivi éventuel | `suivi_protocole_naoh_tac.json` | Ancien format lu une fois et migré. | Non |

Une archive est écrite de façon atomique : l’application écrit d’abord un fichier temporaire puis le remplace. Une archive JSON invalide est ignorée lors de la recherche du protocole actif ; elle n’est pas supprimée automatiquement.

Le protocole actif est l’archive valide la plus récente, selon son nom, dont `step` n’est ni `termine` ni `annule`. La commande `piscine-ph history` liste les archives lisibles ; `piscine-ph status` affiche l’archive active.

## `defaults.json` : paramètres des nouveaux protocoles

Ce fichier est validé au démarrage. Modifier une valeur n’affecte jamais les archives existantes : chaque archive conserve une copie complète de ses paramètres dans `config`.

```json
{
  "schema_version": 1,
  "protocol": { "pool_volume_m3": 46.0 },
  "workflow": { "naoh_large_dose_ml": 250.0 },
  "supply_planning": { "naoh_purchase_recommended_l": 2.0 }
}
```

| Chemin | Unité | Usage |
| --- | ---: | --- |
| `schema_version` | — | Version du format des paramètres. Ne pas modifier sans migration du code. |
| `protocol.pool_volume_m3` | m³ | Volume proposé au démarrage. |
| `protocol.initial_ph`, `intermediate_ph`, `target_ph` | pH | Mesure de départ et paliers du workflow. Ils doivent respecter `initial < intermediate < target`. |
| `protocol.initial_tac_ppm`, `target_tac_ppm` | ppm CaCO3 | TAC proposé au départ et objectif. |
| `protocol.tac_measurement_step_ppm` | ppm CaCO3 | Résolution du test ; les valeurs saisies doivent être des multiples de ce pas. |
| `protocol.bucket_volume_l` | L | Volume nominal du seau. |
| `protocol.naoh_concentration_g_l` | g/L | Concentration de la soude utilisée dans les bilans. |
| `workflow.naoh_*` | pH ou mL | Seuils et portions indicatives de soude. Ils ne prédisent pas la demande réelle du bassin. |
| `workflow.bicarbonate_batch_max_kg` | kg | Taille maximale d’un seul lot de bicarbonate proposé. |
| `workflow.bicarbonate_wait_min_minutes` | min | Attente minimale de filtration avant sa mesure de confirmation. |
| `supply_planning.naoh_purchase_recommended_l` | L | Stock prudent de soude à acheter, non assimilable à une dose. |
| `supply_planning.bicarbonate_purchase_margin_kg` | kg | Marge ajoutée au besoin théorique en bicarbonate. |
| `supply_planning.stabilized_chlorine_extra_bicarbonate_margin_kg` | kg | Marge supplémentaire lorsque les galets stabilisés sont déclarés. |

La [documentation de configuration](configuration.md) explique aussi quand modifier ce fichier.

## Archive de protocole

Chaque fichier `protocole_*.json` représente un seul protocole. Les dates sont des chaînes ISO 8601. Les unités ne sont pas encodées dans les nombres : elles sont définies par le nom du champ (`_m3`, `_ppm`, `_ml`, `_kg`, etc.).

### En-tête, contexte et état

| Champ | Type | Signification |
| --- | --- | --- |
| `version` | entier | Version du schéma d’archive. Les nouvelles archives emploient actuellement la version 3 ; une archive plus ancienne reste lisible lorsque ses champs absents ont une valeur par défaut. |
| `protocol_id` | texte | Identifiant de création. Les archives migrées commencent par `legacy:`. |
| `created_at`, `updated_at` | date ISO 8601 | Création et dernière mutation du protocole. |
| `archive_name` | texte | Nom de ce fichier dans `data/protocoles`. |
| `config` | objet | Photographie des paramètres de bassin et de soude utilisés pour les calculs. |
| `step` | énumération | Étape courante : `naoh_vers_palier`, `tac_vers_80`, `naoh_final`, `surveillance_ph_haut`, `termine` ou `annule`. |
| `current_ph`, `current_tac_ppm` | nombre | Dernières mesures confirmées utilisées par le workflow. |
| `initial_coherence` | objet ou `null` | Contrôle du modèle carbonate sur les valeurs de départ. |

`config` contient les mêmes champs que `defaults.json.protocol`. Ne modifiez pas directement le JSON : changer le volume ou l’objectif compromettrait la traçabilité des doses. La seule correction prévue par l'application est `configure-naoh`, qui met à jour de manière journalisée la concentration d'un même produit et recalcule le cumul des apports NaOH déjà confirmés.

Pour les archives créées avec le questionnaire, `config` contient aussi `naoh_concentration_source`, `naoh_label_percent` et, pour un pourcentage massique, `naoh_density_g_ml`. Ces éléments documentent comment `naoh_concentration_g_l` a été obtenu ; ils sont particulièrement importants car `% m/m` et `% m/v` ne donnent pas la même concentration en g/L.

### Contexte de désinfection

```json
"treatment": {
  "electrolysis_status": "arretee",
  "chlorine_treatment": "galets_stabilises"
}
```

| Champ | Valeurs possibles | Effet |
| --- | --- | --- |
| `treatment.electrolysis_status` | `inconnu`, `en_marche`, `arretee` | Contextualise les alertes sur la tendance du pH. |
| `treatment.chlorine_treatment` | `inconnu`, `galets_stabilises`, `dichlore_stabilise`, `chlore_non_stabilise` | Active les avertissements sur le CYA et la prédiction de pH. |
| `stabilized_tablets` | liste | Ajouts de galets déclarés : `count`, `unit_mass_g` éventuel, `product_label`, `recorded_at`. Le nombre de galets ne sert pas à calculer le CYA. |
| `cyanuric_acid_measurements` | liste | Mesures CYA réelles : `cya_ppm` et `recorded_at`. |
| `water_measurements` | liste | Mesures sans ajout de produit du parcours `surveillance_ph_haut` : `ph`, `tac_ppm`, `free_chlorine_ppm`, date. |

Dans une archive de surveillance, `config.mode` vaut `surveillance_ph_haut` et
les bornes lues sur l'étiquette du désinfectant sont archivées sous
`free_chlorine_min_ppm` et `free_chlorine_max_ppm`. Cette archive ne contient
pas de plan d'approvisionnement et les commandes de dose NaOH/bicarbonate sont
inactives.

### Plan d’approvisionnement

`supply_estimate` est créé au démarrage ou automatiquement au prochain accès à une archive ancienne qui ne le contient pas. Il sert à préparer les achats ; aucun de ses nombres ne constitue une dose à verser.

```json
"supply_estimate": {
  "naoh_solution_recommended_l": 2.0,
  "bicarbonate_theoretical_kg": 3.8609831544871414,
  "bicarbonate_recommended_kg": 6.0,
  "basis_tac_ppm": 30.0,
  "includes_stabilized_chlorine_margin": true
}
```

| Champ | Signification |
| --- | --- |
| `naoh_solution_recommended_l` | Stock prudent de soude 300 g/L. Il est volontairement non prédictif, car le pH seul ne détermine pas la demande acide réelle. |
| `bicarbonate_theoretical_kg` | Masse théorique pour passer du TAC de départ au TAC cible, avant marge. |
| `bicarbonate_recommended_kg` | Quantité arrondie à acheter après les marges de `supply_planning`. |
| `basis_tac_ppm` | TAC initial utilisé par ce calcul. |
| `includes_stabilized_chlorine_margin` | `true` lorsqu’une marge supplémentaire pour galets stabilisés est comprise. |

### Doses préparées et doses confirmées

Les champs `pending_*` sont essentiels : une dose seulement préparée n’est pas considérée comme versée.

| Champ | Présence | Contenu |
| --- | --- | --- |
| `pending_naoh` | objet ou `null` | Soude préparée, en attente de `measure`. Champs : `phase`, pH/TAC avant, `naoh_ml`, `water_l`, date. |
| `pending_bicarbonate` | objet ou `null` | Un seul lot de bicarbonate planifié, en attente de `measure-tac`. Champs : pH/TAC avant, `bicarbonate_kg` (lot), `bicarbonate_total_kg` (besoin calculé avant fractionnement), date. |
| `naoh_doses` | liste | Doses de soude confirmées par une mesure après ajout. Chaque entrée ajoute `ph_after`, `tac_after_ppm`, `coherence`, `recorded_at`. |
| `bicarbonate_doses` | liste | Apports de bicarbonate confirmés, avec les mêmes mesures après ajout. |

Une dose en attente est supprimée par `cancel-dose` (soude) ou `cancel-tac-plan` (bicarbonate) uniquement si elle n’a pas été versée. Dès que `measure` ou `measure-tac` est exécuté, l’entrée est déplacée dans la liste correspondante et contribue au cumul. Après chaque lot de bicarbonate, une nouvelle mesure et un nouveau `plan-tac` sont nécessaires avant de préparer le lot suivant.

### Contrôle de cohérence

Chaque entrée `coherence` — et éventuellement `initial_coherence` — contient :

| Champ | Signification |
| --- | --- |
| `expected_ph`, `expected_tac_ppm` | Valeurs issues du modèle carbonate et du bilan de produits. `expected_ph` peut être `null` lorsque le modèle n’est pas exploitable. |
| `ph_difference`, `tac_difference_ppm` | Mesure moins prévision. `ph_difference` peut être `null`. |
| `inferred_carbon_mol_l` | Carbone dissous inféré par le modèle ; donnée de diagnostic, pas une mesure de laboratoire. |
| `is_consistent` | Résultat des seuils de cohérence du modèle. |
| `warnings` | Avertissements chimiques, de mesure ou liés au traitement déclaré. |

Le contrôle ne remplace pas une mesure et ne bloque pas automatiquement le protocole. Avec du chlore stabilisé, la prévision de pH est explicitement indicative.

### Cumul et journal

`cumulative_additions` est recalculé depuis les listes de doses confirmées. Il contient les volumes, masses, moles et contributions théoriques au TAC de la soude et du bicarbonate. Ne pas le modifier à la main : une correction de mesure via la CLI le recalcule sans compter deux fois un produit.

`journal` est la chronologie lisible du protocole. Chaque élément comporte `event` et `created_at`. Il garde notamment les préparations, mesures confirmées, changements de traitement et enregistrements de CYA.

## Exemple minimal de lecture

Dans une archive, rechercher d’abord ces clés :

```text
step                 → où en est le protocole
pending_naoh         → une soude est-elle seulement préparée ?
naoh_doses           → quelles doses ont été confirmées ?
cumulative_additions → combien a réellement été comptabilisé ?
treatment            → quel traitement est déclaré ?
supply_estimate      → quel stock était conseillé à l’achat ?
```

Par exemple, `pending_naoh.naoh_ml: 250` signifie « 250 mL préparés, pas encore confirmés ». À l’inverse, un élément dans `naoh_doses` avec `naoh_ml: 250`, `ph_after` et `tac_after_ppm` signifie que ces 250 mL sont enregistrés comme ajoutés.

## Modification, sauvegarde et migration

Ne modifiez pas une archive active à la main pendant qu’une commande est en cours. Pour rectifier une mesure après ajout, utiliser `correct-last-measurement`; pour annuler une préparation non versée, utiliser `cancel-dose`; pour arrêter un protocole, utiliser `cancel-protocol`.

Une archive ancienne sans `treatment`, `supply_estimate`, `stabilized_tablets` ou `cyanuric_acid_measurements` reste valide : les valeurs par défaut sont appliquées à la lecture. Lors du prochain accès au protocole actif, `supply_estimate` est généré puis sauvegardé.

L’ancien fichier `suivi_protocole_naoh_tac.json`, s’il existe, est importé une seule fois dans `data/protocoles/` sans suppression du fichier original. Une archive illisible doit être copiée avant toute réparation manuelle ; l’application l’ignore et tente de poursuivre avec une archive valide plus ancienne.
