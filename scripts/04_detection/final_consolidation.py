import pandas as pd
import numpy as np
import os

def main():
    print("================================================================")
    print("= CONSOLIDATION FINALE (NIVEAU 1 + 2 + 3)                      =")
    print("================================================================")

    # 1. Chargement des données
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    tx_path = os.path.join(base_dir, 'output_clean', 'transactions_scorees_final.csv')
    collusion_path = os.path.join(base_dir, 'output_clean', 'scores_collusion.csv')
    journal_path = os.path.join(base_dir, 'data', 'raw', 'journal_fraudes_injectees.csv')

    print(f"Chargement de {tx_path}")
    df_tx = pd.read_csv(tx_path)
    print(f"Chargement de {collusion_path}")
    df_col = pd.read_csv(collusion_path)
    
    initial_count = len(df_tx)

    # 2. Préparation du dictionnaire de collusion
    # Création d'un dictionnaire {id_entite: 'oui'/'non'}
    dict_collusion = dict(zip(df_col['id'], df_col['suspect_collusion']))

    # 3. Mapping sur les transactions
    df_tx['fournisseur_suspect_collusion'] = df_tx['id_fournisseur'].map(dict_collusion).fillna('non')
    df_tx['employe_initiateur_suspect'] = df_tx['id_employe_initiateur'].map(dict_collusion).fillna('non')
    df_tx['employe_validateur_suspect'] = df_tx['id_employe_validateur'].map(dict_collusion).fillna('non')

    # Un employé est suspect si l'initiateur OU le validateur l'est
    df_tx['employe_suspect_collusion'] = np.where(
        (df_tx['employe_initiateur_suspect'] == 'oui') | (df_tx['employe_validateur_suspect'] == 'oui'),
        'oui', 'non'
    )

    # 4. Calcul du score de risque V2
    # Formule : score_final (règles+ML) + 50 si fournisseur suspect + 50 si employé suspect
    bonus_fournisseur = np.where(df_tx['fournisseur_suspect_collusion'] == 'oui', 50, 0)
    bonus_employe = np.where(df_tx['employe_suspect_collusion'] == 'oui', 50, 0)
    
    df_tx['score_risque_v2'] = df_tx['score_final'] + bonus_fournisseur + bonus_employe
    
    # Plafond à 100
    df_tx['score_risque_v2'] = df_tx['score_risque_v2'].clip(upper=100)

    # 5. Calcul du niveau de risque V2
    def get_niveau_v2(score):
        if score < 30: return 'Faible'
        elif score < 60: return 'Moyen'
        elif score < 85: return 'Élevé'
        else: return 'Critique'

    df_tx['niveau_risque_final_v2'] = df_tx['score_risque_v2'].apply(get_niveau_v2)

    # 6. Vérifications
    print("\n--- VÉRIFICATIONS ---")
    final_count = len(df_tx)
    print(f"Nombre de transactions avant : {initial_count}")
    print(f"Nombre de transactions après : {final_count}")
    if initial_count != final_count:
        print("❌ ERREUR : Le nombre de transactions a changé !")
    else:
        print("✅ VALIDÉ : Aucune transaction perdue.")

    print("\nDistribution des niveaux de risque finaux (V2) :")
    print(df_tx['niveau_risque_final_v2'].value_counts().to_string())

    # Vérification des fraudes injectées
    print("\n--- VÉRIFICATION SUR LE JOURNAL DE FRAUDES ---")
    df_journal = pd.read_csv(journal_path)
    
    # Types de fraudes de collusion
    collusion_types = ['Collusion - directe', 'Collusion - indirecte']
    df_journal_collusion = df_journal[df_journal['type_fraude'].isin(collusion_types)]
    
    if len(df_journal_collusion) > 0:
        fraudes_tx_indices = []
        for _, row in df_journal_collusion.iterrows():
            entities = row['reference'].split('/')
            mask = (df_tx['id_fournisseur'].isin(entities)) & ((df_tx['id_employe_initiateur'].isin(entities)) | (df_tx['id_employe_validateur'].isin(entities)))
            fraudes_tx_indices.extend(df_tx[mask].index.tolist())
            
        fraudes_tx_indices = list(set(fraudes_tx_indices))
        df_fraud_result = df_tx.loc[fraudes_tx_indices]
        critique_count = (df_fraud_result['niveau_risque_final_v2'] == 'Critique').sum()
        total_fraudes = len(df_fraud_result)
        
        print(f"Transactions de collusion injectées : {total_fraudes}")
        print(f"Dont classées en risque Critique : {critique_count} ({(critique_count/total_fraudes)*100:.1f}%)")
        
        if critique_count == total_fraudes:
            print("✅ VALIDÉ : 100% des cas de collusion sont classés Critique.")
        else:
            print("❌ ERREUR : Certains cas de collusion ne sont pas classés Critique.")
            display = df_fraud_result[df_fraud_result['niveau_risque_final_v2'] != 'Critique']
            print("Exemples de cas ratés :")
            print(display[['id_transaction', 'score_final', 'fournisseur_suspect_collusion', 'employe_suspect_collusion', 'score_risque_v2']].head())

    # Transactions multi-signaux (Critique + Règles + ML + Collusion)
    # Pour illustrer les cas les plus forts
    mask_multi = (
        (df_tx['niveau_risque_final_v2'] == 'Critique') &
        (df_tx['prediction_ml'] == -1) &
        (df_tx['score_risque'] > 0) & 
        ((df_tx['fournisseur_suspect_collusion'] == 'oui') | (df_tx['employe_suspect_collusion'] == 'oui'))
    )
    nb_multi = mask_multi.sum()
    print(f"\nTransactions multi-signaux très dangereuses (ML + Règles + Collusion + Critique) : {nb_multi}")

    # 7. Export
    output_path = os.path.join(base_dir, 'output_clean', 'transactions_scorees_v3_complete.csv')
    print(f"\nExport vers {output_path}")
    
    # On supprime les colonnes intermédiaires initiateur/validateur pour ne garder que la colonne synthétique
    cols_to_drop = ['employe_initiateur_suspect', 'employe_validateur_suspect']
    df_export = df_tx.drop(columns=cols_to_drop)
    
    # Tri par date_transaction pour respecter la chronologie
    if 'date_transaction' in df_export.columns:
        df_export['date_transaction'] = pd.to_datetime(df_export['date_transaction'])
        df_export = df_export.sort_values('date_transaction').reset_index(drop=True)
    
    df_export.to_csv(output_path, index=False)
    print("✅ Export terminé avec succès.")

if __name__ == "__main__":
    main()
