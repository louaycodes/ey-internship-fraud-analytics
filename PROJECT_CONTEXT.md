> ⚠️ **Tout agent travaillant sur ce projet doit lire ce fichier en premier avant toute action.**

# Contexte du projet — EY Internship Fraud Analytics

## Objectif
Détecter des schémas de fraude transactionnelle et de collusion fournisseur-employé au sein d'une entreprise fictive de distribution (TuniDistrib SA). Ce projet de stage simule une mission de conseil EY en utilisant des données synthétiques complexes (injection de fraudes contrôlées) pour développer un pipeline de détection multi-niveaux.

## État actuel
- **Dernière étape complétée :** Audit complet du pipeline (cohérence bout-en-bout, anti-fuite, validation des chiffres, vérité terrain) et nettoyage structurel des fichiers de sortie terminés.
- **Prochaine étape prévue :** Tests de robustesse du modèle (généralisation sur nouvelles données, stabilité, sensibilité des seuils).
- **Date de dernière mise à jour :** 3 Septembre 2026

## Architecture du pipeline
1. ✅ **Génération des données** (`scripts/01_generation/generateData.py`) : Création des tables brutes avec injection du journal de fraude.
2. ✅ **Diagnostic** (`scripts/02_diagnostic/diagnosticData.py`) : Analyse de la qualité initiale.
3. ✅ **Nettoyage** (`scripts/03_cleaning/clean.py`) : Normalisation RIB, doublons.
4. ✅ **Niveau 1 : Règles métier** (`scripts/04_detection/detection_regles.py`) : Scoring basé sur l'expertise métier (heures/montants suspects, nouveaux fournisseurs).
5. ✅ **Niveau 2 : Machine Learning (Isolation Forest)** (`notebooks/fraud_detection_isolation_forest.ipynb`) : Détection non-supervisée d'anomalies multidimensionnelles + combinaison avec le score des règles.
6. ✅ **Niveau 3 : Analyse de Graphes (Collusion)** (`notebooks/graph_collusion_analysis.ipynb`) : Modélisation en graphe `G_suspect` et détection de communautés (Louvain) pour isoler les réseaux de collusion.

## Comment reprendre le travail (Prochaines étapes)

* Le pipeline complet peut désormais être exécuté via une seule commande :
  ```bash
  python run_pipeline.py --transactions data/raw/transactions.csv --fournisseurs data/raw/fournisseurs.csv --employes data/raw/employes.csv --output output_clean/transactions_scorees.csv
  ```
* Toute la logique métier est désormais consolidée de bout-en-bout. Le prochain objectif pourrait être d'industrialiser ce pipeline ou de l'intégrer avec une base de données / un outil de BI (PowerBI).

## Structure des dossiers
- **data/raw/** : Données brutes et journal des fraudes
- **output_clean/** : Dossier canonique de référence unique contenant toutes les données traitées et scorées (y compris le livrable final unique `transactions_scorees.csv` et les données archivées sous `archive/`)
- **scripts/** : Orchestration et logique modulaire
  - 01_generation/ : Génération des données simulées
  - 02_diagnostic/ : Évaluation initiale des données
  - 03_cleaning/ : Nettoyage et normalisation
  - 04_detection/ : Règles métier, ML (Isolation Forest), et graphes de collusion
  - 05_execution/ : Point d'entrée de l'orchestration (`run_pipeline.py`)
  - 06_validation/ : Scripts d'évaluation de la performance (rappel/précision) et de comparaison de modèles
- **notebooks/** : Notebooks Jupyter d'analyse, d'entraînement ML, et d'exploration de graphes
- **models/** : Modèles de machine learning exportés (joblib)
- **reports/** : Tableaux de bord et analyses générées
- **tests/** : Jeux de données de test et rapports d'expérience (ex: `test1_generalisation`)

## Schéma des données clés
Le fichier consolidé final **`transactions_scorees.csv`** contient 19 colonnes :
- **Métadonnées** : `id_transaction`, `date_transaction`, `id_fournisseur`, `montant`, `type_depense`, `mode_paiement`, `numero_facture`.
- **Acteurs internes** : `id_employe_initiateur`, `id_employe_validateur`, `statut_validation`.
- **Signaux Règles & ML** : `regle_rib_partage`, `regle_montant_anormal`, `regle_doublon_facture`, `regle_creation_tardive`, `prediction_ml` (Isolation Forest : -1 = Anomalie, 0/1 = Normal).
- **Signaux Collusion** : `fournisseur_suspect_collusion`, `employe_suspect_collusion` (oui/non).
- **Scoring Final** : `score_risque` (0-100), `niveau_risque` (Faible, Moyen, Élevé, Critique).

Les référentiels d'entités sont dans `fournisseurs_clean.csv` et `employes_clean.csv`. La vérité terrain est dans `journal_fraudes_injectees.csv`.
## Décisions techniques importantes à ne pas oublier
- **Anti-Leakage (ML)** : Les scores métier (Niveau 1) sont exclus des features d'entraînement de l'Isolation Forest pour éviter la fuite de données et assurer une détection purement comportementale.
- **Score Hybride** : Le modèle final combine le score des règles métier (fort pour les typologies connues) et le score ML (fort pour les anomalies subtiles/multidimensionnelles).
- **Stratégie Graphe (G_suspect)** : Le graphe complet contient trop de bruit (transactions normales). On filtre d'abord sur un lien de *contact physique* (adresse ou téléphone partagé), puis on inclut les transactions *uniquement* entre les nœuds suspects. C'est indispensable pour que Louvain détecte les collusions indirectes.
- **Validation (Nuance "Faux Positif")** : Un "faux positif pur" signifie qu'une transaction est totalement déconnectée d'un signal de fraude. Si un fournisseur a commis une fraude sur la transaction A, remonter ses autres transactions B et C n'est pas un faux positif d'un point de vue alerte métier, même si, au sens strict du journal, l'injection n'a touché que la transaction A.
## Résultats clés obtenus jusqu'ici
- **ML & Règles (Niveaux 1-2)** : Détectent très bien les fraudes transactionnelles isolées, mais échouent sur les cas de collusion (0/8 détectés) car le comportement unitaire semble légitime.
- **Graphes (Niveau 3)** : Le graphe filtré `G_suspect` permet à l'algorithme de Louvain de détecter **100% des clusters de collusion injectés (8/8)**, sans aucun faux positif parmi les coïncidences naturelles testées.

## Pièges déjà rencontrés (pour ne pas les refaire)
- **Confusion des versions (V2/V3/Final)** : L'utilisation de suffixes (`_v2`, `_v3`, `_final`) pour les fichiers de sortie a créé de l'ambiguïté sur lequel utiliser dans Power BI. *Solution* : Consolidation en un fichier unique `transactions_scorees.csv` avec renommage des étapes intermédiaires en `_regles` et `_ml`. Les anciens fichiers sont dans `/archive/`.
- **Collisions aléatoires du générateur** : Le générateur créait des doublons fortuits d'adresse (ex: FRS-00117 ↔ EMP-001) liés au paradoxe des anniversaires. *Solution* : Toujours vérifier manuellement par rapport au `coincidences_log.csv` et au journal des fraudes avant d'assumer une anomalie.
- **Bruit transactionnel dans les graphes** : Exécuter Louvain sur le graphe complet disperse les cas de collusion indirecte dans des communautés trop larges. *Solution* : Le filtrage par arêtes de contact (`G_suspect`) est obligatoire.
- **Évaluation de Généralisation (Test 1)** : Lors de la comparaison entre le modèle de référence et le nouveau modèle, une erreur consistait à comparer les pourcentages calculés deux fois sur le nouveau jeu, donnant l'illusion d'une perfection absolue (les chiffres sont sortis exactement pareils, 95.2% vs 95.2%). *Solution* : Toujours comparer avec le script de validation stricte `compare_exact.py` qui charge en simultané les deux journaux et compte de façon brute les numérateurs et dénominateurs.
## Comment reprendre le travail
1. Activer l'environnement Python : `source .venv/bin/activate`
2. Les scripts de base sont dans `/scripts/`, mais tout le pipeline a déjà tourné.
3. Les notebooks dans `/notebooks/` peuvent être relancés intégralement (`Run All`) sans casser l'état.
4. Les résultats actuels sont disponibles dans `/output_clean/` et `/reports/figures/`.

---
*Note: Cet état du projet doit être mis à jour à chaque fois qu'une nouvelle étape analytique ou d'ingénierie majeure est validée.*
