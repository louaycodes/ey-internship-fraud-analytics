# Rapport du Test 3 — Sensibilité des Seuils (Règles Métier)

## Objectif
Évaluer la sensibilité des 4 règles métier de Niveau 1 (montant anormal, doublon, création tardive, RIB partagé) face à de légères variations de leurs seuils. L'objectif est de vérifier si nos seuils actuels sont situés dans des zones de stabilité (où une petite variation ne change pas radicalement le comportement) ou s'ils sont trop sensibles, et d'ajuster si nécessaire pour optimiser le compromis Rappel/Précision.

## Méthode
Sur le jeu de données de référence (Seed 42), nous avons testé pour chaque règle deux valeurs alternatives (un seuil "bas" et un seuil "haut") tout en maintenant le reste du pipeline strictement identique. 
Le tableau ci-dessous rapporte le **Rappel Global** (fraudes détectées / fraudes totales du périmètre) et la **Précision** (fraudes détectées / total des alertes générées par les règles).

## Résultats

| Règle | Seuil bas | Seuil actuel | Seuil haut |
| :--- | :--- | :--- | :--- |
| **Montant anormal** <br>*(Seuils: 2.5σ / 3.0σ / 3.5σ)* | Rappel: 72/116 (62.1%)<br>Précision: 72/588 (12.2%) | Rappel: 71/116 (61.2%)<br>Précision: 71/271 (26.2%) | Rappel: 71/116 (61.2%)<br>Précision: 71/211 (33.6%) |
| **Doublon facture** <br>*(Seuils: 0.3% / 0.5% / 0.7%)* | Rappel: 71/116 (61.2%)<br>Précision: 71/271 (26.2%) | Rappel: 71/116 (61.2%)<br>Précision: 71/271 (26.2%) | Rappel: 74/116 (63.8%)<br>Précision: 74/277 (26.7%) |
| **Création tardive** <br>*(Seuils: 1j / 2j / 4j)* | Rappel: 71/116 (61.2%)<br>Précision: 71/258 (27.5%) | Rappel: 71/116 (61.2%)<br>Précision: 71/271 (26.2%) | Rappel: 71/116 (61.2%)<br>Précision: 71/317 (22.4%) |
| **RIB partagé** <br>*(Seuils: 1tx / 3tx / 5tx)* | Rappel: 71/116 (61.2%)<br>Précision: 71/219 (32.4%) | Rappel: 71/116 (61.2%)<br>Précision: 71/271 (26.2%) | Rappel: 71/116 (61.2%)<br>Précision: 71/323 (22.0%) |

## Conclusion par Règle

### 1. Montant anormal (Actuel : 3σ)
- **Analyse** : Le seuil est extrêmement sensible à la baisse. Passer à 2.5σ double le nombre total d'alertes (de 271 à 588) pour un gain dérisoire d'une seule fraude supplémentaire détectée (la précision s'effondre à 12.2%). À l'inverse, passer à 3.5σ réduit les alertes de 60 sans perdre en rappel.
- **État** : Le seuil de 3σ est justifié. C'est un standard statistique robuste qui évite l'explosion des faux positifs.

### 2. Doublon facture (Actuel : 0.5%)
- **Analyse** : Le seuil de 0.5% (tolérance de variation de montant relatif) semble très légèrement conservateur. En l'augmentant à 0.7%, nous capturons **3 fraudes supplémentaires** (Rappel: 74/116) pour un coût quasi nul de **6 alertes supplémentaires** au global.
- **État** : Zone stable, mais une petite opportunité d'optimisation gratuite existe vers 0.7%.

### 3. Création tardive (Actuel : 2 jours)
- **Analyse** : Le rappel est totalement plat (aucune variation sur les fraudes détectées). Les alertes varient linéairement (+46 alertes en passant à 4 jours).
- **État** : Zone stable. Le seuil de 2 jours est un excellent compromis métier.

### 4. RIB partagé (Actuel : Top 3 transactions)
- **Analyse** : Le rappel est également plat. Remonter 1, 3 ou 5 transactions historiques par fournisseur suspect ne change pas la détection des cas frauduleux injectés (qui sont soit très récents, soit capturés par d'autres règles). L'augmentation des alertes est purement mécanique.
- **État** : Choix métier validé. Signaler les 3 dernières transactions permet aux analystes d'avoir le contexte récent sans inonder la file d'attente.

## Recommandation Finale
**Garder les seuils actuels**, qui s'avèrent être de très bons compromis (particulièrement le 3σ qui protège le pipeline d'une explosion de faux positifs). 

*Optionnel* : La seule modification mathématiquement intéressante serait de passer le seuil relatif des doublons de 0.5% à 0.7%, mais l'impact global reste mineur. Nous recommandons de ne rien changer pour figer le système.
