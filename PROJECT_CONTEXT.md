> ⚠️ **Tout agent travaillant sur ce projet doit lire ce fichier en premier avant toute action.**

# Contexte du projet — EY Internship Fraud Analytics

## Objectif
Détecter des schémas de fraude transactionnelle et de collusion fournisseur-employé au sein d'une entreprise fictive de distribution (TuniDistrib SA). Ce projet de stage simule une mission de conseil EY en utilisant des données synthétiques complexes (injection de fraudes contrôlées) pour développer un pipeline de détection multi-niveaux.

## État actuel
- **Dernière étape complétée :** Niveau 3 (Graphe de collusion) terminé et validé. Détection réussie des fraudes directes et indirectes. Nettoyage du projet effectué.
- **Prochaine étape prévue :** (À définir - potentiellement restitution/dashboarding Power BI).
- **Date de dernière mise à jour :** 31 Août 2026

## Architecture du pipeline
1. ✅ **Génération des données** (`scripts/01_generation/generateData.py`) : Création des tables brutes avec injection du journal de fraude.
2. ✅ **Diagnostic** (`scripts/02_diagnostic/diagnosticData.py`) : Analyse de la qualité initiale.
3. ✅ **Nettoyage** (`scripts/03_cleaning/clean.py`) : Normalisation RIB, doublons.
4. ✅ **Niveau 1 : Règles métier** (`scripts/04_detection/detection_regles.py`) : Scoring basé sur l'expertise métier (heures/montants suspects, nouveaux fournisseurs).
5. ✅ **Niveau 2 : Machine Learning (Isolation Forest)** (`notebooks/fraud_detection_isolation_forest.ipynb`) : Détection non-supervisée d'anomalies multidimensionnelles + combinaison avec le score des règles.
6. ✅ **Niveau 3 : Analyse de Graphes (Collusion)** (`notebooks/graph_collusion_analysis.ipynb`) : Modélisation en graphe `G_suspect` et détection de communautés (Louvain) pour isoler les réseaux de collusion.

## Structure des dossiers
- `/data/raw/` : Données brutes et `journal_fraudes_injectees.csv` (la "vérité terrain").
- `/data/clean/` : Fichiers intermédiaires propres (`transactions_scorees.csv`, `fournisseurs_clean.csv`).
- `/output_clean/` : Résultats finaux et exports enrichis (`scores_collusion.csv`, `transactions_scorees_final.csv`).
- `/notebooks/` : Analyses avancées (ML et Graphes).
- `/scripts/` : Pipeline d'ingénierie de données (génération, nettoyage, règles de base).
- `/reports/figures/` : Visualisations et graphiques finaux.

## Schéma des données clés
- **`transactions_scorees_final.csv`** : Transactions avec features ML, scores de règles (`score_fraude_regles`), score ML (`score_fraude_ml`), et flags d'anomalies.
- **`fournisseurs_clean.csv` / `employes_clean.csv`** : Référentiels entités avec adresses et téléphones normalisés.
- **`journal_fraudes_injectees.csv`** : Source de vérité listant les ID et types de fraudes injectées (RIB modifiés, montants anormaux, collusion, etc.).
- **`scores_collusion.csv`** : Résultat du Niveau 3, liste les entités appartenant à un cluster de collusion identifié par graphe.

## Décisions techniques importantes à ne pas oublier
- **Anti-Leakage (ML)** : Les scores métier (Niveau 1) sont exclus des features d'entraînement de l'Isolation Forest pour éviter la fuite de données et assurer une détection purement comportementale.
- **Score Hybride** : Le modèle final combine le score des règles métier (fort pour les typologies connues) et le score ML (fort pour les anomalies subtiles/multidimensionnelles).
- **Stratégie Graphe (G_suspect)** : Le graphe complet contient trop de bruit (transactions normales). On filtre d'abord sur un lien de *contact physique* (adresse ou téléphone partagé), puis on inclut les transactions *uniquement* entre les nœuds suspects. C'est indispensable pour que Louvain détecte les collusions indirectes.

## Résultats clés obtenus jusqu'ici
- **ML & Règles (Niveaux 1-2)** : Détectent très bien les fraudes transactionnelles isolées, mais échouent sur les cas de collusion (0/8 détectés) car le comportement unitaire semble légitime.
- **Graphes (Niveau 3)** : Le graphe filtré `G_suspect` permet à l'algorithme de Louvain de détecter **100% des clusters de collusion injectés (8/8)**, sans aucun faux positif parmi les coïncidences naturelles testées.

## Pièges déjà rencontrés (pour ne pas les refaire)
- **Collisions aléatoires du générateur** : Le générateur créait des doublons fortuits d'adresse (ex: FRS-00117 ↔ EMP-001) liés au paradoxe des anniversaires. *Solution* : Toujours vérifier manuellement par rapport au `coincidences_log.csv` et au journal des fraudes avant d'assumer une anomalie.
- **Bruit transactionnel dans les graphes** : Exécuter Louvain sur le graphe complet disperse les cas de collusion indirecte dans des communautés trop larges. *Solution* : Le filtrage par arêtes de contact (`G_suspect`) est obligatoire.

## Comment reprendre le travail
1. Activer l'environnement Python : `source .venv/bin/activate`
2. Les scripts de base sont dans `/scripts/`, mais tout le pipeline a déjà tourné.
3. Les notebooks dans `/notebooks/` peuvent être relancés intégralement (`Run All`) sans casser l'état.
4. Les résultats actuels sont disponibles dans `/output_clean/` et `/reports/figures/`.

---
*Note: Cet état du projet doit être mis à jour à chaque fois qu'une nouvelle étape analytique ou d'ingénierie majeure est validée.*
