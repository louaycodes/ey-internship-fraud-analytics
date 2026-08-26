# EY Internship — Fraud Analytics

Projet réalisé dans le cadre d'un stage au département AI & Data d'EY,
sous forme de mission de conseil simulée : le stagiaire joue à la fois le
rôle du client (TuniDistrib SA, entreprise fictive de distribution) et du
consultant EY chargé de résoudre sa problématique.

**Problématique client :** détection de transactions frauduleuses auprès
des fournisseurs (RIB partagés, fournisseurs fictifs, doublons de facturation).

**Approche technique :**
- Génération de données fictives et reliées (transactions, fournisseurs, employés)
- Nettoyage et normalisation (RIB, noms fournisseurs, seuils par fournisseur)
- Détection à 3 niveaux : règles métier, Machine Learning non-supervisé
  (Isolation Forest), analyse de graphe de collusion
- Restitution via un dashboard Power BI

**Contexte :** projet pédagogique s'appuyant sur des statistiques réelles
(EY Global Integrity Report, ACFE Report to the Nations) pour valider la
pertinence du sujet.