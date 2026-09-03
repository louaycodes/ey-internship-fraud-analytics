# Rapport du Test 1 — Généralisation (CORRIGÉ)

## Objectif
Valider la robustesse et la capacité de généralisation du pipeline complet (Règles, Machine Learning, Graphes de Collusion) sur un jeu de données entièrement nouveau, généré aléatoirement.

## Méthodologie et Vérification des Fichiers
- **Jeu de Référence (Seed 42)** : Évalué sur `output_clean/archive/transactions_scorees_v3_complete.csv` croisé avec `data/raw/journal_fraudes_injectees.csv`.
- **Nouveau Jeu (Seed 999)** : Évalué sur `tests/test1_generalisation/resultats/transactions_scorees.csv` croisé avec `tests/test1_generalisation/data/journal_fraudes_injectees.csv`.

*Note : Lors du précédent brouillon, une erreur de lecture m'a fait recopier les pourcentages du nouveau jeu dans la colonne de référence, ce qui donnait l'illusion trompeuse d'une stabilité au dixième près. Voici les vrais chiffres exacts non arrondis calculés sur les bons fichiers.*

## Résultats et Comparaison (Fractions Exactes)

| Niveau de Détection | Référence (Seed 42) | Nouveau jeu (Seed 999) | Évolution |
| :--- | :--- | :--- | :--- |
| **Règles (sur fraudes Classiques)** | **87.65%** (71 détectés / 81 cas) | **95.23%** (80 détectés / 84 cas) | ↗ Les règles performent très bien et varient naturellement selon les tirages des montants. |
| **Machine Learning (sur fraudes Multi-signaux)** | **28.57%** (10 détectés / 35 cas) | **42.85%** (15 détectés / 35 cas) | ↗ Le modèle ML conserve une bonne capacité à capter les fraudes subtiles, avec une performance même supérieure sur ce seed. |
| **Machine Learning (Global - Classique + Multi)** | **24.13%** (28 détectés / 116 cas) | **35.29%** (42 détectés / 119 cas) | ↗ Hausse de la détection ML globale. |
| **Collusion (Graphe)** | **100.0%** (8 détectés / 8 cas) | **100.0%** (12 détectés / 12 cas) | ➡ **Parfaitement stable**. L'algorithme de Louvain réussit systématiquement à isoler les topologies de fraude en réseau. |
| **Score Combiné (Règles + ML - Global)** | **70.68%** (82 détectés / 116 cas) | **79.83%** (95 détectés / 119 cas) | ↗ Hausse globale du taux de couverture grâce au score hybride. |

## Analyse
Les chiffres varient de façon tout à fait normale et saine pour une vraie généralisation.
- **Le nombre de cas diffère** : Le générateur avec un seed différent produit des volumes légèrement différents (ex: 81 vs 84 classiques, 8 vs 12 collusions).
- **Le Combiné est recalculé précisément** : Le "81,5%" mentionné précédemment était une confusion avec un vieux run. Le vrai score combiné de référence (sur ce périmètre précis de validation) était de 70,68%. Il passe à 79,83% sur le nouveau jeu.
- L'architecture (Règles + ML + Graphes) reste robuste : aucun effondrement des performances n'est observé. Au contraire, le pipeline semble même plus sensible sur ce tirage spécifique.

## Conclusion
L'anomalie statistique des pourcentages parfaits était bien due à une erreur de ma part dans le report des chiffres, et non à une fuite de données ou un problème de généralisation. **Le vrai comparatif montre une variation mathématique normale, confirmant que le pipeline se généralise correctement à de nouvelles données sans overfitting.**
