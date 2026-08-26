# -*- coding: utf-8 -*-
"""
=========================================================================
NETTOYAGE ET NORMALISATION — TuniDistrib SA
=========================================================================
Étape 2 de la méthodologie : avant de coder les règles de détection,
on normalise les champs sensibles à la comparaison (RIB, noms fournisseurs)
pour que les règles fonctionnent correctement sur des données réelles.

Ce script :
  1. Normalise les RIB (suppression espaces, majuscules)
  2. Détecte les noms de fournisseurs proches (doublons potentiels) via
     difflib (bibliothèque standard Python, aucune installation requise)
  3. Vérifie les types (dates, montants) et les uniformise
  4. Exporte des fichiers "propres", prêts pour les règles de détection

USAGE :
    python3 clean_data.py

Placer ce script dans le même dossier que :
    transactions.csv, fournisseurs.csv, employes.csv

Sorties générées dans ./output_clean/ :
    transactions_clean.csv
    fournisseurs_clean.csv
    employes_clean.csv
    doublons_fournisseurs_suspects.csv   (à vérifier manuellement)
=========================================================================
"""

import os
import re
import pandas as pd
from difflib import SequenceMatcher

INPUT_DIR = "../../data/raw"          # dossier contenant les CSV bruts
OUTPUT_DIR = "../../data/clean"
SEUIL_SIMILARITE_NOMS = 0.85   # 0 à 1 ; au-dessus = considéré comme doublon potentiel

os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg):
    print(msg)

# =========================================================================
# 1. CHARGEMENT
# =========================================================================
log("=" * 70)
log("1. CHARGEMENT")
log("=" * 70)

df_t = pd.read_csv(os.path.join(INPUT_DIR, "transactions.csv"), encoding="utf-8-sig")
df_f = pd.read_csv(os.path.join(INPUT_DIR, "fournisseurs.csv"), encoding="utf-8-sig")
df_e = pd.read_csv(os.path.join(INPUT_DIR, "employes.csv"), encoding="utf-8-sig")

log(f"Transactions : {len(df_t):,} lignes")
log(f"Fournisseurs : {len(df_f):,} lignes")
log(f"Employés     : {len(df_e):,} lignes")

# =========================================================================
# 2. NORMALISATION DES RIB
# =========================================================================
log("\n" + "=" * 70)
log("2. NORMALISATION DES RIB")
log("=" * 70)

def normaliser_rib(rib):
    """Supprime les espaces, tirets, et met en majuscules. Un même RIB
    saisi sous des formats différents doit donner la même chaîne normalisée."""
    if pd.isna(rib):
        return rib
    return re.sub(r"[\s\-]", "", str(rib)).upper()

n_avant = df_f["rib_iban"].nunique()
df_f["rib_iban_normalise"] = df_f["rib_iban"].apply(normaliser_rib)
n_apres = df_f["rib_iban_normalise"].nunique()

log(f"RIB uniques avant normalisation : {n_avant}")
log(f"RIB uniques après normalisation : {n_apres}")
if n_avant != n_apres:
    log(f"-> {n_avant - n_apres} RIB fusionnés (étaient identiques mais mal formatés différemment).")
else:
    log("-> Aucun impact : les RIB étaient déjà dans un format cohérent.")

# =========================================================================
# 3. DÉTECTION DE NOMS DE FOURNISSEURS PROCHES (fuzzy matching, difflib)
# =========================================================================
log("\n" + "=" * 70)
log("3. DÉTECTION DE DOUBLONS DE NOMS FOURNISSEURS (fuzzy matching)")
log("=" * 70)

def normaliser_nom_basique(nom):
    """Nettoyage léger avant comparaison : minuscules, suppression des
    suffixes juridiques courants et de la ponctuation, espaces multiples."""
    nom = str(nom).lower()
    nom = re.sub(r"\b(sarl|sa|ste|sté)\b", "", nom)
    nom = re.sub(r"[^\w\s]", "", nom)
    nom = re.sub(r"\s+", " ", nom).strip()
    return nom

df_f["nom_normalise"] = df_f["nom_fournisseur"].apply(normaliser_nom_basique)

noms = df_f[["id_fournisseur", "nom_fournisseur", "nom_normalise"]].values.tolist()
paires_suspectes = []

for i in range(len(noms)):
    for j in range(i + 1, len(noms)):
        id1, nom_orig1, nom_norm1 = noms[i]
        id2, nom_orig2, nom_norm2 = noms[j]
        if nom_norm1 == "" or nom_norm2 == "":
            continue
        score = SequenceMatcher(None, nom_norm1, nom_norm2).ratio()
        if score >= SEUIL_SIMILARITE_NOMS and nom_norm1 != nom_norm2:
            paires_suspectes.append({
                "id_fournisseur_1": id1, "nom_1": nom_orig1,
                "id_fournisseur_2": id2, "nom_2": nom_orig2,
                "score_similarite": round(score, 3),
            })
        elif nom_norm1 == nom_norm2:
            # Identiques après normalisation légère (ex: "Electro Plus" vs "ELECTRO PLUS SARL")
            paires_suspectes.append({
                "id_fournisseur_1": id1, "nom_1": nom_orig1,
                "id_fournisseur_2": id2, "nom_2": nom_orig2,
                "score_similarite": 1.0,
            })

df_doublons_noms = pd.DataFrame(paires_suspectes).sort_values("score_similarite", ascending=False) \
    if paires_suspectes else pd.DataFrame(columns=["id_fournisseur_1","nom_1","id_fournisseur_2","nom_2","score_similarite"])

log(f"Seuil de similarité utilisé : {SEUIL_SIMILARITE_NOMS}")
log(f"Paires de fournisseurs potentiellement dupliqués trouvées : {len(df_doublons_noms)}")
if len(df_doublons_noms) > 0:
    log(df_doublons_noms.to_string(index=False))
    log("\n/!\\ Ces paires sont À VÉRIFIER MANUELLEMENT avant fusion — le fuzzy")
    log("    matching peut avoir des faux positifs (ex: deux vraies entreprises")
    log("    avec des noms proches par coïncidence).")
else:
    log("Aucun doublon de nom détecté à ce seuil. (Normal si le jeu de données")
    log("généré n'a pas volontairement introduit de variantes de noms.)")

df_doublons_noms.to_csv(os.path.join(OUTPUT_DIR, "doublons_fournisseurs_suspects.csv"), index=False)

# =========================================================================
# 4. VÉRIFICATION ET UNIFORMISATION DES TYPES
# =========================================================================
log("\n" + "=" * 70)
log("4. VÉRIFICATION ET UNIFORMISATION DES TYPES")
log("=" * 70)

df_t["date_transaction"] = pd.to_datetime(df_t["date_transaction"], errors="coerce")
df_f["date_creation_fournisseur"] = pd.to_datetime(df_f["date_creation_fournisseur"], errors="coerce")
df_e["date_embauche"] = pd.to_datetime(df_e["date_embauche"], errors="coerce")
df_t["montant"] = pd.to_numeric(df_t["montant"], errors="coerce")

n_dates_invalides = df_t["date_transaction"].isna().sum()
n_montants_invalides = df_t["montant"].isna().sum()
log(f"Dates de transaction non convertibles : {n_dates_invalides}")
log(f"Montants non convertibles             : {n_montants_invalides}")

if n_dates_invalides > 0 or n_montants_invalides > 0:
    avant = len(df_t)
    df_t = df_t.dropna(subset=["date_transaction", "montant"])
    log(f"-> {avant - len(df_t)} lignes supprimées (données non exploitables).")
else:
    log("-> Aucune ligne supprimée, tout est déjà propre.")

# Suppression des espaces superflus dans les champs texte (saisie manuelle)
for col in ["nom_fournisseur", "adresse", "email_contact"]:
    if col in df_f.columns:
        df_f[col] = df_f[col].astype(str).str.strip()

# =========================================================================
# 5. PROFIL STATISTIQUE PAR FOURNISSEUR (utile pour les règles à venir)
# =========================================================================
log("\n" + "=" * 70)
log("5. CALCUL DU PROFIL DE MONTANT HABITUEL PAR FOURNISSEUR")
log("=" * 70)
log("(Ce profil servira de base aux règles de détection : un seuil PAR")
log(" fournisseur plutôt qu'un seuil global, comme discuté précédemment.)")

profil_fournisseur = df_t.groupby("id_fournisseur")["montant"].agg(
    montant_moyen="mean", montant_ecart_type="std", nb_transactions="count"
).reset_index()
profil_fournisseur["montant_ecart_type"] = profil_fournisseur["montant_ecart_type"].fillna(0)

log(f"Profils calculés pour {len(profil_fournisseur)} fournisseurs.")
log(profil_fournisseur.describe().to_string())

# =========================================================================
# 6. EXPORT DES FICHIERS PROPRES
# =========================================================================
log("\n" + "=" * 70)
log("6. EXPORT")
log("=" * 70)

df_t.to_csv(os.path.join(OUTPUT_DIR, "transactions_clean.csv"), index=False)
df_f.to_csv(os.path.join(OUTPUT_DIR, "fournisseurs_clean.csv"), index=False)
df_e.to_csv(os.path.join(OUTPUT_DIR, "employes_clean.csv"), index=False)
profil_fournisseur.to_csv(os.path.join(OUTPUT_DIR, "profil_montant_fournisseur.csv"), index=False)

log(f"Fichiers exportés dans : {OUTPUT_DIR}/")
log("  - transactions_clean.csv")
log("  - fournisseurs_clean.csv")
log("  - employes_clean.csv")
log("  - profil_montant_fournisseur.csv   (moyenne/écart-type par fournisseur)")
log("  - doublons_fournisseurs_suspects.csv   (à vérifier manuellement)")
log("\nPrêt pour l'étape suivante : les règles de détection (Niveau 1).")