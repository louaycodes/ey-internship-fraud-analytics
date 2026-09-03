import pandas as pd
import numpy as np
import os
import joblib

def appliquer_ml(transactions, fournisseurs, profil, model_path, scaler_path):
    """
    Applique le modèle Isolation Forest sur les transactions pour la détection des anomalies.
    Retourne le DataFrame transactions enrichi de la colonne 'prediction_ml'.
    """
    print("\n🤖 Application du modèle Machine Learning (Isolation Forest)...")
    df_tx = transactions.copy()
    
    FEATURE_COLS = [
        "ecart_montant_normalise",
        "delai_depuis_creation",
        "ratio_concentration_employe",
        "rang_temporel_fournisseur",
        "jour_semaine",
        "jour_du_mois",
        "frequence_7j_fournisseur",
        "montant_log",
        "nb_tx_fournisseur",
        "auto_validation",
    ]
    
    df_features = df_tx.copy()
    
    # 1. ecart_montant_normalise
    df_features = df_features.merge(profil[["id_fournisseur", "montant_moyen", "montant_ecart_type", "nb_transactions"]], on="id_fournisseur", how="left")
    df_features["ecart_montant_normalise"] = np.where(
        df_features["montant_ecart_type"].fillna(0) == 0,
        0.0,
        (df_features["montant"] - df_features["montant_moyen"]) / df_features["montant_ecart_type"]
    )
    
    # 2. delai_depuis_creation
    df_frs_dates = fournisseurs[["id_fournisseur", "date_creation_fournisseur"]].copy()
    df_features = df_features.merge(df_frs_dates, on="id_fournisseur", how="left")
    df_features["delai_depuis_creation"] = (df_features["date_transaction"] - df_features["date_creation_fournisseur"]).dt.days
    df_features["delai_depuis_creation"] = df_features["delai_depuis_creation"].clip(lower=0)
    
    # 3. ratio_concentration_employe
    nb_tx_par_frs = df_features.groupby("id_fournisseur")["id_transaction"].transform("count")
    nb_tx_binome = df_features.groupby(["id_fournisseur", "id_employe_initiateur", "id_employe_validateur"])["id_transaction"].transform("count")
    df_features["ratio_concentration_employe"] = nb_tx_binome / nb_tx_par_frs
    
    # 4. rang_temporel_fournisseur
    df_features = df_features.sort_values(["id_fournisseur", "date_transaction"])
    df_features["rang_brut"] = df_features.groupby("id_fournisseur")["date_transaction"].rank(method="min")
    nb_tx_frs = df_features.groupby("id_fournisseur")["id_transaction"].transform("count")
    df_features["rang_temporel_fournisseur"] = df_features["rang_brut"] / nb_tx_frs
    df_features.drop(columns=["rang_brut"], inplace=True)
    
    # 5. jour_semaine + jour_du_mois
    df_features["jour_semaine"] = df_features["date_transaction"].dt.dayofweek
    df_features["jour_du_mois"] = df_features["date_transaction"].dt.day
    
    # 6. frequence_7j_fournisseur
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
    
    # 7. montant_log
    df_features["montant_log"] = np.log1p(df_features["montant"])
    
    # 8. nb_tx_fournisseur
    df_features["nb_tx_fournisseur"] = df_features["nb_transactions"]
    
    # 9. auto_validation
    df_features["auto_validation"] = (df_features["id_employe_initiateur"] == df_features["id_employe_validateur"]).astype(int)
    
    # S'assurer du même ordre de lignes que df_tx
    df_features = df_features.drop_duplicates(subset=["id_transaction"])
    df_features = df_tx[["id_transaction"]].merge(df_features[["id_transaction"] + FEATURE_COLS], on="id_transaction", how="left")
    df_features[FEATURE_COLS] = df_features[FEATURE_COLS].fillna(0)
    
    X_raw = df_features[FEATURE_COLS].values
    
    try:
        scaler = joblib.load(scaler_path)
        model = joblib.load(model_path)
        X_scaled = scaler.transform(X_raw)
        preds = model.predict(X_scaled)
        # Isolation Forest : -1 = anomalie, 1 = normal
        df_tx["prediction_ml"] = np.where(preds == -1, 1, 0)
        nb_anomalies = df_tx["prediction_ml"].sum()
        print(f"   ✓ Modèle chargé et prédictions effectuées : {nb_anomalies:,} transaction(s) signalée(s)")
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement/prédiction du modèle ML : {e}")
        df_tx["prediction_ml"] = 0

    return df_tx

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")
    
    print("=" * 60)
    print("  DÉTECTION DE FRAUDE — SCORING ML (Niveau 2)")
    print("=" * 60)
    
    transactions = pd.read_csv(os.path.join(INPUT_DIR, "transactions_scorees_regles.csv"), parse_dates=["date_transaction"])
    fournisseurs = pd.read_csv(os.path.join(INPUT_DIR, "fournisseurs_clean.csv"), parse_dates=["date_creation_fournisseur"])
    profil = pd.read_csv(os.path.join(INPUT_DIR, "profil_montant_fournisseur.csv"))
    
    model_path = os.path.join(BASE_DIR, "../../models", "isolation_forest_model.joblib")
    scaler_path = os.path.join(BASE_DIR, "../../models", "standard_scaler.joblib")
    
    transactions = appliquer_ml(transactions, fournisseurs, profil, model_path, scaler_path)
    
    transactions.to_csv(os.path.join(INPUT_DIR, "transactions_scorees_ml.csv"), index=False)
    print(f"\n💾 Export sauvegardé sous output_clean/transactions_scorees_ml.csv")
