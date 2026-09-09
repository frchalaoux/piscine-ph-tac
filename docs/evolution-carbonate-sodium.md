# Évolution envisagée — prise en charge du carbonate de sodium (pH+)

Cette note conserve les éléments nécessaires avant d'ajouter le carbonate de sodium au programme. Elle est informative : **le programme ne calcule actuellement que les apports de NaOH (soude) et de bicarbonate de sodium**.

## Décision à ne pas simplifier

Un pH+ en poudre est généralement du carbonate de sodium (`Na2CO3`) ; l'étiquette et la FDS du produit réellement acheté doivent toutefois le confirmer. Le carbonate augmente à la fois le pH et le TAC. Il peut donc réduire les besoins en soude et en bicarbonate lorsque les deux mesures sont basses, mais il ne les remplace pas selon une proportion fixe.

| Produit | Effet principal | Effet secondaire |
| --- | --- | --- |
| NaOH (lessive de soude) | Hausse du pH | Hausse du TAC selon le bilan du protocole |
| Bicarbonate de sodium (`NaHCO3`) | Hausse du TAC | Hausse limitée du pH |
| Carbonate de sodium (`Na2CO3`, pH+) | Hausse rapide du pH | Hausse du TAC |

Le bicarbonate reste préférable lorsque le but est d'augmenter le TAC en limitant l'effet sur le pH. À l'inverse, le carbonate risque de faire dépasser le pH visé si le TAC est déjà convenable. La réponse exacte dépend notamment du pH, du TAC, du CO2 dissous et de la dureté de l'eau : il est interdit de convertir une dose NaOH + bicarbonate en une dose de carbonate par simple règle de trois.

Une fiche de pH+ confirme que le carbonate de sodium augmente aussi le TAC ; un manuel de traitement explique que le bicarbonate a l'effet le plus faible sur le pH lors d'une correction du TAC. [Fiche pH+](https://marina-pool.com/wp-content/uploads/2024/02/MARINA_pH-PLUS_Poudre.pdf) · [manuel technique](https://www.clearwaterpoolsystems.com/wp-content/uploads/documents/mp-chemistry-manual.pdf)

## Comparaison de prix — repère France, relevé le 6 septembre 2026

Ces prix servent seulement à évaluer l'intérêt d'une future option. Ils incluent les conditionnements affichés, pas les frais de port, la disponibilité locale ni la conformité du produit au traitement d'une piscine.

| Produit repère | Prix affiché | Dosage indicatif pour +0,1 pH / 10 m³ | Coût indicatif |
| --- | ---: | ---:| ---: |
| pH+ poudre générique, 5 kg | 12,90 € (2,58 €/kg) | 75 à 100 g | 0,19 à 0,26 € |
| pH+ poudre premium, 5 kg | 29,90 € (5,98 €/kg) | 75 à 100 g | 0,45 à 0,60 € |
| Lessive de soude 30,5 %, 5 L | 18,50 € (3,70 €/L) | 0,10 L | 0,37 € |

Pour le bassin de 46 m³ configuré par défaut, cela représente approximativement 345 à 460 g de pH+ (0,89 à 2,75 € selon le produit) ou 460 mL de lessive de soude (1,70 €), **à résultat indicatif seulement**. Les notices de produits peuvent annoncer 75, 100 ou 200 g par 10 m³ selon leur formulation et leur incrément de pH ; les mesures de contrôle prévalent toujours.

Sources de prix et dosage : [pH+ Aquablue](https://www.castorama.fr/granules-ph-plus-pour-piscine-aquablue-5kg/9008748011228_CAFR.prd), [pH+ Bayrol](https://www.castorama.fr/ph-plus-bayrol-5kg/4008367948153_CAFR.prd), [lessive de soude 30,5 %](https://www.castorama.fr/lessive-de-soude-onyx-30-5-5-l/3183942660505_CAFR.prd), [guide comparant pH+ poudre et liquide](https://www.my-cfgroup.fr/storage/mediatheque/docutheque/guide/francais/CFGroup_GTE%20Piscines_Chemoform_FR_LD.pdf).

## Prérequis de sécurité et de produit

- Ne pas déduire la concentration d'une lessive de soude de son seul poids, ni la considérer adaptée à la piscine sans lire son étiquette et sa FDS.
- Ne pas substituer un produit ménager, du carbonate, du bicarbonate et de la soude sans déclarer le produit réellement employé.
- Continuer les ajouts par lots, filtration en marche, suivi d'une nouvelle mesure pH/TAC ; le carbonate exige la même prudence de manipulation et de protection oculaire que les autres correcteurs alcalins.
- Cette note ne modifie pas les précautions chimiques et les limites du protocole existant.

## Travail nécessaire avant implémentation

1. Ajouter un type de produit alcalin archivé (`NaOH`, `NaHCO3`, `Na2CO3`) avec sa concentration ou pureté issue de l'étiquette/FDS.
2. Définir et tester un calcul spécifique au carbonate à partir du modèle carbonate existant. Ne jamais additionner les recommandations NaOH et bicarbonate.
3. Créer un parcours CLI dédié : explication des unités, choix explicite du produit, avertissement de dépassement de pH et confirmation par mesures intermédiaires.
4. Adapter l'estimation d'approvisionnement, les journaux JSON et la documentation afin de distinguer un achat de carbonate d'une dose à verser.
5. Ajouter des tests de régression sur les cas « pH bas/TAC correct », « pH correct/TAC bas » et « pH bas/TAC bas » avant de présenter le carbonate comme une alternative.

Jusqu'à cette implémentation, conserver le protocole actuel : NaOH pour les étapes pH et bicarbonate pour la correction contrôlée du TAC.
