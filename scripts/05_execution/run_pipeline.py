import argparse
import os
import sys
import pandas as pd

# Ajout du répertoire racine au PYTHONPATH pour permettre les imports de 'scripts'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import importlib

clean = importlib.import_module('scripts.03_cleaning.clean')
nettoyer_donnees = clean.nettoyer_donnees

detection_regles = importlib.import_module('scripts.04_detection.detection_regles')
appliquer_regles = detection_regles.appliquer_regles

ml_features = importlib.import_module('scripts.04_detection.ml_features')
appliquer_ml = ml_features.appliquer_ml

collusion_graph = importlib.import_module('scripts.04_detection.collusion_graph')
detecter_collusion_graphe = collusion_graph.detecter_collusion_graphe

final_consolidation = importlib.import_module('scripts.04_detection.final_consolidation')
consolider_scores = final_consolidation.consolider_scores

def run_pipeline(fichier_transactions, fichier_fournisseurs, fichier_employes):
    print("🚀 Début du pipeline de détection...")
    
    BASE_DIR = os.getcwd()
    
    # =========================================================================
    # 1. NETTOYAGE ET NORMALISATION
    # =========================================================================
    print("\n[1/5] Nettoyage et normalisation des données...")
    df_tx = pd.read_csv(fichier_transactions, encoding="utf-8-sig")
    df_frs = pd.read_csv(fichier_fournisseurs, encoding="utf-8-sig")
    df_emp = pd.read_csv(fichier_employes, encoding="utf-8-sig")
    
    df_tx, df_frs, df_emp, profil_fournisseur = nettoyer_donnees(df_tx, df_frs, df_emp)

    # =========================================================================
    # 2. RÈGLES MÉTIER (NIVEAU 1)
    # =========================================================================
    print("\n[2/5] Application des règles métier (Niveau 1)...")
    df_tx, df_frs, _ = appliquer_regles(df_tx, df_frs, df_emp, profil_fournisseur)

    # =========================================================================
    # 3. MACHINE LEARNING (NIVEAU 2)
    # =========================================================================
    print("\n[3/5] Chargement du modèle ML et prédictions (Niveau 2)...")
    model_path = os.path.join(BASE_DIR, "models", "isolation_forest_model.joblib")
    scaler_path = os.path.join(BASE_DIR, "models", "standard_scaler.joblib")
    df_tx = appliquer_ml(df_tx, df_frs, profil_fournisseur, model_path, scaler_path)

    # =========================================================================
    # 4. GRAPHE DE COLLUSION (NIVEAU 3)
    # =========================================================================
    print("\n[4/5] Détection de collusion via les graphes (Niveau 3)...")
    df_tx = detecter_collusion_graphe(df_tx, df_frs, df_emp)

    # =========================================================================
    # 5. CONSOLIDATION DU SCORE FINAL
    # =========================================================================
    print("\n[5/5] Consolidation du score final...")
    df_final = consolider_scores(df_tx)
        
    print("\n✅ Pipeline terminé avec succès !")
    return df_final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exécuter le pipeline complet de détection de fraude.")
    parser.add_argument("--transactions", required=True, help="Chemin vers le fichier des transactions brutes")
    parser.add_argument("--fournisseurs", required=True, help="Chemin vers le fichier des fournisseurs bruts")
    parser.add_argument("--employes", required=True, help="Chemin vers le fichier des employés bruts")
    parser.add_argument("--output", default="output_clean/transactions_scorees_run_pipeline.csv", help="Chemin du fichier de sortie")
    
    args = parser.parse_args()
    
    df_result = run_pipeline(args.transactions, args.fournisseurs, args.employes)
    
    out_dir = os.path.dirname(args.output)
    if out_dir: os.makedirs(out_dir, exist_ok=True)
        
    df_result.to_csv(args.output, index=False)
    print(f"📁 Fichier sauvegardé sous : {args.output}")
