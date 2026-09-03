"""
====================================================================
detection_regles.py  –  Détection de fraude fournisseurs (règles métier)
====================================================================
Client fictif : TuniDistrib SA  |  Stage EY – Département AI & Data
--------------------------------------------------------------------
Applique 4 règles de détection de fraude sur les données nettoyées :
    1. RIB partagé entre fournisseurs actifs distincts
       → flag fournisseur_a_risque + seules les 3 transactions les plus
         récentes par fournisseur concerné sont marquées
    2. Montant anormalement élevé (> μ + 3σ par fournisseur)
    3. Doublon de facturation (même fournisseur, seuil relatif
       min(3 DT, 0.5% × montant_moyen), date ≤ 7 j)
    4. Création tardive (transaction ≤ 2 jours après création du fournisseur)

Exports :
    - transactions_scorees_regles.csv (toutes les transactions + colonnes de scoring)
    - alertes_prioritaires.csv   (risque Moyen / Élevé, tri décroissant)
    - fournisseurs_clean.csv     (enrichi avec colonne fournisseur_a_risque)
"""

import os
import pandas as pd
import numpy as np
import re

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")
OUTPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")

def _extraire_num_facture(numero: str):
    """Extrait la partie numérique d'un numéro FAC-NNNNN. Retourne int ou None."""
    m = re.match(r"^FAC-(\d+)$", str(numero))
    return int(m.group(1)) if m else None

def _levenshtein(s1: str, s2: str) -> int:
    """Distance de Levenshtein entre deux chaînes (implémentation DP simple)."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]

def _factures_proches(fac_a: str, fac_b: str, seuil_diff_num=2, seuil_levenshtein=1) -> bool:
    """Retourne True si deux numéros de facture sont proches."""
    num_a = _extraire_num_facture(fac_a)
    num_b = _extraire_num_facture(fac_b)
    if num_a is not None and num_b is not None:
        return abs(num_a - num_b) <= seuil_diff_num
    # Fallback : Levenshtein pour formats non standard
    return _levenshtein(str(fac_a), str(fac_b)) <= seuil_levenshtein

def appliquer_regles(transactions, fournisseurs, employes, profil):
    transactions = transactions.copy()
    fournisseurs = fournisseurs.copy()
    
    # ── Initialiser les colonnes de règles à False ───────────────────────
    for col in [
        "regle_rib_partage",
        "regle_montant_anormal",
        "regle_doublon_facture",
        "regle_creation_tardive",
    ]:
        transactions[col] = False

    # =====================================================================
    # 2. RÈGLE 1 — RIB PARTAGÉ
    # =====================================================================
    print("\n🔍 Règle 1 : RIB partagé entre fournisseurs actifs...")
    if "rib_iban_normalise" in fournisseurs.columns:
        col_rib = "rib_iban_normalise"
    else:
        fournisseurs["rib_iban_normalise"] = (
            fournisseurs["rib_iban"].astype(str).str.replace(r"\s+", "", regex=True)
        )
        col_rib = "rib_iban_normalise"

    frs_actifs = fournisseurs[fournisseurs["statut_fournisseur"] == "Actif"].copy()
    rib_counts = (
        frs_actifs.groupby(col_rib)["id_fournisseur"]
        .nunique()
        .reset_index(name="nb_fournisseurs")
    )
    rib_partages = rib_counts[rib_counts["nb_fournisseurs"] >= 2][col_rib].tolist()
    frs_rib_partage = frs_actifs[frs_actifs[col_rib].isin(rib_partages)]["id_fournisseur"].unique()
    
    fournisseurs["fournisseur_a_risque"] = fournisseurs["id_fournisseur"].isin(frs_rib_partage)
    
    NB_TX_RECENTES_RIB = 3
    tx_frs_risque = transactions[transactions["id_fournisseur"].isin(frs_rib_partage)].copy()
    
    # Ensure sorting for determinism
    if not tx_frs_risque.empty:
        idx_top3 = (
            tx_frs_risque
            .sort_values(["id_fournisseur", "date_transaction"], ascending=[True, False])
            .groupby("id_fournisseur")
            .head(NB_TX_RECENTES_RIB)
            .index
        )
        transactions.loc[idx_top3, "regle_rib_partage"] = True

    nb_rib = transactions["regle_rib_partage"].sum()
    print(f"   ✓ {len(rib_partages)} RIB partagé(s) détecté(s)")
    print(f"     → {len(frs_rib_partage)} fournisseur(s) marqué(s) fournisseur_a_risque")
    print(f"     → {nb_rib:,} transaction(s) marquée(s) (top {NB_TX_RECENTES_RIB} récentes)")

    # =====================================================================
    # 3. RÈGLE 2 — MONTANT ANORMALEMENT ÉLEVÉ
    # =====================================================================
    print("\n🔍 Règle 2 : Montant anormal (> μ + 3σ par fournisseur)...")
    tx_profil = transactions.merge(
        profil[["id_fournisseur", "montant_moyen", "montant_ecart_type"]],
        on="id_fournisseur",
        how="left",
    )
    tx_profil["seuil_montant"] = tx_profil["montant_moyen"] + 3 * tx_profil["montant_ecart_type"]
    
    mask_montant = (
        tx_profil["montant"].notna()
        & tx_profil["seuil_montant"].notna()
        & (tx_profil["montant"] > tx_profil["seuil_montant"])
    )
    transactions.loc[mask_montant, "regle_montant_anormal"] = True
    print(f"   ✓ {transactions['regle_montant_anormal'].sum():,} transaction(s) avec montant anormalement élevé")

    # =====================================================================
    # 4. RÈGLE 3 — DOUBLON DE FACTURATION (seuil relatif)
    # =====================================================================
    print("\n🔍 Règle 3 : Doublons de facturation...")
    SEUIL_MONTANT_FIXE = 3.0
    SEUIL_MONTANT_RELATIF = 0.005
    SEUIL_JOURS = 7
    
    seuils_frs = profil[["id_fournisseur", "montant_moyen"]].copy()
    seuils_frs["seuil_doublon"] = np.minimum(SEUIL_MONTANT_FIXE, SEUIL_MONTANT_RELATIF * seuils_frs["montant_moyen"])
    seuil_map = seuils_frs.set_index("id_fournisseur")["seuil_doublon"].to_dict()

    doublons_idx = set()
    for frs_id, grp in transactions.groupby("id_fournisseur"):
        if len(grp) < 2:
            continue
        seuil_mt = seuil_map.get(frs_id, SEUIL_MONTANT_FIXE)
        
        montants = grp["montant"].values
        dates = grp["date_transaction"].values
        factures = grp["numero_facture"].values
        indices = grp.index.values

        n = len(grp)
        for i in range(n):
            ecart_montant = np.abs(montants[i] - montants[i + 1 :])
            ecart_jours = np.abs((dates[i] - dates[i + 1 :]) / np.timedelta64(1, "D"))
            mask_mt_dt = (ecart_montant <= seuil_mt) & (ecart_jours <= SEUIL_JOURS)

            if not mask_mt_dt.any():
                continue

            candidats = np.where(mask_mt_dt)[0]
            for j_offset in candidats:
                j = i + 1 + j_offset
                if _factures_proches(factures[i], factures[j]):
                    doublons_idx.add(indices[i])
                    doublons_idx.add(indices[j])

    transactions.loc[list(doublons_idx), "regle_doublon_facture"] = True
    print(f"   ✓ {transactions['regle_doublon_facture'].sum():,} transaction(s) suspectes de doublon")

    # =====================================================================
    # 5. RÈGLE 4 — CRÉATION TARDIVE DU FOURNISSEUR
    # =====================================================================
    print("\n🔍 Règle 4 : Création tardive (≤ 2 jours)...")
    SEUIL_CREATION_JOURS = 2
    tx_frs = transactions.merge(fournisseurs[["id_fournisseur", "date_creation_fournisseur"]], on="id_fournisseur", how="left")
    ecart_creation = (tx_frs["date_transaction"] - tx_frs["date_creation_fournisseur"]).dt.days
    
    mask_creation = ecart_creation.notna() & (ecart_creation >= 0) & (ecart_creation <= SEUIL_CREATION_JOURS)
    transactions.loc[mask_creation.values, "regle_creation_tardive"] = True
    print(f"   ✓ {transactions['regle_creation_tardive'].sum():,} transaction(s) proches de la création fournisseur")

    # =====================================================================
    # 6. SCORING GLOBAL
    # =====================================================================
    colonnes_regles = ["regle_rib_partage", "regle_montant_anormal", "regle_doublon_facture", "regle_creation_tardive"]
    transactions["score_risque"] = transactions[colonnes_regles].sum(axis=1).astype(int)

    def niveau_risque(score: int) -> str:
        if score <= 1: return "Faible"
        elif score == 2: return "Moyen"
        else: return "Élevé"
        
    transactions["niveau_risque"] = transactions["score_risque"].apply(niveau_risque)
    
    alertes = (
        transactions[transactions["niveau_risque"].isin(["Moyen", "Élevé"])]
        .sort_values("score_risque", ascending=False)
        .reset_index(drop=True)
    )
    
    return transactions, fournisseurs, alertes

if __name__ == "__main__":
    print("=" * 60)
    print("  DÉTECTION DE FRAUDE FOURNISSEURS — TuniDistrib SA")
    print("=" * 60)
    print("\n📂 Chargement des données nettoyées...")

    transactions_raw = pd.read_csv(os.path.join(INPUT_DIR, "transactions_clean.csv"), parse_dates=["date_transaction"])
    fournisseurs_raw = pd.read_csv(os.path.join(INPUT_DIR, "fournisseurs_clean.csv"), parse_dates=["date_creation_fournisseur"])
    employes_raw = pd.read_csv(os.path.join(INPUT_DIR, "employes_clean.csv"))
    profil_raw = pd.read_csv(os.path.join(INPUT_DIR, "profil_montant_fournisseur.csv"))

    transactions, fournisseurs, alertes = appliquer_regles(transactions_raw, fournisseurs_raw, employes_raw, profil_raw)

    print("\n💾 Export des résultats...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    transactions.to_csv(os.path.join(OUTPUT_DIR, "transactions_scorees_regles.csv"), index=False)
    alertes.to_csv(os.path.join(OUTPUT_DIR, "alertes_prioritaires.csv"), index=False)
    fournisseurs.to_csv(os.path.join(OUTPUT_DIR, "fournisseurs_clean.csv"), index=False)

    print("\n" + "=" * 60)
    print("  ✅ Détection terminée avec succès !")
    print("=" * 60)
