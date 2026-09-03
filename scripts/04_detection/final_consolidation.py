import pandas as pd
import numpy as np
import os

def consolider_scores(df_tx):
    print("\n================================================================")
    print("= CONSOLIDATION FINALE (NIVEAU 1 + 2 + 3)                      =")
    print("================================================================")
    df_tx = df_tx.copy()

    # Calcul du score_final de base : règles + ML
    # Assumant que score_risque vient de la partie Règles (0-4)
    # et prediction_ml (0 ou 1)
    if "score_final" not in df_tx.columns:
        if "score_risque" in df_tx.columns and "prediction_ml" in df_tx.columns:
            df_tx["score_final"] = df_tx["score_risque"] + df_tx["prediction_ml"]
        else:
            df_tx["score_final"] = 0

    # Normalisation du score_final (généralement 0-3 ou 0-4) sur une échelle de 0-50
    # Le max observé avant était de 3
    df_tx['score_final_normalise'] = (df_tx['score_final'] / 3.0) * 50.0

    # Formule : score_final_normalise + 50 si fournisseur suspect + 50 si employé suspect
    bonus_fournisseur = np.where(df_tx['fournisseur_suspect_collusion'] == 'oui', 50, 0)
    bonus_employe = np.where(df_tx['employe_suspect_collusion'] == 'oui', 50, 0)
    
    df_tx['score_risque_v2'] = df_tx['score_final_normalise'] + bonus_fournisseur + bonus_employe
    
    # Plafond à 100
    df_tx['score_risque_v2'] = df_tx['score_risque_v2'].clip(upper=100)

    # Calcul du niveau de risque
    def get_niveau_v2(score):
        if score < 25: return 'Faible'
        elif score < 50: return 'Moyen'
        elif score < 75: return 'Élevé'
        else: return 'Critique'

    df_tx['niveau_risque_final_v2'] = df_tx['score_risque_v2'].apply(get_niveau_v2)

    # Nettoyage structurel complet : suppression des colonnes inutiles ou obsolètes
    cols_to_drop = [
        'employe_initiateur_suspect', 'employe_validateur_suspect',
        'devise', 'niveau_risque', 'score_risque', 'score_final', 
        'score_final_normalise', 'niveau_risque_final'
    ]
    cols_to_drop = [c for c in cols_to_drop if c in df_tx.columns]
    df_export = df_tx.drop(columns=cols_to_drop)
    
    # Renommage propre des colonnes finales
    df_export = df_export.rename(columns={
        'score_risque_v2': 'score_risque',
        'niveau_risque_final_v2': 'niveau_risque'
    })
    
    # Tri par date_transaction
    if 'date_transaction' in df_export.columns:
        df_export['date_transaction'] = pd.to_datetime(df_export['date_transaction'])
        df_export = df_export.sort_values('date_transaction').reset_index(drop=True)

    return df_export

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    tx_path = os.path.join(base_dir, 'output_clean', 'scores_collusion.csv')
    journal_path = os.path.join(base_dir, 'data', 'raw', 'journal_fraudes_injectees.csv')

    print(f"Chargement de {tx_path}")
    df_tx = pd.read_csv(tx_path)
    
    initial_count = len(df_tx)
    
    df_export = consolider_scores(df_tx)
    
    final_count = len(df_export)
    print(f"Nombre de transactions avant : {initial_count}")
    print(f"Nombre de transactions après : {final_count}")
    if initial_count != final_count:
        print("❌ ERREUR : Le nombre de transactions a changé !")
    else:
        print("✅ VALIDÉ : Aucune transaction perdue.")

    print("\nDistribution des niveaux de risque finaux :")
    print(df_export['niveau_risque'].value_counts().to_string())

    output_path = os.path.join(base_dir, 'output_clean', 'transactions_scorees.csv')
    print(f"\nExport vers {output_path}")
    
    df_export.to_csv(output_path, index=False)
    print("✅ Export terminé avec succès.")

if __name__ == "__main__":
    main()
