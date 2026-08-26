# -*- coding: utf-8 -*-
"""
=========================================================================
DIAGNOSTIC QUALITÉ DES DONNÉES — TuniDistrib SA
=========================================================================
À exécuter AVANT tout nettoyage ou règle de détection.
Objectif : vérifier que les 4 fichiers CSV sont exploitables et cohérents
entre eux, et que les cas de fraude injectés sont bien présents/détectables.

USAGE :
    python3 diagnostic_donnees.py

Placer ce script dans le même dossier que :
    transactions.csv
    fournisseurs.csv
    employes.csv
    journal_fraudes_injectees.csv

Un rapport texte complet est aussi sauvegardé dans :
    rapport_diagnostic.txt
=========================================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import io

# =========================================================================
# Redirection : tout ce qui est "print" va aussi dans un fichier rapport
# =========================================================================
class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()

rapport_file = open("rapport_diagnostic.txt", "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, rapport_file)

def titre(txt):
    print("\n" + "=" * 78)
    print(txt)
    print("=" * 78)

def sous_titre(txt):
    print("\n--- " + txt + " ---")

# =========================================================================
# 1. CHARGEMENT
# =========================================================================
titre("1. CHARGEMENT DES FICHIERS")

fichiers = {
    "transactions": "output_tunidistrib/transactions.csv",
    "fournisseurs": "output_tunidistrib/fournisseurs.csv",
    "employes": "output_tunidistrib/employes.csv",
    "fraude_log": "output_tunidistrib/journal_fraudes_injectees.csv",
}

dfs = {}
erreurs_chargement = []
for nom, chemin in fichiers.items():
    try:
        df = pd.read_csv(chemin, encoding="utf-8-sig")
        dfs[nom] = df
        print(f"[OK] {chemin:45s} -> {len(df):>8,} lignes, {len(df.columns):>2} colonnes")
    except FileNotFoundError:
        erreurs_chargement.append(chemin)
        print(f"[MANQUANT] {chemin} introuvable dans le dossier courant.")
    except Exception as e:
        erreurs_chargement.append(chemin)
        print(f"[ERREUR] {chemin}: {e}")

if erreurs_chargement:
    print(f"\n/!\\ {len(erreurs_chargement)} fichier(s) n'ont pas pu être chargés. "
          f"Vérifie qu'ils sont bien dans le même dossier que ce script.")
    sys.stdout = sys.__stdout__
    rapport_file.close()
    sys.exit(1)

df_t = dfs["transactions"]
df_f = dfs["fournisseurs"]
df_e = dfs["employes"]
df_log = dfs["fraude_log"]

# =========================================================================
# 2. STRUCTURE ET COMPLÉTUDE
# =========================================================================
titre("2. STRUCTURE ET COMPLÉTUDE")

for nom, df in [("Transactions", df_t), ("Fournisseurs", df_f), ("Employés", df_e)]:
    sous_titre(f"Table: {nom}")
    print(f"Colonnes ({len(df.columns)}): {list(df.columns)}")
    n_vides = df.isna().sum()
    n_vides = n_vides[n_vides > 0]
    if len(n_vides) == 0:
        print("Aucune valeur manquante détectée.")
    else:
        print("Valeurs manquantes par colonne :")
        for col, n in n_vides.items():
            pct = 100 * n / len(df)
            print(f"  - {col:35s}: {n:>6,} manquantes ({pct:.2f}%)")
    n_doublons_lignes = df.duplicated().sum()
    print(f"Lignes strictement dupliquées (toutes colonnes identiques) : {n_doublons_lignes}")

# Vérification des types
sous_titre("Vérification des types de données")
try:
    montants_non_numeriques = pd.to_numeric(df_t["montant"], errors="coerce").isna().sum()
    print(f"Transactions.montant  -> valeurs non numériques : {montants_non_numeriques}")
except KeyError:
    print("/!\\ Colonne 'montant' absente de Transactions.")

try:
    dates_invalides = pd.to_datetime(df_t["date_transaction"], errors="coerce").isna().sum()
    print(f"Transactions.date_transaction -> dates invalides/non parsables : {dates_invalides}")
except KeyError:
    print("/!\\ Colonne 'date_transaction' absente de Transactions.")

# =========================================================================
# 3. COHÉRENCE RELATIONNELLE (clés entre tables)
# =========================================================================
titre("3. COHÉRENCE RELATIONNELLE ENTRE TABLES")

ids_fournisseurs_valides = set(df_f["id_fournisseur"])
ids_employes_valides = set(df_e["id_employe"])

sous_titre("Transactions -> Fournisseurs")
frs_orphelins = set(df_t["id_fournisseur"]) - ids_fournisseurs_valides
n_lignes_orphelines = df_t["id_fournisseur"].isin(frs_orphelins).sum()
print(f"id_fournisseur référencés dans Transactions mais absents de Fournisseurs : {len(frs_orphelins)}")
print(f"Nombre de transactions concernées (orphelines) : {n_lignes_orphelines}")
if frs_orphelins:
    print(f"Exemples : {list(frs_orphelins)[:5]}")

sous_titre("Transactions -> Employés (initiateur)")
if "id_employe_initiateur" in df_t.columns:
    init_orphelins = set(df_t["id_employe_initiateur"]) - ids_employes_valides
    print(f"id_employe_initiateur absents de la table Employés : {len(init_orphelins)}")
else:
    print("/!\\ Colonne 'id_employe_initiateur' absente.")

sous_titre("Transactions -> Employés (validateur)")
if "id_employe_validateur" in df_t.columns:
    valid_orphelins = set(df_t["id_employe_validateur"]) - ids_employes_valides
    print(f"id_employe_validateur absents de la table Employés : {len(valid_orphelins)}")
else:
    print("/!\\ Colonne 'id_employe_validateur' absente.")

sous_titre("Fournisseurs -> doublons d'identifiant")
n_id_frs_dupliques = df_f["id_fournisseur"].duplicated().sum()
print(f"id_fournisseur en double dans la table Fournisseurs : {n_id_frs_dupliques}")

sous_titre("Employés -> doublons d'identifiant")
n_id_emp_dupliques = df_e["id_employe"].duplicated().sum()
print(f"id_employe en double dans la table Employés : {n_id_emp_dupliques}")

# =========================================================================
# 4. PLAUSIBILITÉ STATISTIQUE
# =========================================================================
titre("4. PLAUSIBILITÉ STATISTIQUE")

sous_titre("Montants")
montants = pd.to_numeric(df_t["montant"], errors="coerce")
print(f"Min     : {montants.min():,.3f}")
print(f"Max     : {montants.max():,.3f}")
print(f"Moyenne : {montants.mean():,.3f}")
print(f"Médiane : {montants.median():,.3f}")
n_negatifs = (montants < 0).sum()
n_zero = (montants == 0).sum()
print(f"Montants négatifs : {n_negatifs}")
print(f"Montants à zéro   : {n_zero}")

sous_titre("Dates")
dates = pd.to_datetime(df_t["date_transaction"], errors="coerce")
print(f"Date la plus ancienne : {dates.min()}")
print(f"Date la plus récente  : {dates.max()}")
n_futures = (dates > pd.Timestamp.today()).sum()
print(f"Transactions datées dans le futur : {n_futures}")

sous_titre("Cohérence dates de création fournisseur vs. dates de transaction")
df_f["date_creation_fournisseur"] = pd.to_datetime(df_f["date_creation_fournisseur"], errors="coerce")
merge_check = df_t.merge(df_f[["id_fournisseur", "date_creation_fournisseur"]], on="id_fournisseur", how="left")
merge_check["date_transaction_dt"] = pd.to_datetime(merge_check["date_transaction"], errors="coerce")
transac_avant_creation = (merge_check["date_transaction_dt"] < merge_check["date_creation_fournisseur"]).sum()
print(f"Transactions datées AVANT la création officielle du fournisseur : {transac_avant_creation}")
print("(Un nombre non nul ici est un signal fort à investiguer : soit une fraude potentielle,")
print(" soit une incohérence de génération/saisie à corriger.)")

# =========================================================================
# 5. DÉTECTABILITÉ DES CAS DE FRAUDE INJECTÉS
# =========================================================================
titre("5. VÉRIFICATION DES CAS DE FRAUDE INJECTÉS (JOURNAL)")

print(f"Nombre de cas listés dans le journal : {len(df_log)}")
print(df_log.to_string(index=False))

sous_titre("Test 1 — RIB partagés entre plusieurs fournisseurs")
rib_counts = df_f["rib_iban"].str.replace(" ", "", regex=False).value_counts()
rib_partages = rib_counts[rib_counts > 1]
print(f"RIB utilisés par plusieurs fournisseurs différents : {len(rib_partages)}")
if len(rib_partages) > 0:
    for rib, n in rib_partages.items():
        frs_concernes = df_f[df_f["rib_iban"].str.replace(" ", "", regex=False) == rib]["id_fournisseur"].tolist()
        print(f"  - RIB partagé par {n} fournisseurs : {frs_concernes}")
else:
    print("  /!\\ ATTENTION : aucun RIB partagé détecté. Si le journal en annonce,")
    print("      il y a un problème de génération ou de format à corriger avant de coder la règle.")

sous_titre("Test 2 — Montants extrêmes (outliers statistiques)")
seuil_haut = montants.mean() + 3 * montants.std()
outliers = df_t[montants > seuil_haut]
print(f"Seuil (moyenne + 3 écarts-types) : {seuil_haut:,.2f}")
print(f"Transactions au-delà de ce seuil : {len(outliers)}")
if len(outliers) > 0:
    print(outliers[["id_transaction", "id_fournisseur", "montant", "date_transaction"]].head(10).to_string(index=False))

sous_titre("Test 3 — Doublons de facturation (montants quasi identiques, même fournisseur, dates proches)")
df_t_sorted = df_t.copy()
df_t_sorted["date_transaction"] = pd.to_datetime(df_t_sorted["date_transaction"], errors="coerce")
df_t_sorted = df_t_sorted.sort_values(["id_fournisseur", "date_transaction"])
doublons_potentiels = 0
for frs_id, groupe in df_t_sorted.groupby("id_fournisseur"):
    montants_g = groupe["montant"].values
    dates_g = groupe["date_transaction"].values
    for i in range(len(montants_g) - 1):
        if abs(montants_g[i] - montants_g[i+1]) <= 3 and \
           abs((dates_g[i+1] - dates_g[i]).astype('timedelta64[D]').astype(int)) <= 7:
            doublons_potentiels += 1
print(f"Paires de transactions suspectes (écart <= 3 DT, <= 7 jours, même fournisseur) : {doublons_potentiels}")

sous_titre("Test 4 — Fournisseurs payés très peu de temps après création")
merge_check["delai_creation_paiement"] = (merge_check["date_transaction_dt"] - merge_check["date_creation_fournisseur"]).dt.days
creations_suspectes = merge_check[merge_check["delai_creation_paiement"] <= 2]
print(f"Transactions survenues <= 2 jours après création du fournisseur : {len(creations_suspectes)}")
if len(creations_suspectes) > 0:
    print(creations_suspectes[["id_transaction","id_fournisseur","date_transaction","delai_creation_paiement"]].head(10).to_string(index=False))

# =========================================================================
# 6. RÉSUMÉ ET VERDICT
# =========================================================================
titre("6. RÉSUMÉ ET VERDICT")

problemes = []
if erreurs_chargement:
    problemes.append("Fichiers manquants ou illisibles")
if n_lignes_orphelines > 0:
    problemes.append(f"{n_lignes_orphelines} transactions orphelines (fournisseur inconnu)")
if montants_non_numeriques > 0:
    problemes.append(f"{montants_non_numeriques} montants non numériques")
if dates_invalides > 0:
    problemes.append(f"{dates_invalides} dates invalides")
if n_negatifs > 0:
    problemes.append(f"{n_negatifs} montants négatifs")
if len(rib_partages) == 0 and len(df_log[df_log['type_fraude'].str.contains('RIB', case=False, na=False)]) > 0:
    problemes.append("Cas de fraude 'RIB partagé' annoncé dans le journal mais non détecté dans les données")

if not problemes:
    print("✓ Aucun problème bloquant détecté.")
    print("✓ Les données sont structurellement cohérentes et exploitables.")
    print("✓ Les signaux de fraude injectés sont détectables avec des vérifications simples.")
    print("\n=> On peut avancer vers l'étape de nettoyage/normalisation, puis les règles de détection.")
else:
    print(f"/!\\ {len(problemes)} point(s) à corriger avant de continuer :")
    for p in problemes:
        print(f"   - {p}")
    print("\n=> Corriger ces points avant de construire les règles de détection,")
    print("   sinon les règles seront testées sur des données non fiables.")

print(f"\nRapport complet sauvegardé dans : rapport_diagnostic.txt")

sys.stdout = sys.__stdout__
rapport_file.close()