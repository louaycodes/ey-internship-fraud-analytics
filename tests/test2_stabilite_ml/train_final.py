import pandas as pd
import numpy as np
import os
import sys
import time
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(BASE_DIR, "../../")
sys.path.append(ROOT_DIR)

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

print("Entraînement de l'Isolation Forest (n_estimators=1000, random_state=42)...")
start_time = time.time()
model = IsolationForest(contamination=0.002, n_estimators=1000, random_state=42)
model.fit(X_scaled)
end_time = time.time()

model_path = os.path.join(ROOT_DIR, "models/isolation_forest_model.joblib")
joblib.dump(model, model_path)
joblib.dump(scaler, os.path.join(ROOT_DIR, "models/standard_scaler.joblib"))

model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
print(f"Temps d'entraînement : {end_time - start_time:.2f} secondes")
print(f"Taille du modèle exporté : {model_size_mb:.2f} MB")
