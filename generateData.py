# -*- coding: utf-8 -*-
"""
=========================================================================
GÉNÉRATEUR DE DONNÉES FICTIVES — TuniDistrib SA (Vendor Fraud Detection)
=========================================================================
Ce script est PARAMÉTRABLE en volume : de quelques milliers à plusieurs
centaines de milliers de transactions. Il utilise numpy pour vectoriser
les tirages aléatoires (rapide même à grande échelle).

USAGE :
    python generate_data_scalable.py

À AJUSTER SELON LE VOLUME SOUHAITÉ (voir section CONFIGURATION ci-dessous) :
    - N_FOURNISSEURS       : nombre de fournisseurs
    - N_EMPLOYES           : nombre d'employés
    - N_MOIS               : profondeur d'historique
    - TRANSACTIONS_PAR_MOIS: volume mensuel moyen

Exemple pour ~500 000 lignes : N_MOIS=24, TRANSACTIONS_PAR_MOIS=21000
(soit 24 x 21000 ≈ 504 000, proche du volume réel annoncé dans la Note
de Cadrage : ~3500 transactions/mois sur 2 ans).

Dépendances : pandas, numpy, openpyxl (tous standards, pip install si besoin)
=========================================================================
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# =========================================================================
# CONFIGURATION — MODIFIER CES VALEURS SELON LE VOLUME SOUHAITÉ
# =========================================================================
SEED = 42
N_FOURNISSEURS = 150            # ex: augmenter à 500 pour plus de diversité
N_EMPLOYES = 25
N_MOIS = 24                     # profondeur d'historique (24 = 2 ans, cohérent avec la Note de Cadrage)
TRANSACTIONS_PAR_MOIS_MOYENNE = 3500   # volume mensuel réaliste annoncé pour TuniDistrib
TRANSACTIONS_PAR_MOIS_ECART = 300      # variation aléatoire autour de la moyenne

# Sortie : CSV recommandé au-delà de 200 000 lignes (Excel plafonne à
# 1 048 576 lignes par feuille, mais devient très lent à ouvrir au-delà
# de quelques centaines de milliers de lignes formatées)
OUTPUT_FORMAT = "csv"           # "csv" ou "xlsx"
OUTPUT_DIR = "./output_tunidistrib"

random.seed(SEED)
np.random.seed(SEED)

# =========================================================================
# RÉFÉRENTIELS
# =========================================================================
VILLES_TN = ["Tunis", "Ariana", "Sfax", "Sousse", "Nabeul", "Bizerte", "Monastir",
             "Ben Arous", "Manouba", "Kairouan", "Gabès", "Gafsa", "La Marsa", "Menzah"]
PAYS_INTL = ["France", "Chine", "Allemagne", "Italie", "Turquie", "Émirats Arabes Unis"]
NOMS_FOURNISSEURS_BASE = [
    "Electro Plus", "Tunisie Composants", "Maghreb Electronics", "Distrilec",
    "SOTEL Distribution", "High Tech Import", "Elec Import Export", "Digital Store Pro",
    "Confort Electromenager", "Star Elec", "Nord Electronique", "Sud Distribution Tech",
    "Cap Bon Electric", "Carthage Electronics", "Medina Tech", "Atlas Composants",
    "Blue Wave Import", "Silver Tech Distribution", "Golden Electro", "Prime Electronics",
    "Delta Import", "Zenith Distribution", "Horizon Tech", "Ellipse Electro",
    "Continental Import", "Universal Composants", "Rapid Elec Services", "Modern Home Tech",
]

# CORRECTIF : mots combinables pour générer des noms de fournisseurs UNIQUES
# (au-delà des 28 noms de base ci-dessus). Sans ce correctif, un nom de base
# était réutilisé avec un simple suffixe numérique ("Distrilec 2", "Distrilec 3"...),
# ce qui créait de faux doublons détectés par le fuzzy matching (deux entreprises
# réellement différentes, mais au nom trop proche par construction).
PREFIXES_NOMS = ["Excellence", "Alpha", "Beta", "Oasis", "National", "General", "Techno",
                 "Smart Home", "Grand Sud", "Nouvelle Vague", "Premium", "Fast Track",
                 "Espace", "Groupe", "Comptoir", "Société", "Atelier", "Central",
                 "Panorama", "Trans", "Méditerranée", "Africa", "Magenta", "Cristal"]
VILLES_POUR_NOMS = ["Tunis", "Sfax", "Sousse", "Nabeul", "Bizerte", "Monastir", "Kairouan",
                     "Gabès", "Gafsa", "Sahel", "Cap Bon", "Ariana"]

def generer_noms_fournisseurs_uniques(n):
    """Génère n noms de fournisseurs distincts et réalistes, en combinant les
    noms de base avec des préfixes et des villes, sans jamais recycler un même
    nom avec un simple suffixe numérique."""
    noms = list(NOMS_FOURNISSEURS_BASE)  # les 28 noms de base, tels quels
    rng = random.Random(SEED + 1)
    # Combinaisons Préfixe + nom de base (ex: "Excellence Distrilec")
    combinaisons_prefixe = [f"{p} {b}" for p in PREFIXES_NOMS for b in NOMS_FOURNISSEURS_BASE]
    rng.shuffle(combinaisons_prefixe)
    # Combinaisons nom de base + Ville (ex: "Distrilec Sfax")
    combinaisons_ville = [f"{b} {v}" for b in NOMS_FOURNISSEURS_BASE for v in VILLES_POUR_NOMS]
    rng.shuffle(combinaisons_ville)
    for nom in combinaisons_prefixe + combinaisons_ville:
        if len(noms) >= n:
            break
        if nom not in noms:
            noms.append(nom)
    return noms[:n]

TYPES_DEPENSE = ["Achat marchandise", "Prestation de conseil", "Transport", "Maintenance",
                  "Prestation technique", "Location matériel", "Emballage"]
MODES_PAIEMENT = ["Virement", "Chèque"]
PRENOMS_H = ["Amine", "Karim", "Sami", "Walid", "Nabil", "Hichem", "Slim", "Fares",
             "Youssef", "Bilel", "Mehdi", "Rami", "Anis", "Tarek", "Marwen"]
PRENOMS_F = ["Rim", "Nour", "Amira", "Sonia", "Hela", "Meriem", "Ines", "Salma",
             "Yosra", "Emna", "Dorra", "Wided"]
NOMS_FAMILLE = ["Ben Ali", "Trabelsi", "Gharbi", "Jlassi", "Mansour", "Khelifi",
                "Bouzid", "Cherif", "Sassi", "Ayari", "Zoghlami", "Rekik", "Nasri",
                "Belhaj", "Ouertani", "Hamdi", "Ferjani", "Souissi", "Bahri", "Guesmi"]
POSTES = ["Comptable Fournisseurs", "Comptable Fournisseurs", "Responsable Comptabilité",
          "Assistant Comptable", "Contrôleur de Gestion", "Directeur Administratif et Financier",
          "Responsable Achats", "Assistant Achats"]
RUES = ["Avenue Habib Bourguiba", "Rue de Marseille", "Avenue Mohamed V",
        "Rue du Lac Léman", "Avenue de la Liberté", "Rue Charles de Gaulle",
        "Avenue Taïeb Mhiri", "Rue Ibn Khaldoun", "Avenue de Carthage"]


def rib_tn(seed_num):
    rng = random.Random(seed_num)
    digits = "".join(str(rng.randint(0, 9)) for _ in range(20))
    return f"TN59 {digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]} {digits[16:20]}"


def adresse_aleatoire():
    return f"{random.randint(2,120)} {random.choice(RUES)}, {random.choice(VILLES_TN)}"


def telephone_aleatoire():
    return f"+216 {random.randint(20,29)} {random.randint(100,999)} {random.randint(100,999)}"


# =========================================================================
# TABLE EMPLOYÉS
# =========================================================================
employes = []
for i in range(1, N_EMPLOYES + 1):
    sexe = random.choice(["H", "F"])
    prenom = random.choice(PRENOMS_H) if sexe == "H" else random.choice(PRENOMS_F)
    nom_complet = f"{prenom} {random.choice(NOMS_FAMILLE)}"
    poste = random.choice(POSTES)
    embauche = datetime(2018, 1, 1) + timedelta(days=random.randint(0, 2500))
    employes.append({
        "id_employe": f"EMP-{i:03d}",
        "nom_employe": nom_complet,
        "poste": poste,
        "adresse_personnelle": adresse_aleatoire(),
        "telephone": telephone_aleatoire(),
        "date_embauche": embauche.strftime("%Y-%m-%d"),
    })
df_employes = pd.DataFrame(employes)
employes_validateurs = df_employes[df_employes["poste"].isin(
    ["Comptable Fournisseurs", "Responsable Comptabilité", "Directeur Administratif et Financier"]
)]["id_employe"].tolist()
employes_initiateurs = df_employes["id_employe"].tolist()

# =========================================================================
# TABLE FOURNISSEURS
# =========================================================================
fournisseurs = []
date_debut_historique = datetime.today() - timedelta(days=30 * N_MOIS + 60)
date_fin_historique = datetime.today()

# CORRECTIF : noms générés une seule fois, tous distincts (voir
# generer_noms_fournisseurs_uniques ci-dessus), au lieu de recycler les
# 28 noms de base avec un suffixe numérique.
noms_fournisseurs_uniques = generer_noms_fournisseurs_uniques(N_FOURNISSEURS)

for i in range(1, N_FOURNISSEURS + 1):
    nom_fournisseur = noms_fournisseurs_uniques[i - 1]
    international = random.random() < 0.2
    pays = random.choice(PAYS_INTL) if international else "Tunisie"
    # CORRECTIF : tous les fournisseurs "normaux" sont créés AVANT le début
    # de la période de transactions (dans la fenêtre tampon de 60 jours),
    # afin qu'aucune transaction ne précède la création de son fournisseur.
    # Seuls les fournisseurs volontairement frauduleux (cas "création tardive",
    # injectés plus bas) auront une date de création à l'intérieur de la période.
    creation = date_debut_historique + timedelta(days=random.randint(0, 59))
    fournisseurs.append({
        "id_fournisseur": f"FRS-{i:05d}",
        "nom_fournisseur": nom_fournisseur,
        "rib_iban": rib_tn(1000 + i),
        "adresse": adresse_aleatoire() if not international else f"Adresse internationale, {pays}",
        "telephone": telephone_aleatoire(),
        "date_creation_fournisseur": creation.strftime("%Y-%m-%d"),
        "statut_fournisseur": random.choices(["Actif", "Inactif", "Bloqué"], weights=[90, 8, 2])[0],
        "pays": pays,
    })
df_fournisseurs = pd.DataFrame(fournisseurs)
fournisseurs_actifs = df_fournisseurs[df_fournisseurs["statut_fournisseur"] != "Bloqué"]["id_fournisseur"].tolist()

# Profil de montant habituel par fournisseur (pour des transactions réalistes)
profils_montant = {fid: random.choice([250, 500, 800, 1500, 3000, 6000, 9000])
                    for fid in df_fournisseurs["id_fournisseur"]}

# =========================================================================
# TABLE TRANSACTIONS — génération vectorisée (rapide à grande échelle)
# =========================================================================
lignes_par_mois = np.random.randint(
    TRANSACTIONS_PAR_MOIS_MOYENNE - TRANSACTIONS_PAR_MOIS_ECART,
    TRANSACTIONS_PAR_MOIS_MOYENNE + TRANSACTIONS_PAR_MOIS_ECART,
    size=N_MOIS
)
total_transactions = int(lignes_par_mois.sum())
print(f"Génération de {total_transactions:,} transactions...")

fournisseurs_arr = np.array(fournisseurs_actifs)
employes_init_arr = np.array(employes_initiateurs)
employes_valid_arr = np.array(employes_validateurs)

frs_tirage = np.random.choice(fournisseurs_arr, size=total_transactions)
init_tirage = np.random.choice(employes_init_arr, size=total_transactions)
valid_tirage = np.random.choice(employes_valid_arr, size=total_transactions)
statut_tirage = np.random.choice(["Validé", "En attente", "Rejeté"], size=total_transactions, p=[0.92, 0.06, 0.02])
mode_tirage = np.random.choice(MODES_PAIEMENT, size=total_transactions, p=[0.8, 0.2])
type_tirage = np.random.choice(TYPES_DEPENSE, size=total_transactions)

# Montants : distribution normale autour du profil habituel de chaque fournisseur
moyennes = np.array([profils_montant[f] for f in frs_tirage])
montants = np.round(np.maximum(50, np.random.normal(moyennes, moyennes * 0.25)), 3)

# Dates : réparties sur les N_MOIS, mois par mois
dates = []
cursor = date_debut_historique + timedelta(days=60)
for m, n in enumerate(lignes_par_mois):
    debut_mois = cursor + timedelta(days=30 * m)
    offsets = np.random.randint(0, 29, size=n)
    dates.extend([(debut_mois + timedelta(days=int(o))).strftime("%Y-%m-%d") for o in offsets])

df_transactions = pd.DataFrame({
    "id_transaction": [f"TX-{i:07d}" for i in range(1, total_transactions + 1)],
    "date_transaction": dates,
    "id_fournisseur": frs_tirage,
    "montant": montants,
    "devise": "TND",
    "type_depense": type_tirage,
    "mode_paiement": mode_tirage,
    "id_employe_initiateur": init_tirage,
    "id_employe_validateur": valid_tirage,
    "statut_validation": statut_tirage,
    "numero_facture": [f"FAC-{random.randint(10000,99999)}" for _ in range(total_transactions)],
})
df_transactions = df_transactions.sort_values("date_transaction").reset_index(drop=True)

# =========================================================================
# INJECTION DE CAS DE FRAUDE (proportionnelle au volume : ~0.1% des transactions)
# =========================================================================
n_cas_fraude = max(10, total_transactions // 1000)
print(f"Injection de {n_cas_fraude} cas de fraude...")

fraude_log = []
indices_fraude = np.random.choice(df_transactions.index, size=n_cas_fraude, replace=False)

for k, idx in enumerate(indices_fraude):
    # GARDE : si cette ligne a déjà été supprimée par le nettoyage d'un cas de
    # fraude traité plus tôt dans la boucle (ex: un autre cas "création tardive"
    # touchant le même fournisseur), on passe simplement à l'itération suivante.
    if idx not in df_transactions.index:
        continue
    type_cas = k % 4
    if type_cas == 0:
        # RIB partagé : on force le RIB d'un 2e fournisseur (différent) à copier celui-ci
        frs_source = df_transactions.loc[idx, "id_fournisseur"]
        candidats_cible = [f for f in fournisseurs_actifs if f != frs_source]
        frs_cible = random.choice(candidats_cible)
        rib_source = df_fournisseurs.loc[df_fournisseurs.id_fournisseur == frs_source, "rib_iban"].values[0]
        df_fournisseurs.loc[df_fournisseurs.id_fournisseur == frs_cible, "rib_iban"] = rib_source
        fraude_log.append({"type_fraude": "RIB partagé", "reference": f"{frs_source}/{frs_cible}"})
    elif type_cas == 1:
        # Montant anormal
        df_transactions.loc[idx, "montant"] = round(df_transactions.loc[idx, "montant"] * 8, 3)
        fraude_log.append({"type_fraude": "Montant anormal", "reference": df_transactions.loc[idx, "id_transaction"]})
    elif type_cas == 2:
        # Doublon de facture (on duplique la ligne avec date +3j et montant +1.5)
        nouvelle_ligne = df_transactions.loc[idx].copy()
        nouvelle_ligne["id_transaction"] = f"TX-{total_transactions + k:07d}"
        nouvelle_ligne["montant"] = round(nouvelle_ligne["montant"] + 1.5, 3)
        nouvelle_ligne["date_transaction"] = (
            datetime.strptime(df_transactions.loc[idx, "date_transaction"], "%Y-%m-%d") + timedelta(days=3)
        ).strftime("%Y-%m-%d")
        # CORRECTIF : on n'utilise plus ignore_index=True (qui réinitialisait
        # tous les index et cassait la correspondance des 'idx' déjà tirés pour
        # les itérations suivantes de cette boucle). On assigne un nouvel index
        # unique à la ligne ajoutée, sans toucher aux index existants.
        nouvel_index = df_transactions.index.max() + 1
        nouvelle_ligne_df = nouvelle_ligne.to_frame().T
        nouvelle_ligne_df.index = [nouvel_index]
        df_transactions = pd.concat([df_transactions, nouvelle_ligne_df])
        fraude_log.append({"type_fraude": "Doublon de facture", "reference": df_transactions.loc[idx, "id_transaction"]})
    else:
        # Fournisseur créé juste avant paiement
        frs = df_transactions.loc[idx, "id_fournisseur"]
        date_t = df_transactions.loc[idx, "date_transaction"]
        date_creation_suspecte = (datetime.strptime(date_t, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        df_fournisseurs.loc[df_fournisseurs.id_fournisseur == frs, "date_creation_fournisseur"] = date_creation_suspecte
        # CORRECTIF : un fournisseur fictif créé pour cette fraude ponctuelle ne
        # doit pas avoir d'autres transactions "normales" antérieures à sa date
        # de création (incohérence logique + irréaliste : un fournisseur fictif
        # a très peu d'historique). On supprime ses autres transactions passées.
        masque_autres_transac = (
            (df_transactions["id_fournisseur"] == frs)
            & (df_transactions["date_transaction"] < date_creation_suspecte)
            & (df_transactions.index != idx)
        )
        df_transactions = df_transactions[~masque_autres_transac]
        fraude_log.append({"type_fraude": "Création fournisseur juste avant paiement", "reference": frs})

df_fraude_log = pd.DataFrame(fraude_log)
df_transactions = df_transactions.sort_values("date_transaction").reset_index(drop=True)

# =========================================================================
# INJECTION DE FRAUDES "MULTI-SIGNAUX" — subtiles, invisibles aux règles
# =========================================================================
# Ces cas combinent plusieurs déviations faibles simultanées, chacune
# individuellement sous les seuils des 4 règles existantes, mais dont la
# combinaison est statistiquement atypique (détectable par Isolation Forest).
# ~35 cas au total, soit < 0.1% du volume total.
print("Injection des fraudes multi-signaux (subtiles)...")

multi_signaux_log = []

# ── Préparer les fournisseurs éligibles (actifs, non déjà frauduleux) ────
frs_deja_fraudes = set()
for entry in fraude_log:
    ref = str(entry["reference"])
    if "/" in ref:
        frs_deja_fraudes.update(ref.split("/"))
    elif ref.startswith("FRS"):
        frs_deja_fraudes.add(ref)

frs_eligibles = [
    f for f in fournisseurs_actifs
    if f not in frs_deja_fraudes
]
rng_multi = random.Random(SEED + 100)
np.random.seed(SEED + 100)
rng_multi.shuffle(frs_eligibles)

# Répartir les fournisseurs éligibles entre les 4 types
frs_type1 = frs_eligibles[0:8]     # Dérive progressive
frs_type2 = frs_eligibles[8:18]    # Concentration employé
frs_type3 = frs_eligibles[18:26]   # Fréquence post-création
frs_type4 = frs_eligibles[26:35]   # Montant+timing

# ─────────────────────────────────────────────────────────────────────────
# TYPE 1 — Dérive progressive de montant
# ─────────────────────────────────────────────────────────────────────────
# Un fournisseur dont les montants augmentent de +3 à 5% par mois sur les
# 6 derniers mois. Chaque transaction reste < μ + 3σ.
print(f"  Type 1 — Dérive progressive : {len(frs_type1)} fournisseurs")

for frs_id in frs_type1:
    taux_mensuel = rng_multi.uniform(0.03, 0.05)  # +3 à 5% par mois
    mask_frs = df_transactions["id_fournisseur"] == frs_id
    tx_frs = df_transactions.loc[mask_frs].copy()

    if len(tx_frs) < 20:
        continue

    # Identifier les 6 derniers mois de transactions
    tx_frs["date_dt"] = pd.to_datetime(tx_frs["date_transaction"])
    date_max = tx_frs["date_dt"].max()
    date_seuil = date_max - timedelta(days=180)
    mask_derniers_mois = (tx_frs["date_dt"] >= date_seuil)

    tx_cibles = tx_frs.loc[mask_derniers_mois].sort_values("date_dt")
    if len(tx_cibles) < 10:
        continue

    # Calculer le multiplicateur progressif selon l'ancienneté dans la fenêtre
    mu = profils_montant[frs_id]
    sigma = mu * 0.25
    seuil_3sigma = mu + 3 * sigma  # = 1.75 × μ

    for _, row in tx_cibles.iterrows():
        mois_depuis_debut = (row["date_dt"] - date_seuil).days / 30.0
        multiplicateur = (1 + taux_mensuel) ** mois_depuis_debut
        nouveau_montant = row["montant"] * multiplicateur

        # Plafonner à μ + 2.8σ pour rester sous le seuil 3σ
        plafond = mu + 2.8 * sigma
        nouveau_montant = min(nouveau_montant, plafond)
        df_transactions.loc[row.name, "montant"] = round(nouveau_montant, 3)

    multi_signaux_log.append({
        "type_fraude": "Multi-signaux - Dérive progressive",
        "reference": frs_id,
    })

# ─────────────────────────────────────────────────────────────────────────
# TYPE 2 — Concentration anormale employé
# ─────────────────────────────────────────────────────────────────────────
# Un même binôme initiateur/validateur traite >80% des transactions d'un
# fournisseur donné (normalement ~4-5% par binôme).
print(f"  Type 2 — Concentration employé : {len(frs_type2)} fournisseurs")

for frs_id in frs_type2:
    mask_frs = df_transactions["id_fournisseur"] == frs_id
    tx_indices = df_transactions.loc[mask_frs].index

    if len(tx_indices) < 15:
        continue

    # Choisir un binôme initiateur/validateur fixe
    initiateur = rng_multi.choice(employes_initiateurs)
    # Validateur différent de l'initiateur
    validateur = rng_multi.choice([v for v in employes_validateurs if v != initiateur])

    # Forcer ce binôme sur 80-90% des transactions
    taux_concentration = rng_multi.uniform(0.80, 0.90)
    nb_a_forcer = int(len(tx_indices) * taux_concentration)
    indices_a_forcer = rng_multi.sample(list(tx_indices), nb_a_forcer)

    df_transactions.loc[indices_a_forcer, "id_employe_initiateur"] = initiateur
    df_transactions.loc[indices_a_forcer, "id_employe_validateur"] = validateur

    multi_signaux_log.append({
        "type_fraude": "Multi-signaux - Concentration employé",
        "reference": frs_id,
    })

# ─────────────────────────────────────────────────────────────────────────
# TYPE 3 — Fréquence anormale post-création
# ─────────────────────────────────────────────────────────────────────────
# Fournisseur récemment créé (10-15j avant 1ère transaction, au-delà du
# seuil de 2j) qui reçoit 3× le volume normal sur son 1er mois.
print(f"  Type 3 — Fréquence post-création : {len(frs_type3)} fournisseurs")

for frs_id in frs_type3:
    mask_frs = df_transactions["id_fournisseur"] == frs_id
    tx_frs = df_transactions.loc[mask_frs].copy()

    if len(tx_frs) < 10:
        continue

    tx_frs["date_dt"] = pd.to_datetime(tx_frs["date_transaction"])
    premiere_tx = tx_frs["date_dt"].min()

    # Décaler la date de création à 10-15 jours avant la première transaction
    ecart_jours = rng_multi.randint(10, 15)
    nouvelle_date_creation = (premiere_tx - timedelta(days=ecart_jours)).strftime("%Y-%m-%d")
    df_fournisseurs.loc[
        df_fournisseurs["id_fournisseur"] == frs_id,
        "date_creation_fournisseur"
    ] = nouvelle_date_creation

    # Concentrer des transactions supplémentaires sur le 1er mois
    # On duplique 2× les transactions du 1er mois (avec ID et facture uniques)
    fin_premier_mois = premiere_tx + timedelta(days=30)
    tx_premier_mois = tx_frs[tx_frs["date_dt"] <= fin_premier_mois]

    nb_a_ajouter = min(len(tx_premier_mois) * 2, 15)  # plafonner à 15 ajouts
    if nb_a_ajouter > 0:
        base_idx = df_transactions.index.max() + 1
        base_tx_id = len(df_transactions) + 1

        nouvelles_lignes = []
        for j in range(nb_a_ajouter):
            src = tx_premier_mois.iloc[j % len(tx_premier_mois)].copy()
            src["id_transaction"] = f"TX-{base_tx_id + j:07d}"
            src["numero_facture"] = f"FAC-{rng_multi.randint(10000, 99999)}"
            # Date aléatoire dans le 1er mois, >= ecart_jours après création
            offset = rng_multi.randint(ecart_jours + 1, ecart_jours + 30)
            date_creation_dt = datetime.strptime(nouvelle_date_creation, "%Y-%m-%d")
            src["date_transaction"] = (date_creation_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            # Montant normal pour ce fournisseur
            mu = profils_montant[frs_id]
            src["montant"] = round(max(50, np.random.normal(mu, mu * 0.25)), 3)
            nouvelles_lignes.append(src)

        df_new = pd.DataFrame(nouvelles_lignes)
        df_new.index = range(base_idx, base_idx + len(df_new))
        # Supprimer la colonne temporaire date_dt si elle existe
        if "date_dt" in df_new.columns:
            df_new = df_new.drop(columns=["date_dt"])
        df_transactions = pd.concat([df_transactions, df_new])

    multi_signaux_log.append({
        "type_fraude": "Multi-signaux - Fréquence post-création",
        "reference": frs_id,
    })

# ─────────────────────────────────────────────────────────────────────────
# TYPE 4 — Montant + timing combinés
# ─────────────────────────────────────────────────────────────────────────
# Transactions en fin de mois (jours 25-31) systématiquement à μ+1.5σ–2σ
# (sous le seuil 3σ), alors que le reste du mois est normal.
print(f"  Type 4 — Montant+timing : {len(frs_type4)} fournisseurs")

for frs_id in frs_type4:
    mask_frs = df_transactions["id_fournisseur"] == frs_id
    tx_frs = df_transactions.loc[mask_frs].copy()

    if len(tx_frs) < 15:
        continue

    tx_frs["date_dt"] = pd.to_datetime(tx_frs["date_transaction"])
    tx_frs["jour"] = tx_frs["date_dt"].dt.day

    # Transactions en fin de mois (jours 25-31)
    mask_fin_mois = tx_frs["jour"] >= 25
    tx_fin_mois = tx_frs.loc[mask_fin_mois]

    if len(tx_fin_mois) < 5:
        continue

    mu = profils_montant[frs_id]
    sigma = mu * 0.25

    for idx_row in tx_fin_mois.index:
        # Montant entre μ + 1.5σ et μ + 2σ (bien sous le seuil 3σ)
        facteur = rng_multi.uniform(1.5, 2.0)
        nouveau_montant = mu + facteur * sigma
        df_transactions.loc[idx_row, "montant"] = round(nouveau_montant, 3)

    multi_signaux_log.append({
        "type_fraude": "Multi-signaux - Montant+timing",
        "reference": frs_id,
    })

# ── Consolider le journal ────────────────────────────────────────────────
df_multi_log = pd.DataFrame(multi_signaux_log)
df_fraude_log = pd.concat([df_fraude_log, df_multi_log], ignore_index=True)

# Nettoyer la colonne temporaire si elle subsiste
if "date_dt" in df_transactions.columns:
    df_transactions = df_transactions.drop(columns=["date_dt"])

df_transactions = df_transactions.sort_values("date_transaction").reset_index(drop=True)

print(f"  → {len(multi_signaux_log)} cas multi-signaux injectés")

# =========================================================================
# EXPORT
# =========================================================================
import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

if OUTPUT_FORMAT == "csv":
    df_transactions.to_csv(f"{OUTPUT_DIR}/transactions.csv", index=False, encoding="utf-8-sig")
    df_fournisseurs.to_csv(f"{OUTPUT_DIR}/fournisseurs.csv", index=False, encoding="utf-8-sig")
    df_employes.to_csv(f"{OUTPUT_DIR}/employes.csv", index=False, encoding="utf-8-sig")
    df_fraude_log.to_csv(f"{OUTPUT_DIR}/journal_fraudes_injectees.csv", index=False, encoding="utf-8-sig")
else:
    with pd.ExcelWriter(f"{OUTPUT_DIR}/TuniDistrib_Donnees.xlsx", engine="openpyxl") as writer:
        df_transactions.to_excel(writer, sheet_name="Transactions", index=False)
        df_fournisseurs.to_excel(writer, sheet_name="Fournisseurs", index=False)
        df_employes.to_excel(writer, sheet_name="Employes", index=False)
        df_fraude_log.to_excel(writer, sheet_name="Journal_Fraudes_Injectees", index=False)

print(f"\nTerminé.")
print(f"  Transactions      : {len(df_transactions):,}")
print(f"  Fournisseurs      : {len(df_fournisseurs):,}")
print(f"  Employés          : {len(df_employes):,}")
print(f"  Cas de fraude     : {len(df_fraude_log):,}")
print(f"  Fichiers dans     : {OUTPUT_DIR}/")