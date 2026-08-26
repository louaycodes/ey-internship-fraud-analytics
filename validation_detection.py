"""
validation_detection.py — Croisement résultats détection × journal de fraudes injectées
========================================================================================
Calcule le taux de détection (rappel) et le taux de faux positifs par règle.
"""

import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "output_clean")
JOURNAL_PATH = os.path.join(BASE_DIR, "..", "output_tunidistrib", "journal_fraudes_injectees.csv")

# ── Chargement ──────────────────────────────────────────────────────
scorees = pd.read_csv(
    os.path.join(INPUT_DIR, "transactions_scorees.csv"),
    parse_dates=["date_transaction"],
)
journal = pd.read_csv(JOURNAL_PATH)

print("=" * 70)
print("  VALIDATION : DÉTECTION vs JOURNAL DE FRAUDES INJECTÉES")
print("=" * 70)
print(f"\n  Transactions scorées : {len(scorees):,}")
print(f"  Cas de fraude injectés : {len(journal)}")

# ── Mapping type_fraude → colonne de règle ──────────────────────────
MAPPING_REGLES = {
    "RIB partagé":                                "regle_rib_partage",
    "Montant anormal":                            "regle_montant_anormal",
    "Doublon de facture":                         "regle_doublon_facture",
    "Création fournisseur juste avant paiement":  "regle_creation_tardive",
}

# ── Extraire les références du journal par type ─────────────────────
# RIB partagé : référence = "FRS-XXX/FRS-YYY" → on extrait les 2 id_fournisseur
# Création tardive : référence = "FRS-XXX" → id_fournisseur
# Montant anormal / Doublon : référence = "TX-XXX" → id_transaction

resultats = {}

for type_fraude, col_regle in MAPPING_REGLES.items():
    cas = journal[journal["type_fraude"] == type_fraude].copy()
    nb_injectes = len(cas)

    if nb_injectes == 0:
        resultats[type_fraude] = {
            "injectes": 0, "detectes": 0, "taux_detection": 0,
            "flagués_total": 0, "vrais_positifs": 0, "faux_positifs": 0,
            "taux_faux_positifs": 0,
        }
        continue

    if type_fraude == "RIB partagé":
        # Extraire toutes les paires FRS → ensemble de fournisseurs frauduleux
        frs_frauduleux = set()
        for ref in cas["reference"]:
            parts = str(ref).split("/")
            frs_frauduleux.update(parts)

        # Détection : le fournisseur a-t-il au moins 1 transaction flaguée ?
        frs_detectes = set(
            scorees[
                scorees["id_fournisseur"].isin(frs_frauduleux)
                & (scorees[col_regle] == True)
            ]["id_fournisseur"].unique()
        )
        # On compte par paire de fournisseurs (= cas du journal)
        nb_detectes = 0
        for ref in cas["reference"]:
            parts = str(ref).split("/")
            if any(f in frs_detectes for f in parts):
                nb_detectes += 1

        # Faux positifs : fournisseurs flaguées qui ne sont PAS dans le journal
        frs_flagués = set(
            scorees[scorees[col_regle] == True]["id_fournisseur"].unique()
        )
        frs_faux_positifs = frs_flagués - frs_frauduleux
        tx_flagués_total = int(scorees[col_regle].sum())
        tx_vrais_positifs = int(
            scorees[
                scorees["id_fournisseur"].isin(frs_frauduleux)
                & (scorees[col_regle] == True)
            ].shape[0]
        )
        tx_faux_positifs = tx_flagués_total - tx_vrais_positifs

        resultats[type_fraude] = {
            "injectes": nb_injectes,
            "detectes": nb_detectes,
            "taux_detection": nb_detectes / nb_injectes * 100 if nb_injectes else 0,
            "flagués_total": tx_flagués_total,
            "vrais_positifs": tx_vrais_positifs,
            "faux_positifs": tx_faux_positifs,
            "taux_faux_positifs": tx_faux_positifs / tx_flagués_total * 100 if tx_flagués_total else 0,
            "detail": f"{len(frs_frauduleux)} FRS injectés, {len(frs_detectes)} détectés, "
                      f"{len(frs_faux_positifs)} FRS faux positifs",
        }

    elif type_fraude == "Création fournisseur juste avant paiement":
        # Référence = FRS-XXX → vérifier que les transactions de ce fournisseur
        # sont flaguées regle_creation_tardive
        frs_frauduleux = set(cas["reference"].astype(str))

        frs_detectes = set()
        for frs_id in frs_frauduleux:
            tx_frs = scorees[
                (scorees["id_fournisseur"] == frs_id)
                & (scorees[col_regle] == True)
            ]
            if len(tx_frs) > 0:
                frs_detectes.add(frs_id)

        nb_detectes = len(frs_detectes)

        # Faux positifs : fournisseurs flaguées pas dans le journal
        frs_flagués = set(
            scorees[scorees[col_regle] == True]["id_fournisseur"].unique()
        )
        frs_faux_positifs = frs_flagués - frs_frauduleux
        tx_flagués_total = int(scorees[col_regle].sum())
        tx_vrais_positifs = int(
            scorees[
                scorees["id_fournisseur"].isin(frs_frauduleux)
                & (scorees[col_regle] == True)
            ].shape[0]
        )
        tx_faux_positifs = tx_flagués_total - tx_vrais_positifs

        resultats[type_fraude] = {
            "injectes": nb_injectes,
            "detectes": nb_detectes,
            "taux_detection": nb_detectes / nb_injectes * 100 if nb_injectes else 0,
            "flagués_total": tx_flagués_total,
            "vrais_positifs": tx_vrais_positifs,
            "faux_positifs": tx_faux_positifs,
            "taux_faux_positifs": tx_faux_positifs / tx_flagués_total * 100 if tx_flagués_total else 0,
        }

    else:
        # Montant anormal / Doublon : référence = TX-XXX
        tx_frauduleuses = set(cas["reference"].astype(str))

        # Transactions détectées
        tx_detectees = set(
            scorees[
                scorees["id_transaction"].isin(tx_frauduleuses)
                & (scorees[col_regle] == True)
            ]["id_transaction"]
        )
        nb_detectes = len(tx_detectees)
        tx_non_detectees = tx_frauduleuses - tx_detectees

        # Faux positifs
        tx_flagués_total = int(scorees[col_regle].sum())
        tx_faux_positifs = tx_flagués_total - nb_detectes

        resultats[type_fraude] = {
            "injectes": nb_injectes,
            "detectes": nb_detectes,
            "taux_detection": nb_detectes / nb_injectes * 100 if nb_injectes else 0,
            "flagués_total": tx_flagués_total,
            "vrais_positifs": nb_detectes,
            "faux_positifs": tx_faux_positifs,
            "taux_faux_positifs": tx_faux_positifs / tx_flagués_total * 100 if tx_flagués_total else 0,
            "non_detectees": tx_non_detectees if tx_non_detectees else None,
        }

# ── Affichage ───────────────────────────────────────────────────────
print("\n" + "─" * 70)

total_injectes = 0
total_detectes = 0
total_flagués = 0
total_fp = 0

for type_fraude, r in resultats.items():
    print(f"\n  📋 {type_fraude}")
    print(f"     Cas injectés       : {r['injectes']}")
    print(f"     Cas détectés       : {r['detectes']}")
    print(f"     Taux de détection  : {r['taux_detection']:.1f}%")
    print(f"     Tx flaguées total  : {r['flagués_total']:,}")
    print(f"     Vrais positifs     : {r['vrais_positifs']:,}")
    print(f"     Faux positifs      : {r['faux_positifs']:,}")
    print(f"     Taux faux positifs : {r['taux_faux_positifs']:.1f}%")
    if "detail" in r:
        print(f"     Détail             : {r['detail']}")
    if r.get("non_detectees"):
        print(f"     ⚠ Non détectées    : {r['non_detectees']}")

    total_injectes += r["injectes"]
    total_detectes += r["detectes"]
    total_flagués += r["flagués_total"]
    total_fp += r["faux_positifs"]

print("\n" + "─" * 70)
print("  BILAN GLOBAL")
print("─" * 70)
print(f"  Cas injectés total        : {total_injectes}")
print(f"  Cas détectés total        : {total_detectes}")
print(f"  Taux de détection global  : {total_detectes / total_injectes * 100:.1f}%")
print(f"  Tx flaguées total         : {total_flagués:,}")
print(f"  Faux positifs total       : {total_fp:,}")
print(f"  Taux faux positifs global : {total_fp / total_flagués * 100:.1f}%")
print("=" * 70)
