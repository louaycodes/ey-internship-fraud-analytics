import pandas as pd
import numpy as np
import os
import sys
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
final_consolidation = importlib.import_module("scripts.04_detection.final_consolidation")

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

seeds = [1, 42, 100, 2024, 7]
models = []

for seed in seeds:
    model = IsolationForest(contamination=0.002, n_estimators=200, random_state=seed)
    model.fit(X_scaled)
    models.append(model)

# Compute mean decision function
scores = np.array([model.decision_function(X_scaled) for model in models])
mean_scores = scores.mean(axis=0)

# The threshold is the 0.2th percentile (since contamination is 0.002)
# Lower score = more anomalous. We want the 0.2% lowest scores.
threshold = np.percentile(mean_scores, 0.2)

predictions = np.where(mean_scores < threshold, 1, 0)

print(f"Total alertes de l'ensemble: {predictions.sum()}")

# Load transactions with rules already computed
df_tx = pd.read_csv(os.path.join(ROOT_DIR, "output_clean/transactions_scorees_regles.csv"), parse_dates=["date_transaction"])

# Append predictions
df_tx["prediction_ml"] = predictions
df_tx["fournisseur_suspect_collusion"] = "non"
df_tx["employe_suspect_collusion"] = "non"

df_tx = final_consolidation.consolider_scores(df_tx)
out_path = os.path.join(ROOT_DIR, "tests/test2_stabilite_ml/transactions_scorees_ensemble.csv")
df_tx.to_csv(out_path, index=False)

j, t = load_data(os.path.join(ROOT_DIR, "data/raw/journal_fraudes_injectees.csv"), out_path)
metrics = evaluate_exact(j, t)

ml_global_num, ml_global_den = metrics["ml"]["global"]
ml_multi_num, ml_multi_den = metrics["ml"]["multi"]
total_alertes = predictions.sum()

rappel_global = ml_global_num / ml_global_den * 100 if ml_global_den else 0
rappel_multi = ml_multi_num / ml_multi_den * 100 if ml_multi_den else 0
precision = ml_global_num / total_alertes * 100 if total_alertes else 0

print(f"\n--- ENSEMBLE DE 5 MODELES ---")
print(f"Rappel Global: {rappel_global:.1f}%")
print(f"Rappel Multi: {rappel_multi:.1f}%")
print(f"Precision: {precision:.1f}%")
print(f"Alertes: {total_alertes}")
