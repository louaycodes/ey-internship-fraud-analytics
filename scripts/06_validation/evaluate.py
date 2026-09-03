import pandas as pd
import numpy as np

def evaluate():
    journal_path = "tests/test1_generalisation/data/journal_fraudes_injectees.csv"
    tx_path = "tests/test1_generalisation/resultats/transactions_scorees.csv"
    
    df_journal = pd.read_csv(journal_path)
    df_tx = pd.read_csv(tx_path)

    # 1. Recuperation des ID detectes (identique a ml_script.py)
    # Regles
    anomaly_tx_ids_regles = set(df_tx.loc[df_tx["score_risque"] >= 1, "id_transaction"])
    frs_rule_frs = set(df_tx.loc[(df_tx["regle_rib_partage"]==1) | (df_tx["regle_creation_tardive"]==1), "id_fournisseur"])
    
    # ML
    anomaly_tx_ids = set(df_tx.loc[df_tx["prediction_ml"] == 1, "id_transaction"])
    anomaly_frs_ids = set(df_tx.loc[df_tx["id_transaction"].isin(anomaly_tx_ids), "id_fournisseur"])
    
    # Combine (Regles + ML)
    anomaly_tx_ids_comb = anomaly_tx_ids_regles.union(anomaly_tx_ids)
    anomaly_frs_ids_comb = frs_rule_frs.union(anomaly_frs_ids)
    
    # Collusion
    anomaly_tx_ids_coll = set()
    anomaly_frs_ids_coll = set(df_tx.loc[df_tx["fournisseur_suspect_collusion"] == "oui", "id_fournisseur"])
    
    # Evaluation de Recall (identique a ml_script.py)
    def evaluate_system(journal, tx_ids, frs_ids):
        def det(row):
            if row["type_fraude"].startswith("Collusion"):
                refs = str(row["reference"]).replace("/", ",").split(",")
                return any(fid in frs_ids or fid in tx_ids for fid in refs)
            if row.get("ref_type", "TX" if "TX-" in str(row["reference"]) else "FRS") == "TX":
                return str(row["reference"]) in tx_ids
            else:
                return str(row["reference"]) in frs_ids
                
        detectes = journal.apply(det, axis=1)
        
        # Categorisation identique a generatordata/ml_script
        n_classiques = ~journal["type_fraude"].str.startswith("Multi-signaux") & ~journal["type_fraude"].str.startswith("Collusion")
        n_multi = journal["type_fraude"].str.startswith("Multi-signaux")
        n_coll = journal["type_fraude"].str.startswith("Collusion")
        
        return {
            "recall_classiques": detectes[n_classiques].sum() / n_classiques.sum() if n_classiques.sum() else 0,
            "recall_multi": detectes[n_multi].sum() / n_multi.sum() if n_multi.sum() else 0,
            "recall_coll": detectes[n_coll].sum() / n_coll.sum() if n_coll.sum() else 0,
            "recall_global": detectes[n_classiques | n_multi].sum() / (n_classiques.sum() + n_multi.sum())
        }

    res_regles = evaluate_system(df_journal, anomaly_tx_ids_regles, frs_rule_frs)
    res_ml = evaluate_system(df_journal, anomaly_tx_ids, anomaly_frs_ids)
    res_comb = evaluate_system(df_journal, anomaly_tx_ids_comb, anomaly_frs_ids_comb)
    res_coll = evaluate_system(df_journal, anomaly_tx_ids_coll, anomaly_frs_ids_coll)
    
    # Calcul de Precision
    def calc_precision(df_f, tx_ids, name):
        df_flagged = df_f[df_f["id_transaction"].isin(tx_ids)]
        total_flagged = len(df_flagged)
        if total_flagged == 0: return 0, 0, 0
        
        # Vrais positifs = lies aux cas (approximation via frs/tx suspect)
        # Plus simple: chercher ce qu'on trouve...
        return total_flagged, 0, 0

    print(f"Règles: Recall global: {res_regles['recall_global']:.1%}")
    print(f"ML: Recall global: {res_ml['recall_global']:.1%}")
    print(f"Combiné: Recall global: {res_comb['recall_global']:.1%}")
    print(f"Collusion: Recall coll: {res_coll['recall_coll']:.1%}")

if __name__ == "__main__":
    evaluate()
