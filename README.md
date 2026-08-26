# EY Internship — Fraud Analytics

Projet réalisé dans le cadre d'un stage au département AI & Data d'EY, sous forme de mission de conseil simulée : le stagiaire joue à la fois le rôle du client (TuniDistrib SA, entreprise fictive de distribution) et du consultant EY chargé de résoudre sa problématique.

**Problématique client :** détection de transactions frauduleuses auprès des fournisseurs (RIB partagés, fournisseurs fictifs, doublons de facturation, anomalies statistiques).

**Approche technique :**
- Génération de données fictives et reliées (transactions, fournisseurs, employés)
- Nettoyage et normalisation (RIB, noms fournisseurs, seuils par fournisseur)
- Détection à 3 niveaux : règles métier, Machine Learning non-supervisé (Isolation Forest), analyse de graphe de collusion
- Restitution via un dashboard Power BI

**Contexte :** projet pédagogique s'appuyant sur des statistiques réelles (EY Global Integrity Report, ACFE Report to the Nations) pour valider la pertinence du sujet.

## Structure du projet

La structure du projet suit les standards Python avec une séparation claire entre les données, les scripts et les rapports :

```
DATA/
├── README.md                 # Ce fichier
├── requirements.txt          # Dépendances du projet
├── .gitignore                # Fichiers ignorés par Git
├── data/                     
│   ├── raw/                  # Données brutes générées
│   └── clean/                # Données nettoyées et préparées
├── scripts/
│   ├── 01_generation/        # Génération des données fictives et injection des fraudes
│   ├── 02_diagnostic/        # Analyse exploratoire et diagnostic des données brutes
│   ├── 03_cleaning/          # Nettoyage et normalisation
│   └── 04_detection/         # Règles de détection et validation croisée
└── reports/                  # Rapports générés (ex: rapport de diagnostic)
```

## Ordre d'exécution

Pour relancer l'ensemble du pipeline, exécutez les scripts dans cet ordre (depuis leur dossier respectif ou en adaptant les chemins) :

1. **Génération** : `cd scripts/01_generation && python3 generateData.py`
   Génère les données de base dans `data/raw/` et injecte les cas de fraude.
2. **Diagnostic** : `cd scripts/02_diagnostic && python3 diagnosticData.py`
   Analyse les données brutes et produit un rapport dans `reports/rapport_diagnostic.txt`.
3. **Nettoyage** : `cd scripts/03_cleaning && python3 clean.py`
   Normalise les données et exporte les versions propres dans `data/clean/`.
4. **Détection** : `cd scripts/04_detection && python3 detection_regles.py`
   Applique les règles métier sur les données propres et attribue un score.
5. **Validation** : `cd scripts/04_detection && python3 validation_detection.py`
   Croise les transactions flaguées avec le journal des fraudes pour calculer le rappel et le taux de faux positifs.