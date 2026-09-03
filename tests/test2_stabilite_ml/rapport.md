# Rapport du Test 2 — Stabilité du modèle ML (Isolation Forest)

## Objectif
Évaluer la stabilité du modèle `IsolationForest` face à l'aléa de son initialisation (`random_state`). Sur des données identiques (jeu de référence Seed 42), un modèle instable produirait des prédictions très différentes selon la graine aléatoire choisie, ce qui compromettrait sa fiabilité en production.

## Méthodologie
- **Données** : Jeu de référence fixe (généré avec le seed 42).
- **Entraînement** : Le modèle Isolation Forest a été ré-entraîné 5 fois avec les mêmes hyperparamètres (`contamination=0.002`, `n_estimators=200`) mais avec 5 `random_state` différents : 1, 42, 100, 2024, 7.
- **Évaluation** : Pour chaque modèle, le pipeline complet a été ré-exécuté, et les performances du ML seul ont été mesurées avec la méthode stricte (fractions exactes) validée lors du Test 1.

## Résultats bruts

| Run (random_state) | Rappel Global (%) | Rappel Multi-signaux (%) | Précision (%) | Volume d'Alertes ML |
| :---: | :---: | :---: | :---: | :---: |
| **1** | 25.86% | 34.29% | 19.11% | 157 |
| **42** | 31.03% | 37.14% | 23.08% | 156 |
| **100** | 21.55% | 25.71% | 15.92% | 157 |
| **2024** | 24.14% | 28.57% | 17.83% | 157 |
| **7** | 24.14% | 22.86% | 17.95% | 156 |

## Synthèse Statistique

| Métrique | Minimum | Maximum | Moyenne | Écart-Type (StDev) |
| :--- | :---: | :---: | :---: | :---: |
| **Rappel Global** | 21.55% | 31.03% | **25.34%** | **3.46** |
| **Rappel Multi-signaux** | 22.86% | 37.14% | **29.71%** | **5.79** |
| **Précision** | 15.92% | 23.08% | **18.78%** | **2.62** |
| **Volume d'Alertes ML** | 156 | 157 | **156.6** | **0.55** |

*(Note: Le volume d'alertes ML est imposé de manière quasi-fixe par le paramètre `contamination=0.002` (0.2% de ~78 000 transactions = ~156), ce qui explique sa variance quasi nulle).*

## Conclusion et Analyse

**Le modèle présente une variance significative.**
- Bien que le volume d'alertes généré soit parfaitement stable (156-157), la *nature* des transactions isolées varie fortement selon l'arbre initial.
- Le taux de détection sur les fraudes complexes (multi-signaux) varie de **22.86% (pire cas) à 37.14% (meilleur cas, seed 42)**, soit un écart de plus de 14 points de pourcentage !
- La graine aléatoire 42 (utilisée jusqu'ici) s'avère être un "lucky seed", produisant des résultats nettement meilleurs que la moyenne (37% contre ~29% en moyenne).

### Décision
**Le modèle est considéré comme instable** dans sa configuration de base. Nous avons donc exploré deux pistes de stabilisation.

---

## Essais de Stabilisation

### Piste 1 : Augmentation du nombre d'arbres (`n_estimators`)

Nous avons ré-entraîné le modèle avec 500 puis 1000 arbres sur les mêmes 5 seeds.

**Résultats avec `n_estimators=500` :**
- **Rappel Global** : Moyenne 26.0% | Écart-type : 4.74 | (Min: 22.4%, Max: 33.6%)
- **Rappel Multi-signaux** : Moyenne 32.6% | Écart-type : **5.92** | (Min: 28.6%, Max: 42.9%)
- *Analyse* : La variance reste très forte (près de 14 points d'écart entre le min et le max sur le multi-signaux). 500 arbres ne suffisent pas à lisser le hasard.

**Résultats avec `n_estimators=1000` :**
- **Rappel Global** : Moyenne 25.5% | Écart-type : **1.98** | (Min: 23.3%, Max: 27.6%)
- **Rappel Multi-signaux** : Moyenne 33.1% | Écart-type : **1.56** | (Min: 31.4%, Max: 34.3%)
- *Analyse* : **Succès massif.** La variance s'effondre. L'écart-type passe de 5.79 (avec 200 arbres) à 1.56. Le rappel multi-signaux se stabilise dans une fourchette très étroite (entre 11 et 12 cas détectés sur 35, systématiquement). 

### Piste 2 : Ensemble de modèles (Moyenne des scores de 5 seeds)

Plutôt que d'utiliser un seul modèle, nous avons simulé un modèle "Ensemble" qui calcule la moyenne des scores d'anomalie (`decision_function`) de 5 modèles à 200 arbres (seeds 1, 42, 100, 2024, 7), puis qui applique un seuil pour isoler les 0.2% pires scores.
- **Rappel Global** : 23.3%
- **Rappel Multi-signaux** : 28.6%
- *Analyse* : Bien que cette méthode soit par définition 100% stable, ses performances absolues sont tirées vers le bas. La moyenne "écrase" les signaux très forts captés par certains modèles individuels. Le rappel multi-signaux de 28.6% est inférieur à la moyenne obtenue par un seul modèle à 1000 arbres (33.1%).

## Conclusion Finale
La **Piste 1 avec `n_estimators = 1000` est de loin la meilleure solution**.
Elle ramène l'écart-type largement en dessous du seuil cible de 5 points (1.56 pour le multi-signaux), tout en conservant une meilleure capacité de détection moyenne (33.1%) que l'approche ensembliste (28.6%). 

Bien que le "lucky seed" 42 à 200 arbres détectait miraculeusement 37% des fraudes multi-signaux, configurer 1000 arbres est la seule approche mathématiquement saine pour garantir une performance stable et reproductible en production.
