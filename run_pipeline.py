import pandas as pd
import numpy as np
import os
import re
import argparse
import joblib
import networkx as nx
from networkx.algorithms.community import louvain_communities
from difflib import SequenceMatcher

def normaliser_rib(rib):
    if pd.isna(rib):
        return rib
    return re.sub(r"[\s\-]", "", str(rib)).upper()

def run_pipeline(fichier_transactions, fichier_fournisseurs, fichier_employes):
    print("🚀 Début du pipeline de détection...")
    
    # Chemins de base (en supposant exécution depuis la racine du projet)
    BASE_DIR = os.getcwd()
    
    # =========================================================================
    # 1. NETTOYAGE ET NORMALISATION
    # =========================================================================
    print("1. Nettoyage et normalisation des données...")
    df_tx = pd.read_csv(fichier_transactions, encoding="utf-8-sig")
    df_frs = pd.read_csv(fichier_fournisseurs, encoding="utf-8-sig")
    df_emp = pd.read_csv(fichier_employes, encoding="utf-8-sig")
    
    df_frs["rib_iban_normalise"] = df_frs["rib_iban"].apply(normaliser_rib)
    
    df_tx["date_transaction"] = pd.to_datetime(df_tx["date_transaction"], errors="coerce")
    df_frs["date_creation_fournisseur"] = pd.to_datetime(df_frs["date_creation_fournisseur"], errors="coerce")
    df_emp["date_embauche"] = pd.to_datetime(df_emp["date_embauche"], errors="coerce")
    df_tx["montant"] = pd.to_numeric(df_tx["montant"], errors="coerce")
    
    df_tx = df_tx.dropna(subset=["date_transaction", "montant"]).copy()
    
    for col in ["nom_fournisseur", "adresse", "email_contact"]:
        if col in df_frs.columns:
            df_frs[col] = df_frs[col].astype(str).str.strip()
            
    profil_fournisseur = df_tx.groupby("id_fournisseur")["montant"].agg(
        montant_moyen="mean", montant_ecart_type="std", nb_transactions="count"
    ).reset_index()
    profil_fournisseur["montant_ecart_type"] = profil_fournisseur["montant_ecart_type"].fillna(0)

    # =========================================================================
    # 2. RÈGLES MÉTIER (NIVEAU 1)
    # =========================================================================
    print("2. Application des règles métier (Niveau 1)...")
    
    df_tx["regle_rib_partage"] = False
    df_tx["regle_montant_anormal"] = False
    df_tx["regle_doublon_facture"] = False
    df_tx["regle_creation_tardive"] = False

    # Règle 1
    rib_counts = df_frs["rib_iban_normalise"].value_counts()
    ribs_partages = rib_counts[rib_counts > 1].index
    fournisseurs_suspects = df_frs[df_frs["rib_iban_normalise"].isin(ribs_partages)]["id_fournisseur"]
    
    tx_frs_risque = df_tx[df_tx["id_fournisseur"].isin(fournisseurs_suspects)].copy()
    if not tx_frs_risque.empty:
        idx_top3 = tx_frs_risque.sort_values("date_transaction", ascending=False).groupby("id_fournisseur").head(3).index
        df_tx.loc[idx_top3, "regle_rib_partage"] = True
    
    # Règle 2
    tx_profil = df_tx.merge(profil_fournisseur, on="id_fournisseur", how="left")
    seuil_max = tx_profil["montant_moyen"] + (3 * tx_profil["montant_ecart_type"])
    condition_anormale = (tx_profil["nb_transactions"] >= 5) & (tx_profil["montant"] > seuil_max)
    df_tx.loc[condition_anormale, "regle_montant_anormal"] = True
    
    # Règle 3
    def _factures_proches(f1, f2):
        if pd.isna(f1) or pd.isna(f2): return False
        try:
            n1 = int(re.sub(r'\D', '', str(f1)))
            n2 = int(re.sub(r'\D', '', str(f2)))
            return abs(n1 - n2) <= 2
        except:
            return False

    df_tx_sorted = df_tx.sort_values(by=["id_fournisseur", "date_transaction"])
    doublons_idx = set()
    for frs_id, group in df_tx_sorted.groupby("id_fournisseur"):
        if len(group) < 2: continue
        dates = group["date_transaction"].values
        montants = group["montant"].values
        factures = group["numero_facture"].values
        indices = group.index.values
        for i in range(len(group) - 1):
            j_offset = 0
            while i + 1 + j_offset < len(group):
                j = i + 1 + j_offset
                delta_days = (pd.to_datetime(dates[j]) - pd.to_datetime(dates[i])).days
                if delta_days > 7:
                    break
                m1, m2 = montants[i], montants[j]
                if m1 > 0 and m2 > 0 and abs(m1 - m2) / max(m1, m2) <= 0.05:
                    if _factures_proches(factures[i], factures[j]):
                        doublons_idx.add(indices[i])
                        doublons_idx.add(indices[j])
                j_offset += 1
    df_tx.loc[list(doublons_idx), "regle_doublon_facture"] = True
    
    # Règle 4
    tx_frs = df_tx.merge(df_frs[["id_fournisseur", "date_creation_fournisseur"]], on="id_fournisseur", how="left")
    ecart_jours = (tx_frs["date_transaction"] - tx_frs["date_creation_fournisseur"]).dt.days
    df_tx.loc[(ecart_jours >= 0) & (ecart_jours <= 2), "regle_creation_tardive"] = True

    # =========================================================================
    # 3. MACHINE LEARNING (NIVEAU 2)
    # =========================================================================
    print("3. Chargement du modèle ML et prédictions (Niveau 2)...")
    
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
    df_features = df_features.merge(profil_fournisseur[["id_fournisseur", "montant_moyen", "montant_ecart_type", "nb_transactions"]], on="id_fournisseur", how="left")
    df_features["ecart_montant_normalise"] = np.where(
        df_features["montant_ecart_type"].fillna(0) == 0,
        0.0,
        (df_features["montant"] - df_features["montant_moyen"]) / df_features["montant_ecart_type"]
    )
    
    # 2. delai_depuis_creation
    df_frs_dates = df_frs[["id_fournisseur", "date_creation_fournisseur"]].copy()
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
    
    # Ensure correct order mapping
    df_features = df_features.drop_duplicates(subset=["id_transaction"])
    df_features = df_tx[["id_transaction"]].merge(df_features[["id_transaction"] + FEATURE_COLS], on="id_transaction", how="left")
    df_features[FEATURE_COLS] = df_features[FEATURE_COLS].fillna(0)
    
    X_raw = df_features[FEATURE_COLS].values
    
    try:
        scaler = joblib.load(os.path.join(BASE_DIR, "models", "standard_scaler.joblib"))
        model = joblib.load(os.path.join(BASE_DIR, "models", "isolation_forest_model.joblib"))
        X_scaled = scaler.transform(X_raw)
        preds = model.predict(X_scaled)
        df_tx["prediction_ml"] = np.where(preds == -1, 1, 0)
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement/prédiction du modèle ML : {e}")
        df_tx["prediction_ml"] = 0

    # =========================================================================
    # 4. GRAPHE DE COLLUSION (NIVEAU 3)
    # =========================================================================
    print("4. Construction du graphe de collusion (Niveau 3)...")
    
    G = nx.Graph()
    for _, row in df_frs.iterrows():
        G.add_node(row["id_fournisseur"], type="fournisseur", adresse=row["adresse"], tel=row.get("telephone", ""))
    for _, row in df_emp.iterrows():
        G.add_node(row["id_employe"], type="employe", adresse=row.get("adresse_personnelle", ""), tel=row.get("telephone", ""))
        
    for _, tx in df_tx.iterrows():
        frs = tx["id_fournisseur"]
        emp_i = tx.get("id_employe_initiateur")
        emp_v = tx.get("id_employe_validateur")
        
        if pd.notna(emp_i) and G.has_node(frs) and G.has_node(emp_i):
            if G.has_edge(emp_i, frs):
                G[emp_i][frs]["weight"] += 1
                G[emp_i][frs]["link_types"].add("transaction")
            else:
                G.add_edge(emp_i, frs, weight=1, link_types={"transaction"})
                
        if pd.notna(emp_v) and G.has_node(frs) and G.has_node(emp_v):
            if G.has_edge(emp_v, frs):
                G[emp_v][frs]["weight"] += 1
                G[emp_v][frs]["link_types"].add("transaction")
            else:
                G.add_edge(emp_v, frs, weight=1, link_types={"transaction"})

    def clean_str(s):
        return str(s).lower().strip() if pd.notna(s) and str(s).strip() != "" else None

    adresse_index = {}
    telephone_index = {}
    
    for node, data in G.nodes(data=True):
        addr = clean_str(data.get("adresse"))
        if addr:
            adresse_index.setdefault(addr, []).append(node)
            
        tel = clean_str(data.get("tel"))
        if tel:
            telephone_index.setdefault(tel, []).append(node)
            
    for addr, nodes in adresse_index.items():
        if len(nodes) >= 2:
            for i in range(len(nodes)):
                for j in range(i+1, len(nodes)):
                    u, v = nodes[i], nodes[j]
                    if G.has_edge(u, v):
                        G[u][v].setdefault("link_types", set()).add("adresse")
                        G[u][v]["adresse_partagee"] = addr
                    else:
                        G.add_edge(u, v, link_types={"adresse"}, adresse_partagee=addr)
                        
    for tel, nodes in telephone_index.items():
        if len(nodes) >= 2:
            for i in range(len(nodes)):
                for j in range(i+1, len(nodes)):
                    u, v = nodes[i], nodes[j]
                    if G.has_edge(u, v):
                        G[u][v].setdefault("link_types", set()).add("telephone")
                        G[u][v]["telephone_partage"] = tel
                    else:
                        G.add_edge(u, v, link_types={"telephone"}, telephone_partage=tel)

    # Exclusions
    exclusion_collision = {tuple(sorted(['FRS-00117', 'EMP-001']))}
    coinc_path = os.path.join(BASE_DIR, "data", "raw", "coincidences_log.csv")
    coinc_refs = set()
    if os.path.exists(coinc_path):
        df_coinc = pd.read_csv(coinc_path)
        coinc_refs = set(df_coinc["reference"].dropna().tolist())

    nodes_avec_contact = set()
    arêtes_contact_valides = []
    
    for u, v, data in G.edges(data=True):
        types = data.get("link_types", set())
        contact_types = types - {"transaction"}
        if not contact_types: continue
        
        pair = tuple(sorted([u, v]))
        if pair in exclusion_collision: continue
        if u in coinc_refs and v in coinc_refs: continue
        
        if "adresse" in contact_types:
            addr = data.get("adresse_partagee", "")
            if "internationale" in str(addr).lower(): continue
            
        nodes_avec_contact.add(u)
        nodes_avec_contact.add(v)
        arêtes_contact_valides.append((u, v, data))
        
    G_suspect = nx.Graph()
    for u, v, data in arêtes_contact_valides:
        for node in [u, v]:
            if node not in G_suspect:
                G_suspect.add_node(node, **G.nodes[node])
        G_suspect.add_edge(u, v, **data)
        
    for u, v, data in G.edges(data=True):
        types = data.get("link_types", set())
        if types != {"transaction"}: continue
        if u in nodes_avec_contact and v in nodes_avec_contact:
            for node in [u, v]:
                if node not in G_suspect:
                    G_suspect.add_node(node, **G.nodes[node])
            G_suspect.add_edge(u, v, **data)
    
    fournisseurs_collusion = set()
    employes_collusion = set()
    
    if len(G_suspect.nodes) > 0:
        communities = louvain_communities(G_suspect, seed=42)
        for comm in communities:
            if len(comm) >= 2:
                for n in comm:
                    if G.nodes[n]["type"] == "fournisseur":
                        fournisseurs_collusion.add(n)
                    else:
                        employes_collusion.add(n)
                        
    df_tx["fournisseur_suspect_collusion"] = df_tx["id_fournisseur"].apply(lambda x: "oui" if x in fournisseurs_collusion else "non")
    
    def check_emp_collusion(row):
        return "oui" if (row.get("id_employe_initiateur") in employes_collusion or 
                         row.get("id_employe_validateur") in employes_collusion) else "non"
                         
    df_tx["employe_suspect_collusion"] = df_tx.apply(check_emp_collusion, axis=1)

    # =========================================================================
    # 5. CONSOLIDATION DU SCORE FINAL
    # =========================================================================
    print("5. Consolidation du score final...")
    
    df_tx["score_regles"] = df_tx[["regle_rib_partage", "regle_montant_anormal", "regle_doublon_facture", "regle_creation_tardive"]].sum(axis=1)
    df_tx["score_ml"] = df_tx["prediction_ml"]
    
    def calculer_score_risque(row):
        score_base = row["score_regles"] + row["score_ml"]
        score_norm = (score_base / 3.0) * 50 if score_base <= 3 else 50
        
        bonus = 0
        if row["fournisseur_suspect_collusion"] == "oui": bonus += 50
        if row["employe_suspect_collusion"] == "oui": bonus += 50
        
        final = score_norm + bonus
        return min(final, 100)
        
    df_tx["score_risque"] = df_tx.apply(calculer_score_risque, axis=1)
    
    def categoriser_risque(score):
        if score < 25: return "Faible"
        elif score < 50: return "Moyen"
        elif score < 75: return "Élevé"
        else: return "Critique"
        
    df_tx["niveau_risque"] = df_tx["score_risque"].apply(categoriser_risque)
    
    cols_finales = [
        "id_transaction", "date_transaction", "id_fournisseur", "montant", "type_depense", 
        "mode_paiement", "id_employe_initiateur", "id_employe_validateur", "statut_validation", 
        "numero_facture", "regle_rib_partage", "regle_montant_anormal", "regle_doublon_facture", 
        "regle_creation_tardive", "prediction_ml", "fournisseur_suspect_collusion", 
        "employe_suspect_collusion", "score_risque", "niveau_risque"
    ]
    
    cols_finales = [c for c in cols_finales if c in df_tx.columns]
    
    df_final = df_tx[cols_finales].copy()
    if 'date_transaction' in df_final.columns:
        df_final = df_final.sort_values('date_transaction').reset_index(drop=True)
        
    print("✅ Pipeline terminé avec succès !")
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
