import os
import sys
import numpy as np
import pandas as pd
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(BASE_DIR, "../../")
sys.path.append(ROOT_DIR)

compare_exact = importlib.import_module("scripts.06_validation.compare_exact")
load_data = compare_exact.load_data
clean = importlib.import_module("scripts.03_cleaning.clean")

# Hack detection_regles
def _factures_proches(fac_a, fac_b):
    if pd.isna(fac_a) or pd.isna(fac_b):
        return False
    seuil_diff_num = 2
    seuil_levenshtein = 2
    def extract_num(f):
        digits = ''.join(filter(str.isdigit, str(f)))
        return int(digits) if digits else None
    num_a = extract_num(fac_a)
    num_b = extract_num(fac_b)
    if num_a is not None and num_b is not None:
        return abs(num_a - num_b) <= seuil_diff_num
    def _levenshtein(s1, s2):
        if len(s1) < len(s2):
            return _levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]
    return _levenshtein(str(fac_a), str(fac_b)) <= seuil_levenshtein

def appliquer_regles_custom(transactions, fournisseurs, profil, 
                            mult_sigma=3.0, 
                            seuil_relatif_doublon=0.005, 
                            seuil_creation_jours=2, 
                            nb_tx_recentes_rib=3):
    transactions = transactions.copy()
    fournisseurs = fournisseurs.copy()
    
    for col in ["regle_rib_partage", "regle_montant_anormal", "regle_doublon_facture", "regle_creation_tardive"]:
        transactions[col] = False

    # 1. RIB PARTAGE
    if "rib_iban_normalise" in fournisseurs.columns:
        col_rib = "rib_iban_normalise"
    else:
        fournisseurs["rib_iban_normalise"] = fournisseurs["rib_iban"].astype(str).str.replace(r"\s+", "", regex=True)
        col_rib = "rib_iban_normalise"
    frs_actifs = fournisseurs[fournisseurs["statut_fournisseur"] == "Actif"].copy()
    rib_counts = frs_actifs.groupby(col_rib)["id_fournisseur"].nunique().reset_index(name="nb_fournisseurs")
    rib_partages = rib_counts[rib_counts["nb_fournisseurs"] >= 2][col_rib].tolist()
    frs_rib_partage = frs_actifs[frs_actifs[col_rib].isin(rib_partages)]["id_fournisseur"].unique()
    fournisseurs["fournisseur_a_risque"] = fournisseurs["id_fournisseur"].isin(frs_rib_partage)
    
    tx_frs_risque = transactions[transactions["id_fournisseur"].isin(frs_rib_partage)].copy()
    if not tx_frs_risque.empty:
        idx_top3 = tx_frs_risque.sort_values(["id_fournisseur", "date_transaction"], ascending=[True, False]).groupby("id_fournisseur").head(nb_tx_recentes_rib).index
        transactions.loc[idx_top3, "regle_rib_partage"] = True

    # 2. MONTANT ANORMAL
    tx_profil = transactions.merge(profil[["id_fournisseur", "montant_moyen", "montant_ecart_type"]], on="id_fournisseur", how="left")
    tx_profil["seuil_montant"] = tx_profil["montant_moyen"] + mult_sigma * tx_profil["montant_ecart_type"]
    mask_montant = tx_profil["montant"].notna() & tx_profil["seuil_montant"].notna() & (tx_profil["montant"] > tx_profil["seuil_montant"])
    transactions.loc[mask_montant, "regle_montant_anormal"] = True

    # 3. DOUBLONS
    SEUIL_MONTANT_FIXE = 3.0
    SEUIL_JOURS = 7
    seuils_frs = profil[["id_fournisseur", "montant_moyen"]].copy()
    seuils_frs["seuil_doublon"] = np.minimum(SEUIL_MONTANT_FIXE, seuil_relatif_doublon * seuils_frs["montant_moyen"])
    seuil_map = seuils_frs.set_index("id_fournisseur")["seuil_doublon"].to_dict()

    doublons_idx = set()
    for frs_id, grp in transactions.groupby("id_fournisseur"):
        if len(grp) < 2: continue
        seuil_mt = seuil_map.get(frs_id, SEUIL_MONTANT_FIXE)
        montants, dates, factures, indices = grp["montant"].values, grp["date_transaction"].values, grp["numero_facture"].values, grp.index.values
        n = len(grp)
        for i in range(n):
            ecart_montant = np.abs(montants[i] - montants[i + 1 :])
            ecart_jours = np.abs((dates[i] - dates[i + 1 :]) / np.timedelta64(1, "D"))
            mask_mt_dt = (ecart_montant <= seuil_mt) & (ecart_jours <= SEUIL_JOURS)
            if not mask_mt_dt.any(): continue
            candidats = np.where(mask_mt_dt)[0]
            for j_offset in candidats:
                j = i + 1 + j_offset
                if _factures_proches(factures[i], factures[j]):
                    doublons_idx.add(indices[i])
                    doublons_idx.add(indices[j])
    transactions.loc[list(doublons_idx), "regle_doublon_facture"] = True

    # 4. CREATION TARDIVE
    tx_frs = transactions.merge(fournisseurs[["id_fournisseur", "date_creation_fournisseur"]], on="id_fournisseur", how="left")
    ecart_creation = (tx_frs["date_transaction"] - tx_frs["date_creation_fournisseur"]).dt.days
    mask_creation = ecart_creation.notna() & (ecart_creation >= 0) & (ecart_creation <= seuil_creation_jours)
    transactions.loc[mask_creation.values, "regle_creation_tardive"] = True

    colonnes_regles = ["regle_rib_partage", "regle_montant_anormal", "regle_doublon_facture", "regle_creation_tardive"]
    transactions["score_risque"] = transactions[colonnes_regles].sum(axis=1).astype(int)
    
    # We add dummy prediction_ml and collusion to avoid KeyError in evaluate_exact
    transactions["prediction_ml"] = 0
    transactions["fournisseur_suspect_collusion"] = "non"
    transactions["employe_suspect_collusion"] = "non"
    
    return transactions

# Load clean data
df_tx_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/transactions.csv"), parse_dates=["date_transaction"])
df_frs_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/fournisseurs.csv"), parse_dates=["date_creation_fournisseur"])
df_emp_raw = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/employes.csv"))
df_tx, df_frs, df_emp, profil = clean.nettoyer_donnees(df_tx_raw, df_frs_raw, df_emp_raw)
j = pd.read_csv(os.path.join(ROOT_DIR, "data/raw/journal_fraudes_injectees.csv"))

# Define tests
tests = {
    "Montant anormal": [
        ("Seuil bas (2,5σ)", {"mult_sigma": 2.5}),
        ("Seuil actuel (3σ)", {"mult_sigma": 3.0}),
        ("Seuil haut (3,5σ)", {"mult_sigma": 3.5}),
    ],
    "Doublon facture": [
        ("Seuil bas (0,3%)", {"seuil_relatif_doublon": 0.003}),
        ("Seuil actuel (0,5%)", {"seuil_relatif_doublon": 0.005}),
        ("Seuil haut (0,7%)", {"seuil_relatif_doublon": 0.007}),
    ],
    "Création tardive": [
        ("Seuil bas (1 jour)", {"seuil_creation_jours": 1}),
        ("Seuil actuel (2 jours)", {"seuil_creation_jours": 2}),
        ("Seuil haut (4 jours)", {"seuil_creation_jours": 4}),
    ],
    "RIB partagé": [
        ("Seuil bas (1 tx)", {"nb_tx_recentes_rib": 1}),
        ("Seuil actuel (3 tx)", {"nb_tx_recentes_rib": 3}),
        ("Seuil haut (5 tx)", {"nb_tx_recentes_rib": 5}),
    ]
}

results = {}

for regle, variations in tests.items():
    print(f"\n=== REGLE : {regle} ===")
    results[regle] = []
    for var_name, kwargs in variations:
        df_scored = appliquer_regles_custom(df_tx, df_frs, profil, **kwargs)
        metrics = compare_exact.evaluate_exact(j, df_scored)
        
        num, den = metrics["regles"]["global"]
        tx_regles = df_scored[df_scored["score_risque"] >= 1]["id_transaction"].unique()
        total_alertes = len(tx_regles)
        
        rappel = (num / den * 100) if den else 0
        precision = (num / total_alertes * 100) if total_alertes else 0
        
        results[regle].append(f"{num}/{den} ({rappel:.1f}%) | {num}/{total_alertes} ({precision:.1f}%)")
        print(f"[{var_name}] Rappel: {num}/{den} ({rappel:.1f}%) | Precision: {num}/{total_alertes} ({precision:.1f}%)")

# Print markdown table
print("\n\n--- MARKDOWN TABLE ---")
for regle, res_list in results.items():
    print(f"| {regle} | {res_list[0]} | {res_list[1]} | {res_list[2]} |")
