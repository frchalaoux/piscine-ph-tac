# Donnees d'exploitation

Les fichiers JSON produits par `piscine-ph` sont enregistres dans `data/protocoles/`.

Ce sous-dossier est volontairement ignore par Git : il contient les mesures reelles du bassin et les journaux de protocole.

Après un clonage depuis GitHub, ce sous-dossier peut être absent car il ne contient aucune donnée versionnée. L'application le recrée automatiquement au lancement, avant toute lecture ou écriture d'archive.
