# Comprendre vite la chimie pH / TAC d’une piscine

Ce guide donne les repères nécessaires pour utiliser `piscine-ph` sans avoir étudié la chimie de l’eau. Il explique les grandeurs manipulées par le programme ; il ne remplace ni l’étiquette ni la fiche de données de sécurité (FDS) des produits réellement utilisés.

> Une mesure du bassin prime toujours sur un calcul. Ne jamais verser automatiquement une quantité parce qu’elle est affichée par un programme.

## L’idée essentielle

Le **pH** et le **TAC** répondent à deux questions différentes :

| Grandeur | Question simple | Image mentale |
| --- | --- | --- |
| pH | L’eau est-elle acide ou basique maintenant ? | La position instantanée d’un curseur. |
| TAC | Dans quelle mesure l’eau résiste-t-elle à une baisse de pH ? | La réserve qui amortit le mouvement du curseur. |

Un pH inférieur à 7 est acide, supérieur à 7 basique. Le pH est logarithmique : une variation d’une unité correspond à un facteur dix sur l’activité des ions hydrogène ; ce n’est donc pas une échelle linéaire. L’alcalinité est une **capacité de neutralisation d’acide**, surtout liée dans l’eau courante aux bicarbonates, carbonates et hydroxydes — ce n’est pas « la quantité de bicarbonate » à elle seule. [USGS — pH et alcalinité](https://www.usgs.gov/water-science-school/science/alkalinity-and-water)

Ainsi, un pH qui monte ne signifie pas automatiquement que le TAC monte, et l’inverse est également faux. Cela dépend de ce qui a été ajouté ou échangé avec l’air.

## Les espèces qui relient pH et TAC

Le carbone dissous existe principalement sous plusieurs formes qui se transforment l’une dans l’autre :

```text
CO2 dissous + H2O  <->  H2CO3  <->  H+ + HCO3-  <->  2 H+ + CO3--
                                      bicarbonate       carbonate
```

- Davantage de **CO2 dissous** favorise l’acidité et tend à abaisser le pH.
- Le **bicarbonate** `HCO3-` est la forme la plus importante pour le tamponnement dans la zone de pH habituelle d’une piscine.
- Le **carbonate** `CO3--` devient plus important à pH plus élevé.

Le TAC est mesuré par titrage acide : on ajoute un acide à un échantillon jusqu’à épuiser cette capacité de neutralisation. C’est pourquoi il est souvent exprimé en **ppm équivalent CaCO3**, même si l’eau ne contient pas littéralement cette masse de carbonate de calcium. [USGS — définition et mesure de l’alcalinité](https://water.usgs.gov/nwc/NWC/water_quality/tables/quality.abs.html)

## Ce que font les deux produits du protocole

### Soude : hydroxyde de sodium, NaOH

Dans l’eau, la soude apporte essentiellement des ions hydroxydes `OH-` : c’est une base forte. Elle fait donc monter le pH. Chaque mole de NaOH apporte aussi un équivalent d’alcalinité, donc elle augmente théoriquement le TAC.

Pour le bassin de 46 m3 et une solution annoncée à 300 g/L, 250 mL correspondent à environ 1,875 mol de NaOH. Le bilan théorique de TAC est seulement d’environ +2 ppm CaCO3. Cela **ne permet pas** de prédire de façon fiable le saut de pH réel : le CO2, les autres produits, l’homogénéisation et l’état réel de l’eau comptent beaucoup.

La dissolution ou dilution de NaOH dégage de la chaleur, et la soude est corrosive. Utiliser les protections et la méthode indiquées par la FDS du produit ; ne pas mélanger des produits de piscine entre eux. [PubChem — dangers du NaOH](https://pubchem.ncbi.nlm.nih.gov/compound/Sodium-hydroxide), [CDC — sécurité des produits de piscine](https://www.cdc.gov/healthy-swimming/toolkit/pool-chemical-safety.html)

### Bicarbonate de sodium : NaHCO3

Le bicarbonate apporte principalement des ions `HCO3-`. Il est donc utilisé pour relever le TAC. Il peut aussi faire monter le pH, surtout lorsque celui-ci est très bas, mais son rôle principal dans ce protocole reste la reconstitution du tampon.

Le programme le propose après le palier pH 6 : avec une eau moins fortement acide, la mesure de TAC et l’effet du bicarbonate sont plus interprétables. L’ajout est fractionné, puis contrôlé par une nouvelle mesure ; le bicarbonate n’est pas une « dose unique garantie ».

## Pourquoi l’ordre du protocole est important

```text
pH très bas
   |
   |  petites doses de NaOH, mélange, attente, mesures
   v
palier pH 6
   |
   |  mesure TAC, bicarbonate fractionné, nouvelles mesures
   v
TAC confirmé à la cible
   |
   |  petites doses finales de NaOH et mesures
   v
pH final
```

1. À pH très bas, on évite de chercher une grosse correction calculée d’un coup : la réponse observée est plus fiable qu’une extrapolation.
2. Le TAC est ensuite relevé et **mesuré**. Un TAC plus élevé amortit les variations de pH, mais ne fixe pas un pH magique.
3. Le pH final est ajusté progressivement, car le bicarbonate et les échanges de CO2 peuvent avoir modifié la réponse de l’eau.

Le test TAC du protocole se lit par pas de 10 ppm : saisir 50, 60, 70 ou 80 ppm, pas 52 ppm. Une valeur théorique avec décimales sert au bilan, pas à inventer une précision de mesure.

## Pourquoi le pH peut encore évoluer après un ajout

Après avoir ajouté un produit, l’eau peut continuer à évoluer même sans nouveau produit :

- le mélange n’est pas encore homogène ;
- le CO2 peut être échangé avec l’air, particulièrement avec brassage, buses et agitation ;
- d’autres produits présents dans l’eau peuvent contribuer à l’acidité ou à l’alcalinité ;
- l’eau de remplissage, les baigneurs et certains traitements peuvent modifier l’équilibre.

Dans un système carbonate idéal fermé, l’échange de CO2 change surtout la répartition des formes carbonées et le pH ; il ne crée pas à lui seul l’alcalinité apportée par NaOH ou bicarbonate. En pratique, il faut donc attendre l’homogénéisation et re-mesurer plutôt que déduire le résultat depuis le pH du seau. Les méthodes USGS rappellent que la spéciation carbonate dépend du pH et que d’autres espèces acido-basiques peuvent aussi contribuer au titrage. [USGS — limites des calculs de spéciation](https://water.usgs.gov/water-resources/memos/memo.php?id=2098)

## Comment lire les contrôles affichés par l’application

Après une mesure, l’application calcule un bilan de matière :

- `TAC théorique` : ce que l’ajout seul apporterait dans le volume déclaré ;
- `Cumul versé` : les quantités d’ajouts confirmés par une mesure, pas les préparations annulées ;
- `Alerte` : la mesure et le modèle carbonate ne concordent pas suffisamment.

Le modèle suppose une eau homogène, à 25 °C, dominée par le système carbonate et sans apport ni perte significatifs pendant l’étape. Ce sont des hypothèses utiles pour détecter une valeur surprenante, pas une description complète d’une piscine réelle.

Si le programme indique **« Prédiction de pH indisponible »**, il a détecté que le couple pH/TAC implique une quantité de carbone dissous incohérente avec ce modèle fermé. Le bon réflexe est de vérifier les mesures et de continuer seulement par petites étapes réellement mesurées ; il ne faut pas forcer une correction pour atteindre le pH théorique absent.

## Les bons réflexes

- Mesurer dans le bassin homogénéisé, jamais dans le seau de préparation.
- Noter uniquement ce qui a vraiment été versé ; annuler une dose préparée mais non versée.
- Vérifier le volume réel du bassin et la concentration inscrite sur l’étiquette du produit.
- Respecter la FDS, les équipements de protection et les consignes de dilution du fabricant.
- Ne pas mélanger les produits de piscine, ni ajouter simultanément un acide et de la soude.
- En cas de mesure très inhabituelle, d’erreur de produit, de contact ou de projection, arrêter l’opération et suivre immédiatement la FDS et les consignes d’urgence du produit.

## Pour aller plus loin

- [Guide utilisateur](guide-utilisateur.md) : commandes et déroulement pratique.
- [Documentation du protocole](protocole_ph_tac.md) : formules, calculs et limites du programme.
- [Guide développeur](guide-developpeur.md) : architecture et maintenance.

### Sources pédagogiques

- [USGS — Alkalinity and Water](https://www.usgs.gov/water-science-school/science/alkalinity-and-water)
- [USGS — alcalinité, bicarbonate et carbonate](https://water.usgs.gov/nawqa/pnsp/pubs/ofr94-455/sw-t.html)
- [USGS — méthodes de calcul de l’alcalinité](https://or.water.usgs.gov/alk/methods.html)
- [CDC — sécurité des produits de piscine](https://www.cdc.gov/healthy-swimming/toolkit/pool-chemical-safety.html)
- [PubChem — hydroxyde de sodium](https://pubchem.ncbi.nlm.nih.gov/compound/Sodium-hydroxide)
