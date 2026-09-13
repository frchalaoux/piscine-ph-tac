# Rechercher et lire une FDS manuellement

Une fiche de données de sécurité (FDS) sert à identifier les dangers, les
protections, la manipulation, le stockage, les incompatibilités et la conduite
à tenir en cas d’incident. Elle complète l’étiquette ; elle ne remplace ni les
instructions d’emploi du produit, ni les mesures de l’eau, ni l’avis d’un
professionnel en cas de doute.

`piscine-ph` ne télécharge, ne recherche, ne lit ni n’interprète de FDS
automatiquement. En particulier, il n’utilise pas d’IA pour cette tâche. La
personne qui emploie le produit récupère le document et reporte uniquement les
informations qu’elle peut vérifier.

## Avant de chercher

Photographier ou relever sur le contenant, avant de lancer une recherche :

- la marque et le nom commercial exact ;
- la référence, le format et la concentration (`15 %`, `30 % m/m`, etc.) ;
- le fabricant ou l’importateur ;
- le numéro UFI, le code-barres ou le numéro de lot s’ils sont présents ;
- la langue, la date de révision et la version de la FDS déjà éventuellement
  fournie.

Deux produits aux noms proches ne sont pas interchangeables : un pH- liquide,
un pH- poudre et un bidon d’acide de concentrations différentes nécessitent
leurs propres documents.

## Retrouver la bonne FDS

1. Chercher d’abord sur le site officiel du fabricant ou de l’importateur, dans
   les rubriques *FDS*, *SAV*, *documentation*, *téléchargements* ou *produits*.
2. Si elle n’est pas publiée, demander la FDS au vendeur ou au fabricant en
   donnant la référence exacte et une photo de l’étiquette. Conserver leur
   réponse avec le document.
3. Une recherche web manuelle peut aider à trouver la page officielle, par
   exemple : `"marque référence" "fiche de données de sécurité"` ou
   `site:exemple-fabricant.fr "référence" FDS`. Le résultat doit ensuite être
   vérifié sur le site de l’émetteur indiqué dans la FDS.
4. Télécharger le PDF ou conserver la page officielle, avec son URL, sa date
   de téléchargement et sa version/révision. Ne modifier ni le PDF ni son nom
   de fichier d’origine.

Ne pas retenir une FDS venant uniquement d’une place de marché, d’un forum ou
d’un site d’agrégation lorsque son origine, sa date ou son produit exact ne
peuvent pas être vérifiés. Ce document peut être un indice pour retrouver le
fabricant, pas une preuve suffisante pour paramétrer l’application.

## Vérifier que le document correspond au bidon

Comparer l’étiquette et la **section 1 — Identification** de la FDS : nom du
produit, fournisseur, référence et usage. Comparer ensuite la forme et la
concentration avec la **section 3 — Composition / informations sur les
composants**. La date de révision doit être lisible.

Arrêter ici et demander confirmation au fournisseur si l’un de ces éléments ne
correspond pas, si la concentration n’est pas indiquée, si le document est
incomplet ou si le produit a changé de fournisseur.

## Lire la FDS utilement

Lire au minimum ces sections avant toute manipulation :

| Section FDS | Ce qu’il faut relever | Décision pratique |
| --- | --- | --- |
| 1. Identification | Produit exact, fournisseur, révision, usage prévu | Vérifier qu’il s’agit bien du bidon présent. |
| 2. Identification des dangers | Pictogrammes, mentions de danger, conseils de prudence | Préparer les protections et écarter les personnes non équipées. |
| 3. Composition | Substance, concentration, éventuellement densité déclarée | Ne reporter dans l’application que les nombres et unités explicitement indiqués. |
| 4. Premiers secours | Conduite à tenir en cas de projection ou d’inhalation | Savoir où trouver eau de rinçage et numéro d’urgence avant ouverture. |
| 6. Dispersion accidentelle | Confinement, nettoyage, produits à éviter | Ne pas improviser l’absorption ou le rinçage. |
| 7. Manipulation et stockage | Aération, récipient, température, séparation des produits | Organiser la zone de travail et le stockage. |
| 8. Contrôles de l’exposition / protection individuelle | Gants, lunettes/visière, vêtements et ventilation demandés | Porter l’équipement réellement indiqué par cette FDS. |
| 10. Stabilité et réactivité | Produits incompatibles et conditions à éviter | Ne jamais rapprocher ou mélanger les produits incompatibles. |
| 13. Élimination | Filière et consignes pour produit/restes/contenant | Ne pas vider un reste dans le bassin, l’évier ou la poubelle sans consigne. |

Les sections 14 et 15 peuvent aussi préciser le transport et les informations
réglementaires. Elles sont utiles pour déplacer ou stocker un produit, mais ne
déterminent pas une dose piscine.

## Ce que l’application peut recevoir, et ce qu’elle ne doit pas déduire

| Information | Source à privilégier | Usage dans `piscine-ph` |
| --- | --- | --- |
| Concentration de soude NaOH | Étiquette ou FDS du produit exact | Saisir `g/L`, ou `% m/m` avec la densité explicitement déclarée, ou `% m/v`. Ne jamais déduire une densité. |
| Pureté d’un pH+ carbonate (`Na2CO3`) | Étiquette ou FDS du produit exact | Saisir le libellé, le pourcentage et choisir la source correspondante pour l’étude sans dosage. |
| Acide sulfurique | Étiquette, notice et FDS du produit couvert | Le parcours n’est valable que pour l’acide sulfurique 15 % déclaré ; une autre concentration ne doit pas être assimilée. |
| Chlore actif, galets et conditions d’emploi | Étiquette ou notice du produit exact | Déclarer le produit et ses seuils ; une FDS ne remplace pas une consigne de dosage. |
| CYA, pH et TAC du bassin | Mesures réalisées dans le bassin | Ne jamais les estimer depuis la FDS, le nombre de galets ou un calcul théorique. |

Si une valeur utile n’est lisible ni sur l’étiquette ni dans une FDS vérifiée,
ne pas la deviner et ne pas sélectionner « FDS » dans l’application. Conserver
la référence du produit, demander le document au fournisseur et reprendre le
parcours lorsque l’information est confirmée.

## Trace à conserver avec le produit

Pour chaque bidon ou sac utilisé, noter dans un carnet ou un dossier local :
le nom du fichier FDS, l’URL ou le contact du fournisseur, la date de
téléchargement, la date de révision, la référence produit et les champs repris
dans l’application. Les archives JSON de `piscine-ph` enregistrent les valeurs
déclarées pour un protocole ; elles ne remplacent pas la conservation de la FDS
source.

En cas de contradiction entre une ancienne FDS, une fiche commerciale et
l’étiquette du produit réellement présent, arrêter le protocole : l’étiquette
et la FDS actuelle du produit exact doivent être clarifiées avec le fournisseur.
