# Traitement temporaire : électrolyse arrêtée et galets stabilisés

Ce guide couvre le cas d'une piscine normalement désinfectée par électrolyse au sel, dont la cellule est arrêtée pour maintenance, avec une désinfection temporaire par galets de chlore stabilisé. Il complète le protocole pH/TAC ; il ne remplace ni l'étiquette ni la fiche de données de sécurité des produits.

## Ce qui change réellement dans l'eau

Le sel déjà dissous reste dans le bassin. À la concentration habituelle d'une piscine au sel, il ne modifie pas de manière utile le calcul de quantité de NaOH ou de bicarbonate du programme.

En revanche, l'arrêt de la cellule supprime la cause courante de hausse progressive du pH liée à l'électrolyse. Les galets de trichlore, forme courante des galets stabilisés, ont au contraire une action acidifiante et peuvent diminuer pH et TAC. La tendance habituelle peut donc s'inverser : ne pas reconduire automatiquement les apports de pH+ prévus lorsque l'électrolyse fonctionnait.

Chaque galet stabilisé apporte aussi du stabilisant, appelé acide cyanurique ou CYA. Le CYA protège le chlore des UV, mais il s'accumule et ralentit l'action désinfectante du chlore. Il ne s'évapore pas avec l'eau : lorsqu'il devient trop élevé, la méthode pratique de réduction est le renouvellement partiel d'eau. L'Anses décrit le rôle protecteur du cyanurate dans les produits chlorés stabilisés ; le CDC rappelle que l'action désinfectante est ralentie en sa présence. [Anses](https://www.anses.fr/system/files/EAUX2007sa0409Ra.pdf) · [CDC](https://www.cdc.gov/healthy-swimming/about/home-pool-and-hot-tub-water-treatment-and-testing.html)

## Ce que le programme calcule encore correctement

Les bilans de quantité confirmés restent inchangés :

- une mole de NaOH ajoutée apporte théoriquement un équivalent de TAC ;
- une mole de bicarbonate de sodium apporte théoriquement un équivalent de TAC ;
- la masse de bicarbonate calculée pour augmenter un TAC mesuré reste un repère valide.

Le programme ne calcule volontairement pas le CYA à partir du nombre de galets. La composition, la masse, la vitesse de dissolution, les apports d'eau neuve et les pertes d'eau diffèrent d'un bassin à l'autre : seule une mesure CYA est retenue comme donnée opérationnelle.

La prévision de pH du contrôle de cohérence devient en revanche **indicative**. Elle repose sur un modèle carbonate fermé, alors qu'un galet apporte de l'acidité et du cyanurate pendant la période de mesure. Un écart entre pH prédit et pH mesuré ne prouve donc pas, à lui seul, une erreur de mesure ou de calcul. Le TAC mesuré dans le bassin reste la référence.

## Déclarer et journaliser cette situation

Au début de la période temporaire, déclarer le contexte :

```bash
uv run piscine-ph treatment --electrolysis arretee --chlorine galets_stabilises
```

Le programme affiche alors, après les contrôles pH/TAC, un avertissement indiquant que la prévision de pH est indicative. Le contexte est conservé dans l'archive JSON, y compris si le protocole est repris plus tard.

Journaliser chaque recharge de doseur :

```bash
uv run piscine-ph record-tablets --count 2 --unit-mass-g 200 --product "galets trichlore 200 g"
```

Cette commande est un journal, non une estimation de CYA. Elle exige que le contexte `galets_stabilises` ait d'abord été déclaré.

Après un test de stabilisant, enregistrer la valeur réellement lue :

```bash
uv run piscine-ph measure-cya --cya 35
```

La commande `status` affiche le traitement déclaré, le nombre de galets journalisés et la dernière mesure CYA. À partir de 50 ppm, elle affiche une vigilance ; à partir de 75 ppm, elle alerte de ne plus ajouter de chlore stabilisé et d'évaluer un renouvellement partiel d'eau. Ces seuils sont des garde-fous de suivi pour une piscine privée : les limites réglementaires citées par l'Anses s'appliquent aux piscines collectives et ne remplacent pas la notice du fabricant. [Anses](https://www.anses.fr/fr/system/files/EAUX2018SA0034Ra.pdf)

## Routine pendant ces deux mois

Avant chaque correction pH/TAC, mesurer pH et TAC. Contrôler aussi le chlore libre plusieurs fois par semaine — et après forte fréquentation, chaleur ou orage — ainsi que le CYA au moins toutes les une à deux semaines pendant l'emploi de galets. Pour une piscine privée utilisant un chlore stabilisé, le CDC conseille un pH entre 7,0 et 7,8 et au moins 2 mg/L de chlore libre ; la notice du produit et les caractéristiques du bassin restent prioritaires. [CDC](https://www.cdc.gov/healthy-swimming/about/home-pool-and-hot-tub-water-treatment-and-testing.html)

Pendant une correction du pH ou du TAC :

1. Si possible, ne rechargez pas le doseur de galets juste avant la période de circulation et de mesure qui suit la correction.
2. Faites des apports pH+ plus prudents qu'en période d'électrolyse active, puis mesurez après homogénéisation complète.
3. Ne déduisez jamais le CYA du seul nombre de galets : mesurez-le.
4. Évitez un chlore choc stabilisé (dichlore) tant que le CYA augmente. Le mot « choc » décrit une action rapide, pas l'absence de stabilisant : vérifier toujours la matière active sur l'étiquette.

Un produit à base de dichloroisocyanurate ou de trichloroisocyanurate est stabilisé. Un produit à base d'hypochlorite de calcium ou d'hypochlorite de sodium est non stabilisé, mais il a ses propres effets sur le pH, le calcium et les consignes d'emploi. Ne mélanger aucun de ces produits entre eux, ni avec un correcteur de pH, dans un doseur, un seau ou à sec.

## Retour à l'électrolyse

Quand la cellule est réparée : arrêter les galets stabilisés, contrôler pH, TAC, chlore libre et CYA, puis enregistrer le nouveau contexte :

```bash
uv run piscine-ph treatment --electrolysis en_marche --chlorine chlore_non_stabilise
```

Le champ `chlore_non_stabilise` décrit ici le chlore produit par l'électrolyse : il n'ajoute pas de CYA. La tendance à la hausse du pH peut alors reprendre ; reprendre les corrections progressivement, à partir des nouvelles mesures plutôt que de l'ancien rythme.
