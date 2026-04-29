import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from urllib.parse import quote
from datetime import datetime, timezone

# --- CONFIGURATION DE L'INTERFACE STREAMLIT ---
st.set_page_config(page_title="Albion Market Terminal", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Times New Roman', Times, serif !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Terminal de Faction : Arbitrage et Forge")

# --- BARRE LATERALE ---
st.sidebar.header("Configuration du Convoi")
capacite_monture = st.sidebar.number_input("Capacite monture (kg)", value=1620)
heures_fraicheur = st.sidebar.slider("Fraicheur des donnees max (Heures)", 1, 48, 3)
premium = st.sidebar.checkbox("J'ai le Premium (Taxe 4%)", value=False)
min_profit = st.sidebar.number_input("Profit Net Minimum / Objet (Arbitrage classique)", value=10000)
min_profit_res = st.sidebar.number_input("Profit Net Minimum / Voyage (Ressources)", value=100000)
min_volume = st.sidebar.number_input("Volume Moyen Minimum / Jour", value=1)
webhook_discord = st.sidebar.text_input("URL Webhook Discord (Optionnel)", type="password")

TAXE = 0.04 if premium else 0.08
TAXE_ACHAT_DIRECT = 0.0  # Pour l'arbitrage inter-villes (achat via Buy Order ou achat direct)
QUALITES = "1,2,3,4"
JOURS = 30
DICO_QUALITES = {1: "Normal", 2: "Bon", 3: "Exceptionnel", 4: "Excellent", 5: "Chef-d'oeuvre"}
VILLES_ACHAT = ["Caerleon", "Bridgewatch", "Martlock", "Lymhurst", "Fort Sterling", "Thetford"]
MARCHE_NOIR  = "Black Market"

# --- CONSTANTES GLOBALES (Generation dynamique) ---
TIERS = ['T4', 'T5', 'T6', 'T7', 'T8']
ENCHANTS = ['', '@1', '@2', '@3', '@4']

# Onglet 1 : Capes et Sacs
FACTIONS = ['HERETIC', 'UNDEAD', 'KEEPER', 'MORGANA', 'DEMON', 'AVALON', 'SMUGGLER']
ITEMS_BAGS = [f"{t}_BAG{e}" for t in TIERS for e in ENCHANTS]
ITEMS_SATCHELS = [f"{t}_BAG_INSIGHT{e}" for t in TIERS for e in ENCHANTS]
ITEMS_CAPES = [f"{t}_CAPEITEM_{f}{e}" for t in TIERS for f in FACTIONS for e in ENCHANTS]
ITEMS_TAB1 = ITEMS_BAGS + ITEMS_SATCHELS + ITEMS_CAPES

POIDS_OBJETS = {'T4': 1.1, 'T5': 1.6, 'T6': 2.2, 'T7': 3.1, 'T8': 4.2}

# Onglet 2 : Forge
PARTIES = ['HEAD', 'ARMOR', 'SHOES']
MATERIAUX = ['LEATHER', 'CLOTH', 'PLATE']
ITEMS_BASES  = [f"{t}_{p}_{m}_SET1{e}" for t in TIERS for p in PARTIES for m in MATERIAUX for e in ENCHANTS]
ITEMS_ROYALS = [f"{t}_{p}_{m}_ROYAL{e}" for t in TIERS for p in PARTIES for m in MATERIAUX for e in ENCHANTS]
ITEMS_SIGILS = [f"QUESTITEM_TOKEN_ROYAL_{t}" for t in TIERS]
ITEMS_TAB2   = ITEMS_SIGILS + ITEMS_BASES + ITEMS_ROYALS

COUT_SIGILS = {
    'T4_HEAD': 2, 'T4_SHOES': 2, 'T4_ARMOR': 4,
    'T5_HEAD': 4, 'T5_SHOES': 4, 'T5_ARMOR': 8,
    'T6_HEAD': 8, 'T6_SHOES': 8, 'T6_ARMOR': 16,
    'T7_HEAD': 8, 'T7_SHOES': 8, 'T7_ARMOR': 16,
    'T8_HEAD': 8, 'T8_SHOES': 8, 'T8_ARMOR': 16,
}

# Onglet 3 : Ressources
ENCHANTS_RES = ['', '_LEVEL1', '_LEVEL2', '_LEVEL3', '_LEVEL4']
TYPES_RES = {
    'WOOD': 'Bois Brut', 'PLANKS': 'Planches',
    'HIDE': 'Peau Brute', 'LEATHER': 'Cuir',
    'FIBER': 'Fibre', 'CLOTH': 'Tissu',
    'ORE': 'Minerai', 'METALBAR': 'Lingot',
    'ROCK': 'Pierre', 'STONEBLOCK': 'Bloc de pierre'
}
ITEMS_TAB3 = [f"{t}_{res}{e}" for t in TIERS for res in TYPES_RES.keys() for e in ENCHANTS_RES]


# --- OUTILS COMMUNS ---
@st.cache_data(ttl=300)
def fetch_api_data(items_list, target_locations, include_history=False, history_location=MARCHE_NOIR):
    all_data, all_histo = [], []
    chunk_size = 60
    
    with requests.Session() as session:
        for i in range(0, len(items_list), chunk_size):
            chunk = items_list[i:i+chunk_size]
            items_str = ','.join(chunk)
            
            url_data = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={','.join(quote(l) for l in target_locations)}&qualities={QUALITES}"
            
            try:
                all_data.extend(session.get(url_data, timeout=15).json())
                
                if include_history:
                    url_histo = f"https://europe.albion-online-data.com/api/v2/stats/history/{items_str}?locations={quote(history_location)}&qualities={QUALITES}&time-scale=24"
                    all_histo.extend(session.get(url_histo, timeout=20).json())
            except Exception:
                pass
                
    return all_data, all_histo

def nettoyer_nom(item_id):
    nom = item_id.split("@")[0]
    nom = nom.replace("CAPEITEM_", "CAPE ")
    nom = nom.replace("BAG_INSIGHT", "SATCHEL")
    nom = nom.replace("_", " ")
    return nom

def extraire_tier(item_id):
    for t in TIERS:
        if t in item_id: return t
    return 'Inconnu'

tab1, tab2, tab3, tab4 = st.tabs(["Arbitrage : Capes & Sacs", "Forge Royale : Sigils", "Ressources & Raffinage", "📷 Scan de Marché"])

# ==========================================
# ONGLET 1 : ARBITRAGE (Vers Marche Noir)
# ==========================================
with tab1:
    @st.cache_data(ttl=300)
    def fetch_historique_item(item_id_raw, qualite, timescale=1, cutoff_jours=7):
        item_id = item_id_raw.split("@")[0]
        enchant = f"@{item_id_raw.split('@')[1]}" if "@" in item_id_raw else ""
        item_full = f"{item_id}{enchant}"
        url = f"https://europe.albion-online-data.com/api/v2/stats/history/{item_full}?locations={quote(MARCHE_NOIR)}&qualities={qualite}&time-scale={timescale}"
        
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data and data[0].get("data"):
                    df = pd.DataFrame(data[0]["data"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
                    df = df.sort_values("timestamp")
                    cutoff = pd.Timestamp.now() - pd.Timedelta(days=cutoff_jours)
                    return df[df["timestamp"] >= cutoff]
        except Exception:
            pass
        return pd.DataFrame()

    def afficher_graphique(item_id_raw, qualite, nom_affiche, prix_mn_actuel, timescale=1, cutoff_jours=7, hauteur=350, largeur=100):
        df_histo = fetch_historique_item(item_id_raw, qualite, timescale, cutoff_jours)

        if df_histo.empty:
            st.warning("Pas assez de donnees historiques pour cet objet.")
            return

        prix_moyen = int(df_histo["avg_price"].mean())
        fig = go.Figure()

        fig.add_hline(y=prix_mn_actuel, line_dash="solid", line_color="#e05252", annotation_text=f"Prix MN actuel: {prix_mn_actuel:,}", annotation_font_color="#e05252", annotation_position="right")
        fig.add_hline(y=prix_moyen, line_dash="dot", line_color="#c8a96e", annotation_text=f"Moyenne: {prix_moyen:,}", annotation_font_color="#c8a96e", annotation_position="left")

        fig.add_trace(go.Bar(x=df_histo["timestamp"], y=df_histo["item_count"], name="Volume", marker_color="rgba(180,120,60,0.3)", yaxis="y2"))
        fig.add_trace(go.Scatter(x=df_histo["timestamp"], y=df_histo["avg_price"], mode="lines+markers", name="Prix moyen historique", line=dict(color="#e8c97a", width=2), marker=dict(color="#e8c97a", size=8, symbol="circle", line=dict(color="#5c3d1e", width=2)), hovertemplate="<b>%{x|%d/%m %H:%M}</b><br>Prix: %{y:,.0f}<extra></extra>"))

        fig.update_layout(
            title=dict(text=f"Historique — {nom_affiche}", font=dict(color="#e8c97a", size=16)),
            paper_bgcolor="#2c1f0e", plot_bgcolor="#1e1408", font=dict(color="#c8a96e"),
            xaxis=dict(gridcolor="#3d2a10", tickformat="%d/%m %H:%M", showgrid=True, rangeslider=dict(visible=True, bgcolor="#1e1408", thickness=0.05)),
            yaxis=dict(gridcolor="#3d2a10", tickformat=",.0f", title="Prix (Silver)"),
            yaxis2=dict(overlaying="y", side="right", title="Volume", showgrid=False),
            legend=dict(bgcolor="rgba(0,0,0,0)"), hovermode="x unified", height=hauteur, margin=dict(l=60, r=60, t=50, b=40)
        )
        
        if largeur == 100:
            st.plotly_chart(fig, use_container_width=True)
        else:
            col_graph, _ = st.columns([largeur, 100 - largeur])
            with col_graph:
                st.plotly_chart(fig, use_container_width=True)

    if "df_resultats_tab1" not in st.session_state:
        st.session_state.df_resultats_tab1 = None

    if st.button("Lancer l'Analyse Arbitrage", use_container_width=True):
        with st.spinner("Extraction des donnees en cours..."):
            
            # On recupere les donnees des villes ET du Marche Noir
            locations_all = VILLES_ACHAT + [MARCHE_NOIR]
            data_all, data_histo = fetch_api_data(ITEMS_TAB1, target_locations=locations_all, include_history=True, history_location=MARCHE_NOIR)

            volumes = {}
            for bloc in data_histo:
                if not bloc.get("data"): continue
                df_tmp = pd.DataFrame(bloc["data"]).sort_values("timestamp", ascending=False).head(JOURS)
                volumes[(bloc["item_id"], bloc["quality"])] = round(df_tmp["item_count"].mean())

            maintenant = datetime.now(timezone.utc)
            prix_villes = {}
            prix_mn = {}
            
            for entry in data_all:
                if entry["city"] == MARCHE_NOIR:
                    if entry["buy_price_max"] > 0:
                        prix_mn[(entry["item_id"], entry["quality"])] = entry["buy_price_max"]
                else:
                    if entry["sell_price_min"] > 0:
                        date_brute = entry.get("sell_price_min_date", "")
                        age_heures = 999
                        if date_brute and not date_brute.startswith("0001"):
                            date_api = datetime.strptime(date_brute, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                            age_heures = (maintenant - date_api).total_seconds() / 3600
                        if age_heures <= heures_fraicheur:
                            key = (entry["item_id"], entry["quality"])
                            existant = prix_villes.get(key, {})
                            if not existant or entry["sell_price_min"] < existant.get("prix", float("inf")):
                                prix_villes[key] = {
                                    "prix": entry["sell_price_min"],
                                    "buy_order_local": entry["buy_price_max"],
                                    "ville": entry["city"],
                                    "age_h": round(age_heures, 1),
                                    "item_id_raw": entry["item_id"]
                                }

            lignes = []
            for key, achat_data in prix_villes.items():
                item_id, qualite = key
                
                # --- LOGIQUE : Qualité égale ou inférieure ---
                vente_mn = 0
                qualite_cible_int = qualite 
                
                for q in range(1, qualite + 1):
                    prix_q_mn = prix_mn.get((item_id, q), 0)
                    if prix_q_mn >= vente_mn: 
                        vente_mn = prix_q_mn
                        qualite_cible_int = q
                
                # On récupère le nom de la qualité cible (ex: "Normal")
                qualite_vendable_nom = DICO_QUALITES.get(qualite_cible_int, qualite_cible_int)
                # ----------------------------------------------
                
                volume = volumes.get((item_id, qualite_cible_int), 0)
                
                if not vente_mn or volume < min_volume: continue
                
                achat = achat_data["prix"]
                vente_net = vente_mn * (1 - TAXE)
                profit = round(vente_net - achat)
                if profit < min_profit: continue
                
                tier = item_id[:2]
                poids_u = POIDS_OBJETS.get(tier, 2.0)
                qte_max = int(capacite_monture / poids_u)
                
                lignes.append({
                    "Objet": nettoyer_nom(item_id),
                    "_item_id_raw": achat_data["item_id_raw"],
                    "_qualite_int": qualite,
                    "Enchant": item_id.split("@")[1] if "@" in item_id else "0",
                    "Qualite": DICO_QUALITES.get(qualite, qualite),
                    "Ville": achat_data["ville"],
                    "Achat": achat,
                    "Buy Order Ville": achat_data["buy_order_local"],
                    "Vente (MN)": vente_mn,
                    "Qualité Vendable": qualite_vendable_nom, # <-- Nouvelle colonne
                    "Profit Net": profit,
                    "Profit TRAJET": profit * qte_max,
                    "Score Liquidite": profit * volume,
                    "Vol/J": volume,
                    "Stabilite %": round((1 - (volume / (volume + 250))) * 100),
                    "Fraicheur": f"{achat_data['age_h']} h",
                })

            if not lignes:
                st.warning(f"Aucune opportunite fraiche (<{heures_fraicheur}h) repondant aux criteres.")
            else:
                df = pd.DataFrame(lignes).sort_values("Profit TRAJET", ascending=False).reset_index(drop=True)
                df.index += 1
                st.session_state.df_resultats_tab1 = df

    if st.session_state.df_resultats_tab1 is not None:
        df = st.session_state.df_resultats_tab1.copy()
        
        # --- 1. FILTRES LOCAUX (Sans appel API) ---
        st.markdown("### 🎛️ Filtres Rapides")
        
        # Création d'une colonne Tier pour le filtrage
        df['Tier'] = df['_item_id_raw'].apply(lambda x: x[:2])
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            tiers_uniques = sorted(df['Tier'].unique().tolist())
            tiers_selectionnes = st.multiselect("Filtrer par Tier", options=tiers_uniques, default=tiers_uniques)
        with col_f2:
            enchants_uniques = sorted(df['Enchant'].astype(str).unique().tolist())
            enchants_selectionnes = st.multiselect("Filtrer par Enchantement", options=enchants_uniques, default=enchants_uniques)

        # Application des filtres sur le dataframe
        df_filtre = df[(df['Tier'].isin(tiers_selectionnes)) & (df['Enchant'].astype(str).isin(enchants_selectionnes))].copy()

        # --- 2. INDICATEURS VISUELS (KPIs) ---
        st.markdown("---")
        if df_filtre.empty:
            st.warning("Aucun objet ne correspond à ces filtres.")
        else:
            top = df_filtre.iloc[0] # Récupération de la meilleure ligne après filtrage
            
            st.markdown("### 🏆 Meilleure Opportunité Actuelle")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            # Utilisation de st.metric avec le delta pour donner du contexte visuel
            kpi1.metric(
                label="Objet à cibler", 
                value=f"{top['Objet']}", 
                delta=f"{top['Ville']} ➔ Marche Noir",
                delta_color="off" # Gris, car c'est une information, pas une hausse/baisse
            )
            kpi2.metric(
                label="Profit Unitaire Net", 
                value=f"{top['Profit Net']:,.0f} 🥈", 
                delta=f"Stabilité: {top['Stabilite %']}%"
            )
            kpi3.metric(
                label="Profit Trajet (Monture pleine)", 
                value=f"{top['Profit TRAJET']:,.0f} 🥈", 
                delta="Volume dispo" if top['Vol/J'] > 10 else "Faible Volume",
                delta_color="normal" if top['Vol/J'] > 10 else "inverse"
            )
            kpi4.metric(
                label="Investissement Unitaire", 
                value=f"{top['Achat']:,.0f} 🥈",
                delta=f"{top['Qualite']} (E{top['Enchant']})",
                delta_color="off"
            )

            # --- 3. AFFICHAGE DU TABLEAU FILTRÉ ---
            st.success(f"{len(df_filtre)} opportunités trouvées avec ces filtres.")
            
            # Ajout de "Qualité Vendable" après "Vente (MN)"
            cols_affichage = [
                "Objet", "Tier", "Enchant", "Qualite", "Ville", "Achat", 
                "Buy Order Ville", "Vente (MN)", "Qualité Vendable", 
                "Profit Net", "Profit TRAJET", "Vol/J", "Stabilite %", "Fraicheur"
            ]
            
            df_affiche = df_filtre[cols_affichage].copy()
            
            # Formatage esthétique pour le tableau Streamlit
            for col in ["Achat", "Buy Order Ville", "Vente (MN)", "Profit Net", "Profit TRAJET"]:
                df_affiche[col] = df_affiche[col].fillna(0).map("{:,.0f}".format)

            st.dataframe(df_affiche, use_container_width=True, height=400)

            # --- GESTION DU WEBHOOK DISCORD BASÉ SUR LE FILTRE ---
            if webhook_discord:
                if st.button("Alerter sur Discord", type="primary"):
                    msg = {
                        "content": f"**[ALERTE ARBITRAGE]**\n"
                                   f"📦 **Objet :** {top['Objet']} (Tier {top['Tier']}, E{top['Enchant']}, {top['Qualite']})\n"
                                   f"🗺️ **Trajet :** {top['Ville']} ➔ Marché Noir\n"
                                   f"💰 **Profit Total :** {top['Profit TRAJET']:,.0f} Silver\n"
                                   f"📈 **Volume :** {top['Vol/J']}/jour"
                    }
                    requests.post(webhook_discord, json=msg)
                    st.success("Alerte envoyée avec succès sur Discord.")
# ==========================================
# ONGLET 2 : FORGE ROYALE
# ==========================================
with tab2:
    st.write("Calcul des marges de forge optimisees (Achat Base et Sigils inter-villes, Revente Marche Noir).")

    def traduire_nom_piece(item_id):
        nom = item_id.split('@')[0]
        nom = nom.replace("_SET1", "").replace("_ROYAL", " ROYAL")
        nom = nom.replace("HEAD", "Tete").replace("ARMOR", "Torse").replace("SHOES", "Bottes")
        nom = nom.replace("LEATHER", "Cuir").replace("CLOTH", "Tissu").replace("PLATE", "Plaques")
        return nom

    if st.button("Lancer l'Analyse Forge Optimisee", use_container_width=True):
        with st.spinner("Extraction des donnees de forge en cours..."):
            try:
                locations_all = VILLES_ACHAT + [MARCHE_NOIR]
                data_all, _ = fetch_api_data(ITEMS_TAB2, target_locations=locations_all, include_history=False)
                
                df_all = pd.DataFrame(data_all)

                if not df_all.empty:
                    df_all['tier'] = df_all['item_id'].apply(extraire_tier)
                    
                    df_villes = df_all[df_all['city'] != MARCHE_NOIR]
                    df_mn = df_all[df_all['city'] == MARCHE_NOIR]

                    df_sigils = df_villes[df_villes['item_id'].str.contains('TOKEN')][['tier','city','sell_price_min']]
                    df_sigils = df_sigils[df_sigils['sell_price_min'] > 0].rename(columns={'sell_price_min':'prix_sigil'})

                    df_bases = df_villes[df_villes['item_id'].str.contains('SET1')][['item_id','tier','quality','city','sell_price_min']]
                    df_bases = df_bases[df_bases['sell_price_min'] > 0].rename(columns={'sell_price_min':'prix_base'})

                    df_royals = df_mn[df_mn['item_id'].str.contains('ROYAL')][['item_id','tier','quality','buy_price_max']]
                    df_royals = df_royals[df_royals['buy_price_max'] > 0].rename(columns={'buy_price_max':'prix_vente_bm'})

                    best_sigils = df_sigils.loc[df_sigils.groupby('tier')['prix_sigil'].idxmin()] if not df_sigils.empty else pd.DataFrame()
                    best_bases  = df_bases.loc[df_bases.groupby(['item_id','quality'])['prix_base'].idxmin()] if not df_bases.empty else pd.DataFrame()

                    lignes_forge = []
                    if not best_bases.empty and not best_sigils.empty:
                        for _, base_row in best_bases.iterrows():
                            tier        = base_row['tier']
                            base_id     = base_row['item_id']
                            prix_base   = base_row['prix_base']
                            ville_base  = base_row['city']
                            qualite     = base_row['quality']
                            royal_id    = base_id.replace('SET1', 'ROYAL')
                            
                            sigil_row   = best_sigils[best_sigils['tier'] == tier]
                            royal_row   = df_royals[(df_royals['tier'] == tier) & (df_royals['item_id'] == royal_id) & (df_royals['quality'] == qualite)]
                            
                            if sigil_row.empty or royal_row.empty: continue
                            
                            prix_sigil    = sigil_row.iloc[0]['prix_sigil']
                            ville_sigil   = sigil_row.iloc[0]['city']
                            prix_vente_bm = royal_row.iloc[0]['prix_vente_bm']
                            piece_key     = f"{tier}_{base_id.split('_')[1]}"
                            nb_sigils     = COUT_SIGILS.get(piece_key, 8)
                            
                            cout_total    = prix_base + (prix_sigil * nb_sigils)
                            revenu_net    = prix_vente_bm * (1 - TAXE)
                            profit        = revenu_net - cout_total
                            rentabilite   = (profit / cout_total) * 100 if cout_total > 0 else 0
                            enchantement  = base_id.split('@')[1] if '@' in base_id else '0'
                            
                            lignes_forge.append({
                                "Piece":            traduire_nom_piece(royal_id),
                                "Enchant":          enchantement,
                                "Qualite":          DICO_QUALITES.get(qualite, qualite),
                                "Ville Base":       ville_base,
                                "Prix Base":        prix_base,
                                "Ville Sigils":     ville_sigil,
                                "Prix 1 Sigil":     prix_sigil,
                                "Nb Sigils":        nb_sigils,
                                "Cout Fabrication": cout_total,
                                "Revente MN":       prix_vente_bm,
                                "Profit Net":       profit,
                                "Rentabilite %":    round(rentabilite, 1),
                            })

                    if not lignes_forge:
                        st.warning("Aucune donnee de forge trouvee.")
                    else:
                        df_forge = pd.DataFrame(lignes_forge).sort_values("Profit Net", ascending=False).head(25).reset_index(drop=True)
                        df_forge.index += 1
                        st.success("Top 25 des operations de forge.")
                        for col in ["Prix Base", "Prix 1 Sigil", "Cout Fabrication", "Revente MN", "Profit Net"]:
                            df_forge[col] = df_forge[col].map("{:,.0f}".format)
                        st.dataframe(df_forge, use_container_width=True, height=500)

            except Exception as e:
                st.error(f"Erreur : {e}")

# ==========================================
# ONGLET 3 : RESSOURCES (Inter-Villes uniquement)
# ==========================================
with tab3:
    st.write("Analyse d'arbitrage de ressources brutes et raffinees **entre les villes royales** (Achat au moins cher, Vente au plus cher).")
    
    def formater_nom_res(item_id):
        parts = item_id.split('_')
        t = parts[0]
        enc = ".0"
        if "LEVEL" in item_id:
            enc = "." + item_id.split("LEVEL")[1]
        
        for k, v in TYPES_RES.items():
            if k in item_id:
                return f"{t} {v} {enc}"
        return item_id

    if st.button("Lancer l'Analyse Ressources Inter-Villes", use_container_width=True):
        with st.spinner("Analyse des flux de ressources entre les villes..."):
            try:
                # On ne requete QUE les villes d'achat (pas le Marche Noir)
                data_villes, _ = fetch_api_data(ITEMS_TAB3, target_locations=VILLES_ACHAT, include_history=False)
                
                maintenant = datetime.now(timezone.utc)
                offres = []
                
                # Consolider toutes les donnees valides
                for entry in data_villes:
                    date_sell = entry.get("sell_price_min_date", "")
                    age_sell = 999
                    if date_sell and not date_sell.startswith("0001"):
                        age_sell = (maintenant - datetime.strptime(date_sell, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds()/3600
                        
                    date_buy = entry.get("buy_price_max_date", "")
                    age_buy = 999
                    if date_buy and not date_buy.startswith("0001"):
                        age_buy = (maintenant - datetime.strptime(date_buy, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds()/3600

                    offres.append({
                        "item_id": entry["item_id"],
                        "city": entry["city"],
                        "sell_price": entry["sell_price_min"],
                        "age_sell": age_sell,
                        "buy_price": entry["buy_price_max"],
                        "age_buy": age_buy
                    })
                
                df_offres = pd.DataFrame(offres)
                
                lignes_res = []
                # Analyser chaque ressource pour trouver le meilleur trajet
                for item_id in df_offres['item_id'].unique():
                    df_item = df_offres[df_offres['item_id'] == item_id]
                    
                    # On cherche la ville ou l'objet est vendu le moins cher (donnee fraiche requise)
                    vendeurs = df_item[(df_item['sell_price'] > 0) & (df_item['age_sell'] <= heures_fraicheur)]
                    # On cherche la ville ou des joueurs ont place des Buy Orders le plus haut (donnee fraiche requise)
                    acheteurs = df_item[(df_item['buy_price'] > 0) & (df_item['age_buy'] <= heures_fraicheur)]
                    
                    if not vendeurs.empty and not acheteurs.empty:
                        meilleur_achat = vendeurs.loc[vendeurs['sell_price'].idxmin()]
                        meilleur_vente = acheteurs.loc[acheteurs['buy_price'].idxmax()]
                        
                        ville_achat = meilleur_achat['city']
                        ville_vente = meilleur_vente['city']
                        
                        # Si la meilleure ville de vente est la meme que la ville d'achat, on ignore (pas de trajet)
                        # Sauf si on veut faire du flip local (acheter a l'HV et revendre en Buy Order immediatement)
                        if ville_achat != ville_vente:
                            prix_achat = meilleur_achat['sell_price']
                            prix_vente = meilleur_vente['buy_price']
                            
                            # La taxe de vente standard s'applique sur les Buy Orders si on vend de facon limitee (ou on paie le setup)
                            # Ici on simplifie: Vendre a un Buy Order existant paie la taxe premium/non-premium
                            profit_unitaire = (prix_vente * (1 - TAXE)) - prix_achat
                            
                            # On determine le poids grossier
                            poids_u = 1.0 if any(brute in item_id for brute in ['WOOD', 'HIDE', 'FIBER', 'ORE', 'ROCK']) else 0.5
                            qte_max = int(capacite_monture / poids_u)
                            
                            profit_voyage = profit_unitaire * qte_max
                            
                            if profit_voyage >= min_profit_res:
                                lignes_res.append({
                                    "Ressource": formater_nom_res(item_id),
                                    "Ville Achat": ville_achat,
                                    "Prix Achat": prix_achat,
                                    "Ville Vente": ville_vente,
                                    "Buy Order": prix_vente,
                                    "Profit / Unite": round(profit_unitaire, 1),
                                    "Marge Trajet (Boeuf)": round(profit_voyage),
                                    "Age Donnees": f"A:{round(meilleur_achat['age_sell'],1)}h / V:{round(meilleur_vente['age_buy'],1)}h"
                                })
                
                if lignes_res:
                    df_res_final = pd.DataFrame(lignes_res).sort_values("Marge Trajet (Boeuf)", ascending=False).reset_index(drop=True)
                    df_res_final.index += 1
                    
                    st.success(f"{len(df_res_final)} trajets de ressources rentables trouves entre les villes.")
                    
                    df_style_res = df_res_final.copy()
                    for col in ["Prix Achat", "Buy Order", "Profit / Unite", "Marge Trajet (Boeuf)"]:
                        df_style_res[col] = df_style_res[col].map("{:,.0f}".format)
                        
                    st.dataframe(df_style_res, use_container_width=True, height=500)
                    
                    top_res = df_res_final.iloc[0]
                    if webhook_discord:
                        if st.button("Alerter sur Discord (Ressources)", type="primary"):
                            msg = {"content": f"**ALERTE CONVOI RESSOURCES**\nObjet: {top_res['Ressource']}\nTrajet: {top_res['Ville Achat']} -> {top_res['Ville Vente']}\nProfit Total Estime: {top_res['Marge Trajet (Boeuf)']:,.0f} Silver"}
                            requests.post(webhook_discord, json=msg)
                            st.success("Alerte convoyeur envoyee.")
                else:
                    st.warning("Aucune route commerciale de ressources n'atteint le profit minimum specifie.")
                    
            except Exception as e:
                st.error(f"Erreur lors de l'analyse des ressources : {e}")
                # ==========================================
# ONGLET 4 : SCAN DE CAPTURE D'ÉCRAN
# ==========================================
with tab4:
    st.markdown("### 📷 Extraction de données via Capture d'Écran")
    st.write("Uploadez une capture d'écran du marché d'Albion Online pour la convertir en tableau.")
    
    # Widget d'upload d'image
    fichier_image = st.file_uploader("Choisissez une image (PNG, JPG)", type=["png", "jpg", "jpeg"])
    
    if fichier_image is not None:
        # Affichage de l'image uploadée
        st.image(fichier_image, caption="Capture d'écran à analyser", width=600)
        
        if st.button("Lancer l'extraction des données", use_container_width=True):
            with st.spinner("Analyse de l'image en cours... Cela peut prendre quelques secondes."):
                
                # -------------------------------------------------------------
                # C'EST ICI QUE LA MAGIE DOIT OPÉRER (Appel au moteur de lecture)
                # -------------------------------------------------------------
                
                # Exemple de données simulées que votre moteur OCR/IA devrait retourner
                # (À remplacer par votre vrai script d'extraction)
                donnees_extraites = [
                    {"Objet": "T4 Tissu", "Qualité": "Normal", "Prix": 150, "Quantité": 999},
                    {"Objet": "T5 Bois", "Qualité": "Normal", "Prix": 450, "Quantité": 500}
                ]
                
                df_scan = pd.DataFrame(donnees_extraites)
                
                # -------------------------------------------------------------
                
                if not df_scan.empty:
                    st.success("Extraction réussie !")
                    st.dataframe(df_scan, use_container_width=True)
                    
                    # Option pour télécharger le tableau en CSV
                    csv = df_scan.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Télécharger en CSV",
                        data=csv,
                        file_name='donnees_marche.csv',
                        mime='text/csv',
                    )
                else:
                    st.error("Aucune donnée lisible n'a été trouvée sur cette image.")
