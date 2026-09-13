# Choisir un protocole

Cette page aide à choisir un parcours dans le menu **Protocoles** de la TUI
ou avec `piscine-ph start`. Chaque parcours archive les mesures et les choix
qui lui appartiennent. Il ne remplace ni l'étiquette du produit, ni sa FDS, ni
une nouvelle mesure dans le bassin.

## Choix rapide

Avant tout nouveau parcours, déclarer la source de désinfection et l'état des
appareils. Les quatre paramètres doivent être renseignés ; « aucune » et
« non installé » décrivent une absence réelle, tandis que « non renseigné »
empêche le démarrage. Le contexte est conservé dans chaque archive et repris
dans les parcours enchaînés, avec son état actuel à vérifier.

| Si votre besoin principal est… | Ouvrir ce protocole | Ce que le programme fait | Ce qu'il ne fait pas |
| --- | --- | --- | --- |
| Consigner l'état de l'eau sans ajout | **Mesurer l'eau** | Archive pH, TAC et chlore libre ; affiche les constats liés aux cibles et aux seuils déclarés. | Ne calcule ni acide ni chlore. |
| Remonter ou abaisser un pH mesuré | **Corriger le pH** | Prépare des lots de soude ou d'acide selon le parcours et le produit déclaré ; demande une mesure après chaque lot. | Ne transforme pas le pH seul en quantité totale à verser. |
| Remonter un TAC trop bas | **Corriger le TAC** | Calcule un lot limité de bicarbonate depuis le TAC mesuré. | Ne propose pas de baisse du TAC et ne suppose pas que le pH restera inchangé. |
| Suivre le chlore, les appareils et le CYA | **Gérer la désinfection** | Archive le désinfectant, les équipements, les galets, le CYA et les seuils de chlore lus sur l'étiquette. | Ne pilote aucun appareil et ne calcule aucune dose de chlore. |

Les parcours sont reliés : une correction de pH ou de TAC peut modifier l'autre
valeur. Après tout lot, revenir à **Mesurer l'eau**, relever pH et TAC, puis
seulement décider d'un éventuel lot suivant.

Dans la TUI, l’**Assistant guidé** applique cet enchaînement par défaut à partir
de l’état archivé : il ne présente qu’une prochaine action compatible et ramène
à la mesure de confirmation après un lot. Le **Mode manuel** conserve l’accès
direct aux parcours, sans jamais contourner les validations métier.

## Les valeurs communes

| Valeur | Signification | Quand la saisir |
| --- | --- | --- |
| **pH** | Mesure de l'acidité ou de la basicité de l'eau. Ce n'est pas une échelle linéaire. | Au départ, puis après chaque lot pH ou TAC. |
| **TAC** (ppm équivalent CaCO3) | Capacité de l'eau à neutraliser un acide, donc son effet tampon. Ce n'est pas « la quantité de bicarbonate ». | Au départ, puis après chaque lot. Le programme respecte le pas du test, 10 ppm par défaut. |
| **Volume du bassin** (m³) | Volume d'eau concerné par un apport. | À l'ouverture d'une correction pH ou TAC ; une erreur fausse les masses ou volumes calculés. |
| **Cible pH / TAC** | Valeur opérationnelle voulue pour ce parcours, distincte de la mesure actuelle. | Avant de démarrer ; elle est archivée et ne doit pas être modifiée à la main dans le JSON. |
| **Chlore libre** (ppm) | Chlore actif mesuré avec le test adapté. | Dans les parcours de surveillance ou de désinfection. Les bornes sont celles de l'étiquette, pas une consigne universelle du programme. |
| **CYA** (ppm) | Acide cyanurique, ou stabilisant. | Avec galets ou dichlore stabilisés, lorsque la mesure est disponible. Il contextualise les alertes ; il n'est jamais déduit du nombre de galets. |

Pour les notions chimiques, consulter aussi le [guide de chimie](comprendre-la-chimie.md).

## 1. Mesurer l'eau

Utiliser ce parcours quand vous voulez suivre l'eau sans ajouter de produit :
contrôle après un événement, vérification lorsque les cibles sont atteintes, ou
relevé du chlore libre. Saisir le pH et le TAC actuels ; le chlore libre est
facultatif dans ce parcours. Le pH de référence et les bornes de chlore servent
uniquement aux constats affichés, jamais à déclencher une correction.

À chaque mesure, renseigner pH et TAC, puis le chlore libre lorsqu'il a été
mesuré. Le programme journalise la mesure et attire l'attention sur les écarts,
mais ne prépare aucun lot. Si une correction semble nécessaire, choisir ensuite
le parcours adapté à partir de la nouvelle mesure.

Dans l’Assistant guidé, cette décision est déterministe et ne constitue jamais
une dose :

- TAC sous la référence : proposer **Corriger le TAC** en premier, car le
  bicarbonate peut modifier le pH ; une nouvelle mesure décidera ensuite du pH.
- TAC non bas et pH sous/sur la référence : proposer **Corriger le pH** vers le
  haut/bas ; le produit reste à déclarer par l’utilisateur.
- pH/TAC conformes mais chlore libre hors des bornes déclarées : proposer
  **Gérer la désinfection**, sans calculer de recharge.
- pH et TAC conformes : conclure explicitement qu’aucune correction n’est
  proposée. Un TAC trop haut est aussi conservé sans baisse automatique.

Lorsqu’un parcours correctif est choisi, le relevé est fermé et devient le
parent de la nouvelle archive : les valeurs sont préremplies, puis à vérifier
avant sa création.

## 2. Corriger le pH

Choisir le produit réellement employé, puis le sous-parcours correspondant.

### Remonter le pH avec la soude (NaOH)

À utiliser seulement avec une solution de NaOH dont la concentration est lue
sur l'étiquette ou la FDS. Le programme demande : volume, pH et TAC mesurés,
un palier intermédiaire, une cible pH, le volume du seau et la concentration
de NaOH. Les pH doivent respecter `pH initial < palier < cible`.

Le palier intermédiaire existe pour mesurer le TAC avant sa correction. Une
dose de soude est préparée dans le seau, mais n'est comptée comme versée
qu'après la mesure pH/TAC de confirmation. Une concentration en `% m/m`
exige aussi la densité ; `% m/v` et `% m/m` ne sont pas interchangeables.

### Abaisser le pH avec l'acide sulfurique 15 %

À utiliser si le pH mesuré est strictement supérieur à la cible et si le
produit est bien l'acide sulfurique 15 % couvert par le parcours. Le lot est
issu du ratio archivé de la notice, plafonné à une baisse cible de 0,1 pH, puis
une mesure pH/TAC est obligatoire. Le programme refuse le lot si le régulateur
pH est en marche, ou si des galets au trichlore sont déclarés actifs.

Ne choisissez pas ce parcours pour déduire une quantité d'acide à partir d'un
produit, d'une concentration ou d'une notice différente.

### Étudier un pH+ au carbonate de sodium (Na2CO3)

Ce n'est pas encore un protocole de dosage. Il archive le libellé du produit,
sa pureté et sa source (étiquette ou FDS), puis montre le plafond théorique
lié au TAC et le pH théorique associé. Le résultat peut écarter le carbonate
si le pH ou le TAC est déjà à la cible. Même lorsqu'il est étudiable, aucun lot
n'est créé : le carbonate ne remplace pas automatiquement la soude et le
bicarbonate. Voir la [note carbonate](evolution-carbonate-sodium.md).

## 3. Corriger le TAC

Ce parcours ne traite que la **hausse** du TAC au bicarbonate de sodium
(`NaHCO3`). L'utiliser lorsque le TAC mesuré est strictement inférieur à la
cible, avec le volume du bassin, le pH de contexte, le TAC mesuré et le TAC
cible. Les deux TAC doivent être des multiples du pas du test (10 ppm par
défaut) : une valeur `52 ppm` ne donne pas une mesure plus précise qu'un test
lu par dizaines.

Le programme prépare un seul lot limité à la taille configurée (1 kg par
défaut), même si le besoin théorique est plus élevé. Après ajout et filtration,
mesurer pH et TAC, confirmer le lot, puis recalculer si le TAC reste trop bas.
Le bicarbonate peut modifier le pH : la nouvelle mesure, non le calcul
précédent, décide de la suite.

Un TAC trop haut ne doit pas être traité avec ce parcours. La baisse dépend du
produit et du bassin ; aucune dose n'est déduite automatiquement ici.

## 4. Gérer la désinfection

Utiliser ce parcours pour documenter et suivre le traitement, pas pour le
piloter. À l'ouverture, saisir pH, TAC et les bornes basse/haute de chlore
libre figurant sur l'étiquette du produit. Ensuite déclarer la source active
de désinfection, l'état de l'électrolyse, du doseur de galets et du régulateur
pH ; une seule source de désinfection est active à la fois.

Journaliser les galets réellement ajoutés et les mesures CYA disponibles. Lors
d'une mesure d'eau, le chlore libre est obligatoire dans ce parcours. Le
programme peut signaler un chlore hors des bornes, des galets consommés ou une
électrolyse arrêtée, mais il ne calcule pas de recharge automatique : la dose
dépend du produit, de son étiquette, du bassin et du contexte CYA.

## Séquence sûre après un ajout

```text
Mesurer pH / TAC / chlore si pertinent
        ↓
Ouvrir le parcours correspondant et préparer un seul lot, si le parcours le permet
        ↓
Ajouter suivant l'étiquette et la FDS ; filtration en marche
        ↓
Attendre le délai du produit ou du parcours
        ↓
Mesurer de nouveau pH et TAC, puis confirmer ou arrêter
```

Une archive terminée ou annulée reste disponible dans **Archives**. Pour
enchaîner un nouveau parcours, sélectionner cette archive puis **Enchaîner
depuis cette archive** : les dernières valeurs pH/TAC sont préremplies pour
être vérifiées, et la nouvelle archive conserve le lien vers son parent. En
CLI, employer `piscine-ph start --follow-up-from NOM_ARCHIVE`. Un parcours actif
est repris par défaut afin de ne pas perdre le lien entre une dose, sa mesure de
confirmation et les valeurs suivantes. Utiliser une nouvelle archive forcée
seulement lorsque vous voulez réellement séparer les suivis.
