import pandas as pd
import sys

def load_data(journal_path, tx_path):
    df_journal = pd.read_csv(journal_path)
    df_tx = pd.read_csv(tx_path)
    return df_journal, df_tx

def evaluate_exact(df_journal, df_tx):
    # Regles
    tx_regles = set(df_tx.loc[df_tx["score_risque"] >= 1, "id_transaction"].astype(str))
    frs_regles = set(df_tx.loc[(df_tx["regle_rib_partage"]==1) | (df_tx["regle_creation_tardive"]==1), "id_fournisseur"].astype(str))
    
    # ML
    tx_ml = set(df_tx.loc[df_tx["prediction_ml"] == 1, "id_transaction"].astype(str))
    frs_ml = set(df_tx.loc[df_tx["id_transaction"].isin(tx_ml), "id_fournisseur"].astype(str))
    
    # Combine
    tx_comb = tx_regles.union(tx_ml)
    frs_comb = frs_regles.union(frs_ml)
    
    # Collusion
    frs_coll = set(df_tx.loc[df_tx.get("fournisseur_suspect_collusion", pd.Series()) == "oui", "id_fournisseur"].astype(str))
    emp_coll_init = set(df_tx.loc[df_tx.get("employe_suspect_collusion", pd.Series()) == "oui", "id_employe_initiateur"].dropna().astype(str))
    emp_coll_val = set(df_tx.loc[df_tx.get("employe_suspect_collusion", pd.Series()) == "oui", "id_employe_validateur"].dropna().astype(str))
    ent_coll = frs_coll.union(emp_coll_init).union(emp_coll_val)

    def det(row, tx_ids, frs_ids):
        # type_fraude in journal determines logic
        # reference could be comma separated
        refs = str(row["reference"]).replace("/", ",").split(",")
        refs = [r.strip() for r in refs if r.strip()]
        
        if row["type_fraude"].startswith("Collusion"):
            return any(fid in frs_ids for fid in refs)
            
        ref_type = row.get("ref_type")
        if pd.isna(ref_type):
            ref_type = "TX" if "TX-" in refs[0] else "FRS"
            
        if ref_type == "TX":
            return any(r in tx_ids for r in refs)
        else:
            return any(r in frs_ids for r in refs)

    n_classiques = ~df_journal["type_fraude"].str.startswith("Multi-signaux") & ~df_journal["type_fraude"].str.startswith("Collusion")
    n_multi = df_journal["type_fraude"].str.startswith("Multi-signaux")
    n_coll = df_journal["type_fraude"].str.startswith("Collusion")
    n_global = n_classiques | n_multi

    def get_metrics(tx_ids, frs_ids, use_coll=False):
        detectes = df_journal.apply(lambda r: det(r, tx_ids, frs_ids), axis=1)
        
        num_classiques = detectes[n_classiques].sum()
        den_classiques = n_classiques.sum()
        
        num_multi = detectes[n_multi].sum()
        den_multi = n_multi.sum()
        
        num_coll = detectes[n_coll].sum()
        den_coll = n_coll.sum()
        
        num_global = detectes[n_global].sum()
        den_global = n_global.sum()
        
        return {
            "classique": (num_classiques, den_classiques),
            "multi": (num_multi, den_multi),
            "coll": (num_coll, den_coll),
            "global": (num_global, den_global)
        }
        
    return {
        "regles": get_metrics(tx_regles, frs_regles),
        "ml": get_metrics(tx_ml, frs_ml),
        "comb": get_metrics(tx_comb, frs_comb),
        "collusion": get_metrics(set(), ent_coll, True)
    }

print("=== CHARGEMENT REFERENCE (Seed 42) ===")
ref_j, ref_t = load_data("data/raw/journal_fraudes_injectees.csv", "output_clean/archive/transactions_scorees_v3_complete.csv")
res_ref = evaluate_exact(ref_j, ref_t)

print("=== CHARGEMENT NOUVEAU JEU (Seed 999) ===")
new_j, new_t = load_data("tests/test1_generalisation/data/journal_fraudes_injectees.csv", "tests/test1_generalisation/resultats/transactions_scorees.csv")
res_new = evaluate_exact(new_j, new_t)

metrics = [
    ("regles", "classique"), ("regles", "global"),
    ("ml", "classique"), ("ml", "multi"), ("ml", "global"),
    ("comb", "classique"), ("comb", "multi"), ("comb", "global"),
    ("collusion", "coll")
]

for sys_name, met_name in metrics:
    r_num, r_den = res_ref[sys_name][met_name]
    n_num, n_den = res_new[sys_name][met_name]
    
    r_pct = (r_num/r_den*100) if r_den else 0
    n_pct = (n_num/n_den*100) if n_den else 0
    
    print(f"{sys_name.upper()} - {met_name.upper()}:")
    print(f"  Ref : {r_num}/{r_den} ({r_pct:.1f}%)")
    print(f"  New : {n_num}/{n_den} ({n_pct:.1f}%)")
    print()

