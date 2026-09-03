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

def log(msg):
    print(msg)

def normaliser_rib(rib):
    """Supprime les espaces, tirets, et met en majuscules."""
    if pd.isna(rib):
        return rib
    return re.sub(r"[\s\-]", "", str(rib)).upper()

def normaliser_nom_basique(nom):
    """Nettoyage léger avant comparaison : minuscules, suppression des
    suffixes juridiques courants et de la ponctuation, espaces multiples."""
    nom = str(nom).lower()
    nom = re.sub(r"\b(sarl|sa|ste|sté)\b", "", nom)
    nom = re.sub(r"[^\w\s]", "", nom)
    nom = re.sub(r"\s+", " ", nom).strip()
    return nom

def nettoyer_donnees(df_t, df_f, df_e, output_dir=None, seuil_similarite_noms=0.85):
    """
    Nettoie et normalise les données brutes.
    Retourne : (df_t_clean, df_f_clean, df_e_clean, profil_fournisseur)
    """
    df_t = df_t.copy()
    df_f = df_f.copy()
    df_e = df_e.copy()

    log("=" * 70)
    log("2. NORMALISATION DES RIB")
    log("=" * 70)

    n_avant = df_f["rib_iban"].nunique()
    df_f["rib_iban_normalise"] = df_f["rib_iban"].apply(normaliser_rib)
    n_apres = df_f["rib_iban_normalise"].nunique()

    log(f"RIB uniques avant normalisation : {n_avant}")
    log(f"RIB uniques après normalisation : {n_apres}")

    log("\n" + "=" * 70)
    log("3. DÉTECTION DE DOUBLONS DE NOMS FOURNISSEURS (fuzzy matching)")
    log("=" * 70)

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
            if score >= seuil_similarite_noms and nom_norm1 != nom_norm2:
                paires_suspectes.append({
                    "id_fournisseur_1": id1, "nom_1": nom_orig1,
                    "id_fournisseur_2": id2, "nom_2": nom_orig2,
                    "score_similarite": round(score, 3),
                })
            elif nom_norm1 == nom_norm2:
                paires_suspectes.append({
                    "id_fournisseur_1": id1, "nom_1": nom_orig1,
                    "id_fournisseur_2": id2, "nom_2": nom_orig2,
                    "score_similarite": 1.0,
                })

    df_doublons_noms = pd.DataFrame(paires_suspectes).sort_values("score_similarite", ascending=False) \
        if paires_suspectes else pd.DataFrame(columns=["id_fournisseur_1","nom_1","id_fournisseur_2","nom_2","score_similarite"])

    if output_dir:
        df_doublons_noms.to_csv(os.path.join(output_dir, "doublons_fournisseurs_suspects.csv"), index=False)

    log("\n" + "=" * 70)
    log("4. VÉRIFICATION ET UNIFORMISATION DES TYPES")
    log("=" * 70)

    df_t["date_transaction"] = pd.to_datetime(df_t["date_transaction"], errors="coerce")
    df_f["date_creation_fournisseur"] = pd.to_datetime(df_f["date_creation_fournisseur"], errors="coerce")
    df_e["date_embauche"] = pd.to_datetime(df_e["date_embauche"], errors="coerce")
    df_t["montant"] = pd.to_numeric(df_t["montant"], errors="coerce")

    if df_t["date_transaction"].isna().sum() > 0 or df_t["montant"].isna().sum() > 0:
        df_t = df_t.dropna(subset=["date_transaction", "montant"])

    for col in ["nom_fournisseur", "adresse", "email_contact"]:
        if col in df_f.columns:
            df_f[col] = df_f[col].astype(str).str.strip()

    log("\n" + "=" * 70)
    log("5. CALCUL DU PROFIL DE MONTANT HABITUEL PAR FOURNISSEUR")
    log("=" * 70)

    profil_fournisseur = df_t.groupby("id_fournisseur")["montant"].agg(
        montant_moyen="mean", montant_ecart_type="std", nb_transactions="count"
    ).reset_index()
    profil_fournisseur["montant_ecart_type"] = profil_fournisseur["montant_ecart_type"].fillna(0)

    return df_t, df_f, df_e, profil_fournisseur

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INPUT_DIR = os.path.join(BASE_DIR, "../../data/raw")
    OUTPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")
    SEUIL_SIMILARITE_NOMS = 0.85   # 0 à 1 ; au-dessus = considéré comme doublon potentiel

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    log("=" * 70)
    log("1. CHARGEMENT")
    log("=" * 70)

    df_t_raw = pd.read_csv(os.path.join(INPUT_DIR, "transactions.csv"), encoding="utf-8-sig")
    df_f_raw = pd.read_csv(os.path.join(INPUT_DIR, "fournisseurs.csv"), encoding="utf-8-sig")
    df_e_raw = pd.read_csv(os.path.join(INPUT_DIR, "employes.csv"), encoding="utf-8-sig")

    df_t_clean, df_f_clean, df_e_clean, profil = nettoyer_donnees(
        df_t_raw, df_f_raw, df_e_raw, output_dir=OUTPUT_DIR, seuil_similarite_noms=SEUIL_SIMILARITE_NOMS
    )

    log("\n" + "=" * 70)
    log("6. EXPORT")
    log("=" * 70)

    df_t_clean.to_csv(os.path.join(OUTPUT_DIR, "transactions_clean.csv"), index=False)
    df_f_clean.to_csv(os.path.join(OUTPUT_DIR, "fournisseurs_clean.csv"), index=False)
    df_e_clean.to_csv(os.path.join(OUTPUT_DIR, "employes_clean.csv"), index=False)
    profil.to_csv(os.path.join(OUTPUT_DIR, "profil_montant_fournisseur.csv"), index=False)
    
    log(f"Fichiers exportés dans : {OUTPUT_DIR}/")
    log("Prêt pour l'étape suivante : les règles de détection (Niveau 1).")