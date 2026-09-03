import pandas as pd
import numpy as np
import os
import networkx as nx
from networkx.algorithms.community import louvain_communities

def detecter_collusion_graphe(transactions, fournisseurs, employes):
    """
    Construit le graphe de collusion et détecte les communautés suspectes.
    Retourne le DataFrame transactions enrichi de 'fournisseur_suspect_collusion' et 'employe_suspect_collusion'.
    """
    print("\n🕸️  Construction du graphe et détection de collusion (Niveau 3)...")
    df_tx = transactions.copy()
    
    G = nx.Graph()
    for _, row in fournisseurs.iterrows():
        G.add_node(row["id_fournisseur"], type="fournisseur", adresse=row["adresse"], tel=row.get("telephone", ""))
    for _, row in employes.iterrows():
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

    nodes_avec_contact = set()
    arêtes_contact_valides = []
    
    for u, v, data in G.edges(data=True):
        types = data.get("link_types", set())
        contact_types = types - {"transaction"}
        if not contact_types: continue
        
        # Filtrer adresses internationales génériques (ex: 'zone internationale')
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
    
    nb_frs = df_tx["fournisseur_suspect_collusion"].value_counts().get("oui", 0)
    print(f"   ✓ {nb_frs:,} transaction(s) impliquant un fournisseur en collusion")
    
    return df_tx

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")
    OUTPUT_DIR = os.path.join(BASE_DIR, "../../output_clean")
    
    print("=" * 60)
    print("  DÉTECTION DE FRAUDE — GRAPHE DE COLLUSION (Niveau 3)")
    print("=" * 60)
    
    transactions = pd.read_csv(os.path.join(OUTPUT_DIR, "transactions_scorees_ml.csv"), parse_dates=["date_transaction"])
    fournisseurs = pd.read_csv(os.path.join(OUTPUT_DIR, "fournisseurs_clean.csv"))
    employes = pd.read_csv(os.path.join(OUTPUT_DIR, "employes_clean.csv"))
    
    transactions = detecter_collusion_graphe(transactions, fournisseurs, employes)
    
    transactions.to_csv(os.path.join(OUTPUT_DIR, "scores_collusion.csv"), index=False)
    print(f"\n💾 Export sauvegardé sous output_clean/scores_collusion.csv")
