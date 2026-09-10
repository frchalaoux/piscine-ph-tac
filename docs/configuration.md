# Configuration versionnée

Les valeurs opérationnelles livrées avec l'application sont centralisées dans `src/piscine_ph/defaults.json`. Ce fichier est embarqué dans le paquet Python et validé au démarrage par les modèles Pydantic de `settings.py`.

Il est prévu pour modifier les réglages par défaut d'un nouveau protocole, pas les données d'un protocole déjà créé. Chaque archive JSON conserve sa propre copie de ces valeurs dans `config` : changer `defaults.json` ne réécrit donc jamais un historique existant.

| Clé JSON | Unité | Rôle |
| --- | --- | --- |
| `protocol.pool_volume_m3` | m3 | Volume proposé à la commande `start`. |
| `protocol.initial_ph` | pH | pH de départ proposé. |
| `protocol.intermediate_ph` | pH | Palier à atteindre avant la phase TAC. |
| `protocol.target_ph` | pH | Cible finale proposée. |
| `protocol.initial_tac_ppm` | ppm CaCO3 | TAC de départ proposé. |
| `protocol.target_tac_ppm` | ppm CaCO3 | TAC minimum à confirmer. |
| `protocol.tac_measurement_step_ppm` | ppm CaCO3 | Résolution du test TAC ; les valeurs saisies doivent être des multiples. |
| `protocol.bucket_volume_l` | L | Taille nominale du seau. |
| `protocol.naoh_concentration_g_l` | g/L | Concentration de la soude utilisée pour les conversions. |

Les bornes de chlore libre ne sont pas des valeurs globales dans
`defaults.json` : elles sont saisies à la création d'une archive de
`surveillance_ph_haut`, car elles doivent venir de l'étiquette du désinfectant
réel. Elles sont archivées dans `config.free_chlorine_min_ppm` et
`config.free_chlorine_max_ppm`.
| `workflow.naoh_large_gap_ph` | unité pH | Seuil entre la portion moyenne et la grande portion. |
| `workflow.naoh_medium_gap_ph` | unité pH | Seuil entre la petite et la moyenne portion. |
| `workflow.naoh_large_dose_ml` | mL | Repère de dose au-delà du seuil `naoh_large_gap_ph`. |
| `workflow.naoh_medium_dose_ml` | mL | Repère de dose entre les deux seuils d'écart pH. |
| `workflow.naoh_small_dose_ml` | mL | Repère de dose au plus au seuil `naoh_medium_gap_ph`. |
| `workflow.bicarbonate_batch_max_kg` | kg | Masse maximale d'un seul lot de bicarbonate, à confirmer par mesure avant le lot suivant. |
| `workflow.bicarbonate_wait_min_minutes` | min | Durée minimale de filtration avant la mesure pH/TAC après un lot de bicarbonate. |
| `supply_planning.naoh_purchase_recommended_l` | L | Stock prudent de soude proposé dans le plan d'approvisionnement ; ce n'est pas une dose. |
| `supply_planning.bicarbonate_purchase_margin_kg` | kg | Marge ajoutée au besoin théorique de bicarbonate. |
| `supply_planning.stabilized_chlorine_extra_bicarbonate_margin_kg` | kg | Marge supplémentaire si les galets stabilisés sont déclarés. |

Les suggestions NaOH restent indicatives : elles ne sont pas un calcul de la quantité nécessaire. Une modification de ce fichier doit être revue, testée avec `uv run pytest`, puis appliquée seulement à un nouveau protocole.

Au démarrage guidé, l'utilisateur confirme la concentration du produit réellement employé ; cette valeur prioritaire est archivée dans `config`, avec son origine (`g_par_litre`, `pourcentage_massique` ou `pourcentage_volumique`). Le questionnaire convertit `% m/m` avec la densité déclarée et `% m/v` directement. Ne pas déduire cette concentration du poids brut d'un bidon.

Les masses molaires, constantes carbonate, tolérances de cohérence et limites de sécurité du seau ne sont volontairement pas dans ce JSON. Elles sont documentées dans `src/piscine_ph/chemistry.py`, car les modifier sans révision scientifique changerait le modèle ou les protections du programme.

La [référence des fichiers JSON](fichiers-json.md) décrit le format de `defaults.json` et celui des archives enregistrées dans `data/protocoles/`.
