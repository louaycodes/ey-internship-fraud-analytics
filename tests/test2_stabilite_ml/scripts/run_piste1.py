import pandas as pd
import numpy as np
import os
import joblib
import sys
import subprocess
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(BASE_DIR, "../../")
sys.path.append(ROOT_DIR)

compare_exact = importlib.import_module("scripts.06_validation.compare_exact")
load_data = compare_exact.load_data
evaluate_exact = compare_exact.evaluate_exact
clean = importlib.import_module("scripts.03_cleaning.clean")

def get_features(df_tx, fournisseurs, profil):
    FEATURE_COLS = [
        "ecart_montant_normalise", "delai_depuis_creation", "ratio_concentration_employe",
        "rang_temporel_fournisseur", "jour_semaine", "jour_du_mois", "frequence_7j_fournisseur",
        "montant_log", "nb_tx_fournisseur", "auto_validation",
    ]
    df_features = df_tx.copy()
    
    df_features = df_features.merge(profil[["id_fournisseur", "montant_moyen", "montant_ecart_type", "nb_transactions"]], on="id_fournisseur", how="left")
    df_features["ecart_montant_normalise"] = np.where(
        df_features["montant_ecart_type"].fillna(0) == 0,
        0.0,
        (df_features["montant"] - df_features["montant_moyen"]) / df_features["montant_ecart_type"]
    )
    
    df_frs_dates = fournisseurs[["id_fournisseur", "date_creation_fournisseur"]].copy()
    df_features = df_features.merge(df_frs_dates, on="id_fournisseur", how="left")
    df_features["delai_depuis_creation"] = (df_features["date_transaction"] - df_features["date_creation_fournisseur"]).dt.days
    df_features["delai_depuis_creation"] = df_features["delai_depuis_creation"].clip(lower=0)
    
    nb_tx_par_frs = df_features.groupby("id_fournisseur")["id_transaction"].transform("count")
    nb_tx_binome = df_features.groupby(["id_fournisseur", "id_employe_initiateur", "id_employe_validateur"])["id_transaction"].transform("count")
    df_features["ratio_concentration_employe"] = nb_tx_binome / nb_tx_par_frs
    
    df_features = df_features.sort_values(["id_fournisseur", "date_transaction"])
    df_features["rang_brut"] = df_features.groupby("id_fournisseur")["date_transaction"].rank(method="min")
    nb_tx_frs = df_features.groupby("id_fournisseur")["id_transaction"].transform("count")
    df_features["rang_temporel_fournisseur"] = df_features["rang_brut"] / nb_tx_frs
    df_features.drop(columns=["rang_brut"], inplace=True)
    
    df_features["jour_semaine"] = df_features["date_transaction"].dt.dayofweek
    df_features["jour_du_mois"] = df_features["date_transaction"].dt.day
    
    def _count_rolling_7d(group):
        indexed = group.set_index("date_transaction")["id_transaction"]
        counts = indexed.rolling("7D").count().astype(int) - 1
        counts.index = group.index
        return counts
        
    df_sub = df_features[["id_transaction", "id_fournisseur", "date_transaction"]].sort_values(["id_fournisseur", "date_transaction"])
    freq_series = df_sub.groupby("id_fournisseur", group_keys=False).apply(_count_rolling_7d)
    df_sub = df_sub.copy()
    df_sub["frequence_7j_fournisseur"] = freq_series.values
    df_features = df_features.merge(df_sub[["id_transaction", "frequence_7j_fournisseur"]], on="id_transaction", how="left")
    
    df_features["montant_log"] = np.log1p(df_features["montant"])
    df_features["nb_tx_fournisseur"] = df_features["nb_transactions"]
    df_features["auto_validation"] = (df_features["id_employe_initiateur"] == df_features["id_employe_validateur"]).astype(int)
    
    df_features = df_features.drop_duplicates(subset=["id_transaction"])
    df_features = df_tx[["id_transaction"]].merge(df_features[["id_transaction"] + FEATURE_COLS], on="id_transaction", how="left")
    df_features[FEATURE_COLS] = df_features[FEATURE_COLS].fillna(0)
    
    return df_features[FEATURE_COLS].values

df_tx_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/transactions.csv"), parse_dates=["date_transaction"])
df_frs_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/fournisseurs.csv"), parse_dates=["date_creation_fournisseur"])
df_emp_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/employes.csv"))

df_tx, df_frs, df_emp, profil = clean.nettoyer_donnees(df_tx_raw, df_frs_raw, df_emp_raw)
X_raw = get_features(df_tx, df_frs, profil)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)
joblib.dump(scaler, os.path.join(ROOT_DIR, "models/standard_scaler.joblib"))

seeds = [1, 42, 100, 2024, 7]
n_estimators_list = [500, 1000]

with open(os.path.join(ROOT_DIR, "tests/test2_stabilite_ml/piste1_results.txt"), "w") as f_out:
    for n_est in n_estimators_list:
        results = []
        f_out.write(f"\n====================================\n")
        f_out.write(f"TEST AVEC n_estimators = {n_est}\n")
        f_out.write(f"====================================\n")
        
        for seed in seeds:
            model = IsolationForest(contamination=0.002, n_estimators=n_est, random_state=seed)
            model.fit(X_scaled)
            joblib.dump(model, os.path.join(ROOT_DIR, "models/isolation_forest_model.joblib"))
            
            subprocess.run([
                sys.executable, 
                os.path.join(ROOT_DIR, "scripts/05_execution/run_pipeline.py"),
                "--transactions", os.path.join(ROOT_DIR, "data/raw/transactions.csv"),
                "--fournisseurs", os.path.join(ROOT_DIR, "data/raw/fournisseurs.csv"),
                "--employes", os.path.join(ROOT_DIR, "data/raw/employes.csv"),
                "--output", os.path.join(ROOT_DIR, f"tests/test2_stabilite_ml/transactions_scorees_tmp.csv")
            ], stdout=subprocess.DEVNULL)
            
            j, t = load_data(os.path.join(ROOT_DIR, "data/raw/journal_fraudes_injectees.csv"), os.path.join(ROOT_DIR, f"tests/test2_stabilite_ml/transactions_scorees_tmp.csv"))
            metrics = evaluate_exact(j, t)
            
            ml_global_num, ml_global_den = metrics["ml"]["global"]
            ml_multi_num, ml_multi_den = metrics["ml"]["multi"]
            tx_ml = set(t.loc[t["prediction_ml"] == 1, "id_transaction"].astype(str))
            total_alertes = len(tx_ml)
            
            rappel_global = ml_global_num / ml_global_den * 100 if ml_global_den else 0
            rappel_multi = ml_multi_num / ml_multi_den * 100 if ml_multi_den else 0
            precision = ml_global_num / total_alertes * 100 if total_alertes else 0
            
            results.append({
                "seed": seed,
                "rappel_global": rappel_global,
                "rappel_multi": rappel_multi,
                "precision": precision,
                "alertes": total_alertes
            })
            f_out.write(f"Seed {seed}: Rappel Global={rappel_global:.1f}%, Rappel Multi={rappel_multi:.1f}%, Alertes={total_alertes}\n")
            
        df_res = pd.DataFrame(results)
        f_out.write(f"\nSYNTHÈSE STATISTIQUE n_estimators={n_est}:\n")
        f_out.write(str(df_res.describe()) + "\n")

print("Piste 1 terminée.")
