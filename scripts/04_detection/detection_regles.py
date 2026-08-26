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
    - transactions_scorees.csv   (toutes les transactions + colonnes de scoring)
    - alertes_prioritaires.csv   (risque Moyen / Élevé, tri décroissant)
    - fournisseurs_clean.csv     (enrichi avec colonne fournisseur_a_risque)
"""

import os
import pandas as pd
import numpy as np
from itertools import combinations

# ── Chemins ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "../../data/clean")
OUTPUT_DIR = INPUT_DIR  # exports dans le même dossier

# =====================================================================
# 1. CHARGEMENT DES DONNÉES
# =====================================================================
print("=" * 60)
print("  DÉTECTION DE FRAUDE FOURNISSEURS — TuniDistrib SA")
print("=" * 60)

print("\n📂 Chargement des données nettoyées...")

transactions = pd.read_csv(
    os.path.join(INPUT_DIR, "transactions_clean.csv"),
    parse_dates=["date_transaction"],
)
fournisseurs = pd.read_csv(
    os.path.join(INPUT_DIR, "fournisseurs_clean.csv"),
    parse_dates=["date_creation_fournisseur"],
)
employes = pd.read_csv(os.path.join(INPUT_DIR, "employes_clean.csv"))
profil = pd.read_csv(os.path.join(INPUT_DIR, "profil_montant_fournisseur.csv"))

print(f"   • Transactions  : {len(transactions):>7,} lignes")
print(f"   • Fournisseurs  : {len(fournisseurs):>7,} lignes")
print(f"   • Employés      : {len(employes):>7,} lignes")
print(f"   • Profils montant: {len(profil):>7,} lignes")

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

# Utiliser la colonne rib_iban_normalise déjà présente (nettoyage amont)
# Sinon, normaliser rib_iban en supprimant les espaces
if "rib_iban_normalise" in fournisseurs.columns:
    col_rib = "rib_iban_normalise"
else:
    fournisseurs["rib_iban_normalise"] = (
        fournisseurs["rib_iban"].astype(str).str.replace(r"\s+", "", regex=True)
    )
    col_rib = "rib_iban_normalise"

# Filtrer les fournisseurs actifs uniquement
frs_actifs = fournisseurs[fournisseurs["statut_fournisseur"] == "Actif"].copy()

# Détecter les RIB portés par ≥ 2 fournisseurs actifs distincts
rib_counts = (
    frs_actifs.groupby(col_rib)["id_fournisseur"]
    .nunique()
    .reset_index(name="nb_fournisseurs")
)
rib_partages = rib_counts[rib_counts["nb_fournisseurs"] >= 2][col_rib].tolist()

# Identifier les fournisseurs concernés
frs_rib_partage = frs_actifs[frs_actifs[col_rib].isin(rib_partages)][
    "id_fournisseur"
].unique()

# ── Enrichir fournisseurs avec colonne fournisseur_a_risque ──────────
fournisseurs["fournisseur_a_risque"] = fournisseurs["id_fournisseur"].isin(
    frs_rib_partage
)

# ── Au niveau transaction : ne flaguer que les 3 plus récentes ───────
# Pas de date de modification de RIB disponible → on prend les 3
# transactions les plus récentes par fournisseur à risque.
NB_TX_RECENTES_RIB = 3

tx_frs_risque = transactions[
    transactions["id_fournisseur"].isin(frs_rib_partage)
].copy()

if not tx_frs_risque.empty:
    idx_top3 = (
        tx_frs_risque
        .sort_values("date_transaction", ascending=False)
        .groupby("id_fournisseur")
        .head(NB_TX_RECENTES_RIB)
        .index
    )
    transactions.loc[idx_top3, "regle_rib_partage"] = True

nb_rib = transactions["regle_rib_partage"].sum()
nb_frs_risque = fournisseurs["fournisseur_a_risque"].sum()
print(f"   ✓ {len(rib_partages)} RIB partagé(s) détecté(s)")
print(f"     → {len(frs_rib_partage)} fournisseur(s) marqué(s) fournisseur_a_risque")
print(f"     → {nb_rib:,} transaction(s) marquée(s) (top {NB_TX_RECENTES_RIB} "
      f"récentes par fournisseur)")

# =====================================================================
# 3. RÈGLE 2 — MONTANT ANORMALEMENT ÉLEVÉ
# =====================================================================
print("\n🔍 Règle 2 : Montant anormal (> μ + 3σ par fournisseur)...")

# Joindre le profil statistique de chaque fournisseur
tx_profil = transactions.merge(
    profil[["id_fournisseur", "montant_moyen", "montant_ecart_type"]],
    on="id_fournisseur",
    how="left",
)

# Calculer le seuil spécifique à chaque fournisseur
tx_profil["seuil_montant"] = (
    tx_profil["montant_moyen"] + 3 * tx_profil["montant_ecart_type"]
)

# Flaguer les transactions dépassant le seuil de leur fournisseur
mask_montant = (
    tx_profil["montant"].notna()
    & tx_profil["seuil_montant"].notna()
    & (tx_profil["montant"] > tx_profil["seuil_montant"])
)
transactions.loc[mask_montant, "regle_montant_anormal"] = True

nb_montant = transactions["regle_montant_anormal"].sum()
print(f"   ✓ {nb_montant:,} transaction(s) avec montant anormalement élevé")

# =====================================================================
# 4. RÈGLE 3 — DOUBLON DE FACTURATION (seuil relatif)
# =====================================================================
print("\n🔍 Règle 3 : Doublons de facturation (même fournisseur, "
      "seuil relatif, dates ≤ 7 j, n° facture proche)...")

SEUIL_MONTANT_FIXE = 3.0       # plancher absolu en DT
SEUIL_MONTANT_RELATIF = 0.005  # 0.5 % du montant_moyen fournisseur
SEUIL_JOURS = 7                # écart de dates toléré

# Pré-calculer le seuil de montant par fournisseur : min(3 DT, 0.5% × μ)
#
# CHOIX DÉLIBÉRÉ — min() au lieu de max() :
# Un doublon de facturation est un écart absolu de quelques dinars (erreur
# de copier-coller, double saisie), pas un pourcentage du montant moyen.
# Pour un gros fournisseur (μ = 6 000 DT), max(3, 30) = 30 DT serait trop
# permissif et générerait des faux positifs massifs. min(3, 30) = 3 DT
# reste strict.  Pour un petit fournisseur (μ = 250 DT), min(3, 1.25) = 1.25 DT
# resserre le filet, car à ce niveau de montant, même 3 DT d'écart est
# significatif et peu suspect de doublon réel.
seuils_frs = profil[["id_fournisseur", "montant_moyen"]].copy()
seuils_frs["seuil_doublon"] = np.minimum(
    SEUIL_MONTANT_FIXE,
    SEUIL_MONTANT_RELATIF * seuils_frs["montant_moyen"],
)
seuil_map = seuils_frs.set_index("id_fournisseur")["seuil_doublon"].to_dict()

# ── Critère additionnel : proximité du numéro de facture ─────────────
# Un vrai doublon de facturation implique la saisie en double de la même
# facture, pas juste une coïncidence de montant.  On exige en plus :
#   • Différence numérique ≤ 2 sur le suffixe (FAC-NNNNN)
#   • OU distance de Levenshtein ≤ 1 (fallback pour formats non numériques)
SEUIL_DIFF_NUM_FACTURE = 2     # écart numérique toléré sur le n° facture
SEUIL_LEVENSHTEIN = 1          # distance de Levenshtein tolérée (fallback)

import re

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

def _factures_proches(fac_a: str, fac_b: str) -> bool:
    """Retourne True si deux numéros de facture sont proches."""
    num_a = _extraire_num_facture(fac_a)
    num_b = _extraire_num_facture(fac_b)
    if num_a is not None and num_b is not None:
        return abs(num_a - num_b) <= SEUIL_DIFF_NUM_FACTURE
    # Fallback : Levenshtein pour formats non standard
    return _levenshtein(str(fac_a), str(fac_b)) <= SEUIL_LEVENSHTEIN

doublons_idx = set()  # indices des transactions suspectes

# Traiter par fournisseur pour comparer les paires intra-fournisseur
for frs_id, grp in transactions.groupby("id_fournisseur"):
    if len(grp) < 2:
        continue

    # Seuil spécifique au fournisseur (fallback = plancher fixe)
    seuil_mt = seuil_map.get(frs_id, SEUIL_MONTANT_FIXE)

    montants = grp["montant"].values
    dates = grp["date_transaction"].values
    factures = grp["numero_facture"].values
    indices = grp.index.values

    n = len(grp)
    for i in range(n):
        ecart_montant = np.abs(montants[i] - montants[i + 1 :])
        ecart_jours = np.abs(
            (dates[i] - dates[i + 1 :]) / np.timedelta64(1, "D")
        )
        # Critères montant + date
        mask_mt_dt = (ecart_montant <= seuil_mt) & (ecart_jours <= SEUIL_JOURS)

        if not mask_mt_dt.any():
            continue

        # Critère additionnel : proximité du numéro de facture
        candidats = np.where(mask_mt_dt)[0]
        for j_offset in candidats:
            j = i + 1 + j_offset
            if _factures_proches(factures[i], factures[j]):
                doublons_idx.add(indices[i])
                doublons_idx.add(indices[j])

transactions.loc[list(doublons_idx), "regle_doublon_facture"] = True

nb_doublons = transactions["regle_doublon_facture"].sum()
taux_nouveau = nb_doublons / len(transactions) * 100
taux_ancien = 7334 / 77699 * 100  # valeur de la version précédente
print(f"   ✓ {nb_doublons:,} transaction(s) suspectes de doublon")
print(f"     Taux ancien (seuil fixe 3 DT)    : {taux_ancien:.1f}% (7 334 tx)")
print(f"     Taux nouveau (seuil relatif)      : {taux_nouveau:.1f}% ({nb_doublons:,} tx)")
print(f"     Réduction                         : "
      f"{(1 - nb_doublons / 7334) * 100:+.1f}%")

# =====================================================================
# 5. RÈGLE 4 — CRÉATION TARDIVE DU FOURNISSEUR
# =====================================================================
print("\n🔍 Règle 4 : Création tardive (transaction ≤ 2 jours après "
      "création du fournisseur)...")

SEUIL_CREATION_JOURS = 2

# Joindre la date de création du fournisseur
tx_frs = transactions.merge(
    fournisseurs[["id_fournisseur", "date_creation_fournisseur"]],
    on="id_fournisseur",
    how="left",
)

# Calculer l'écart en jours entre la transaction et la création
ecart_creation = (
    tx_frs["date_transaction"] - tx_frs["date_creation_fournisseur"]
).dt.days

# La transaction doit être APRÈS la création (écart ≥ 0) et ≤ seuil
mask_creation = ecart_creation.notna() & (ecart_creation >= 0) & (
    ecart_creation <= SEUIL_CREATION_JOURS
)
transactions.loc[mask_creation.values, "regle_creation_tardive"] = True

nb_creation = transactions["regle_creation_tardive"].sum()
print(f"   ✓ {nb_creation:,} transaction(s) proches de la création fournisseur")

# =====================================================================
# 6. SCORING GLOBAL
# =====================================================================
print("\n📊 Calcul du score de risque global...")

colonnes_regles = [
    "regle_rib_partage",
    "regle_montant_anormal",
    "regle_doublon_facture",
    "regle_creation_tardive",
]

# Score = nombre de règles déclenchées (0 à 4)
transactions["score_risque"] = transactions[colonnes_regles].sum(axis=1).astype(int)

# Niveau de risque
def niveau_risque(score: int) -> str:
    if score <= 1:
        return "Faible"
    elif score == 2:
        return "Moyen"
    else:
        return "Élevé"

transactions["niveau_risque"] = transactions["score_risque"].apply(niveau_risque)

# ── Résumé ───────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("  RÉSUMÉ DU SCORING")
print("─" * 60)
repartition = transactions["niveau_risque"].value_counts()
for niveau in ["Faible", "Moyen", "Élevé"]:
    count = repartition.get(niveau, 0)
    pct = count / len(transactions) * 100
    print(f"   {niveau:<8} : {count:>7,} transactions ({pct:5.1f}%)")

print(f"\n   Score moyen     : {transactions['score_risque'].mean():.2f}")
print(f"   Score max       : {transactions['score_risque'].max()}")

# Détail par règle
print("\n  Détail par règle :")
for col in colonnes_regles:
    nom = col.replace("regle_", "").replace("_", " ").capitalize()
    count = transactions[col].sum()
    print(f"   • {nom:<22} : {count:>7,} transactions")

# =====================================================================
# 7. EXPORTS
# =====================================================================
print("\n💾 Export des résultats...")

# 7a. Toutes les transactions scorées
path_scorees = os.path.join(OUTPUT_DIR, "transactions_scorees.csv")
transactions.to_csv(path_scorees, index=False)
print(f"   ✓ transactions_scorees.csv     ({len(transactions):,} lignes)")

# 7b. Alertes prioritaires (Moyen / Élevé), triées par score décroissant
alertes = (
    transactions[transactions["niveau_risque"].isin(["Moyen", "Élevé"])]
    .sort_values("score_risque", ascending=False)
    .reset_index(drop=True)
)
path_alertes = os.path.join(OUTPUT_DIR, "alertes_prioritaires.csv")
alertes.to_csv(path_alertes, index=False)
print(f"   ✓ alertes_prioritaires.csv     ({len(alertes):,} lignes)")

# 7c. Fournisseurs enrichis avec colonne fournisseur_a_risque
path_frs = os.path.join(OUTPUT_DIR, "fournisseurs_clean.csv")
fournisseurs.to_csv(path_frs, index=False)
print(f"   ✓ fournisseurs_clean.csv       ({len(fournisseurs):,} lignes, "
      f"enrichi avec fournisseur_a_risque)")

print("\n" + "=" * 60)
print("  ✅ Détection terminée avec succès !")
print("=" * 60)
