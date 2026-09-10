# Produits déclarés et limites de sécurité

Cette page distingue les informations lues dans les fiches de données de
sécurité (FDS) fournies pour le bassin des règles de l'application. Une FDS
décrit les dangers, la manipulation, le stockage et l'élimination ; elle ne
remplace pas l'étiquette d'emploi et ne donne pas à l'application le droit de
calculer une dose.

## Informations provenant des FDS fournies

### Correcteur pH-

La FDS `IRRIPOOL PH- LIQUIDE 15 % – GCIJML15` identifie un correcteur de pH à
base d'acide sulfurique, à moins de 15 %. Elle indique notamment l'irritation
de la peau et des yeux, le port de gants et d'une protection oculaire/du
visage, l'évitement des projections et des brouillards, ainsi qu'un stockage
fermé, étiqueté, frais, sec et ventilé.

### Galets au trichlore

Les FDS `GCCHL4EC – Chlore lent multifonctions Eco` et `GCCHLLEC – Chlore
lent Eco` déclarent toutes deux du trichlore (acide trichloroisocyanurique),
avec 72 % de chlore actif minimum. Elles signalent que le produit apporte du
chlore et du CYA après dissolution.

Elles imposent de ne pas le combiner avec d'autres produits, spécialement les
acides : une réaction peut dégager du chlore et d'autres gaz dangereux. Les
galets doivent également être tenus à l'écart de la chaleur, des matières
combustibles et de l'humidité, dans leur contenant fermé et adapté.

## Règles appliquées par `piscine-ph`

- Les profils `GCCHL4EC` et `GCCHLLEC` sont distincts dans le contexte de
  traitement ; le JSON conserve celui qui est déclaré.
- Le programme affiche l'incompatibilité avec l'acide sulfurique pour ces deux
  profils et l'inscrit dans le journal lors d'un ajout de galets.
- Il ne calcule ni quantité d'acide sulfurique ni nombre de galets. Ces deux
  valeurs dépendent de la notice du fabricant, de l'installation et des
  mesures réelles.
- Le parcours désinfectant demande une mesure de chlore libre. Il journalise
  les galets et le CYA mesuré, sans déduire artificiellement le CYA des galets.

## Ce qui reste à fournir pour un calcul de produit

Une étiquette ou notice d'emploi du produit précis, avec son dosage et les
conditions d'application, est indispensable. Même avec cette notice,
l'application conservera des apports fractionnés et une re-mesure entre les
ajouts ; elle ne doit jamais proposer de mélange ou d'ajout simultané d'acide
et de galets au trichlore.
