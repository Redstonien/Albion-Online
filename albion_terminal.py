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
min_profit = st.sidebar.number_input("Profit Net Minimum / Objet", value=10000)
min_volume = st.sidebar.number_input("Volume Moyen Minimum / Jour", value=1)
webhook_discord = st.sidebar.text_input("URL Webhook Discord (Optionnel)", type="password")

TAXE = 0.04 if premium else 0.08
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

# --- OUTILS COMMUNS ---
@st.cache_data(ttl=300)
def fetch_api_data(items_list, include_history=False):
    all_villes, all_mn, all_histo = [], [], []
    chunk_size = 60
    
    with requests.Session() as session:
        for i in range(0, len(items_list), chunk_size):
            chunk = items_list[i:i+chunk_size]
            items_str = ','.join(chunk)
            
            url_villes = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={','.join(quote(l) for l in VILLES_ACHAT)}&qualities={QUALITES}"
            url_mn     = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={quote(MARCHE_NOIR)}&qualities={QUALITES}"
            
            try:
                all_villes.extend(session.get(url_villes, timeout=15).json())
                all_mn.extend(session.get(url_mn, timeout=15).json())
                
                if include_history:
                    url_histo = f"https://europe.albion-online-data.com/api/v2/stats/history/{items_str}?locations={quote(MARCHE_NOIR)}&qualities={QUALITES}&time-scale=24"
                    all_histo.extend(session.get(url_histo, timeout=20).json())
            except Exception:
                pass
                
    return all_villes, all_mn, all_histo

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

tab1, tab2 = st.tabs(["Arbitrage : Capes & Sacs", "Forge Royale : Sigils"])

# ==========================================
# ONGLET 1 : ARBITRAGE
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

    if "df_resultats" not in st.session_state:
        st.session_state.df_resultats = None

    if st.button("Lancer l'Analyse Arbitrage", use_container_width=True):
        with st.spinner("Extraction des donnees en cours..."):
            data_villes, data_mn, data_histo = fetch_api_data(ITEMS_TAB1, include_history=True)

            volumes = {}
            for bloc in data_histo:
                if not bloc.get("data"): continue
                df_tmp = pd.DataFrame(bloc["data"]).sort_values("timestamp", ascending=False).head(JOURS)
                volumes[(bloc["item_id"], bloc["quality"])] = round(df_tmp["item_count"].mean())

            maintenant = datetime.now(timezone.utc)
            prix_villes = {}
            for entry in data_villes:
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

            prix_mn = {(e["item_id"], e["quality"]): e["buy_price_max"] for e in data_mn if e["buy_price_max"] > 0}

            lignes = []
            for key, achat_data in prix_villes.items():
                item_id, qualite = key
                vente_mn = prix_mn.get(key)
                volume = volumes.get(key, 0)
                
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
                st.session_state.df_resultats = df

    if st.session_state.df_resultats is not None:
        df = st.session_state.df_resultats
        st.success(f"{len(df)} opportunites trouvees.")

        cols_affichage = ["Objet", "Enchant", "Qualite", "Ville", "Achat", "Buy Order Ville", "Vente (MN)", "Profit Net", "Profit TRAJET", "Score Liquidite", "Vol/J", "Stabilite %", "Fraicheur"]
        
        df_affiche = df[cols_affichage].copy()
        for col in ["Achat", "Buy Order Ville", "Vente (MN)", "Profit Net", "Profit TRAJET", "Score Liquidite"]:
            df_affiche[col] = df_affiche[col].fillna(0).map("{:,.0f}".format)

        st.dataframe(df_affiche, use_container_width=True, height=400)

        top = df.iloc[0]
        st.markdown("---")
        st.subheader("Meilleure opportunite de transport")
        st.write(f"**Objet :** {top['Objet']} | Enchant : {top['Enchant']} | {top['Qualite']}")
        st.write(f"**Achat :** {top['Ville']} pour {top['Achat']:,} silver")
        st.write(f"**Vente MN :** {top['Vente (MN)']:,} silver")
        st.write(f"**Profit Trajet :** {top['Profit TRAJET']:,} Silver")

        if webhook_discord:
            if st.button("Alerter sur Discord", type="primary"):
                msg = {"content": f"[ALERTE ARBITRAGE]\nObjet : {top['Objet']} (E{top['Enchant']}, {top['Qualite']})\nTrajet : {top['Ville']} -> Marche Noir\nProfit Total : {top['Profit TRAJET']:,} Silver\n(Volume : {top['Vol/J']}/jour)"}
                requests.post(webhook_discord, json=msg)
                st.success("Alerte envoyee.")

        st.markdown("---")
        st.subheader("Historique de prix")

        toutes_options = []
        for item_id_raw in ITEMS_TAB1:
            base = item_id_raw.split("@")[0]
            enchant = item_id_raw.split("@")[1] if "@" in item_id_raw else "0"
            nom_propre = nettoyer_nom(item_id_raw)
            for q_int, q_nom in DICO_QUALITES.items():
                toutes_options.append({
                    "label": f"{nom_propre}.{q_int}.{enchant}",
                    "item_id_raw": item_id_raw,
                    "qualite_int": q_int,
                    "nom_affiche": f"{nom_propre} (Q{q_int}, E{enchant})"
                })

        prix_mn_map = {(row["_item_id_raw"], row["_qualite_int"]): int(row["Vente (MN)"]) for _, row in df.iterrows()}
        labels_disponibles = [o["label"] for o in toutes_options]

        recherche = st.selectbox("Recherche : [ITEM].[Qualite].[Enchant]", options=[""] + labels_disponibles, format_func=lambda x: x if x else "Tape pour rechercher...")

        if recherche:
            opt = next((o for o in toutes_options if o["label"] == recherche), None)
            if opt:
                col_settings, _ = st.columns([1, 1])
                with col_settings:
                    hauteur_graphique = st.slider("Hauteur du graphique (px)", min_value=300, max_value=1500, value=350, step=50)
                    largeur_graphique = st.slider("Largeur du graphique (%)", min_value=50, max_value=100, value=100, step=5)
                    granularite = st.radio(
                        "Granularite du graphique", 
                        options=["1h (Dernieres 24h)", "1h (7 derniers jours)", "6h (30 derniers jours)", "24h (Long terme)"], 
                        horizontal=True
                    )
                
                # Integration de la nouvelle option (Dernieres 24h)
                if granularite.startswith("1h (Dernieres"): timescale, cutoff_jours = 1, 1
                elif granularite.startswith("1h (7"): timescale, cutoff_jours = 1, 7
                elif granularite.startswith("6h"): timescale, cutoff_jours = 6, 30
                else: timescale, cutoff_jours = 24, 900
                
                afficher_graphique(opt["item_id_raw"], opt["qualite_int"], opt["nom_affiche"], prix_mn_map.get((opt["item_id_raw"], opt["qualite_int"]), 0), timescale, cutoff_jours, hauteur_graphique, largeur_graphique)

# ==========================================
# ONGLET 2 : FORGE ROYALE
# ==========================================
with tab2:
    st.write("Calcul des marges de forge optimisees (Toutes pieces, tous enchantements).")

    def traduire_nom_piece(item_id):
        nom = item_id.split('@')[0]
        nom = nom.replace("_SET1", "").replace("_ROYAL", " ROYAL")
        nom = nom.replace("HEAD", "Tete").replace("ARMOR", "Torse").replace("SHOES", "Bottes")
        nom = nom.replace("LEATHER", "Cuir").replace("CLOTH", "Tissu").replace("PLATE", "Plaques")
        return nom

    if st.button("Lancer l'Analyse Forge Optimisee", use_container_width=True):
        with st.spinner("Extraction des donnees de forge en cours..."):
            data_villes, data_mn, _ = fetch_api_data(ITEMS_TAB2, include_history=False)
            
            df_villes = pd.DataFrame(data_villes)
            df_mn     = pd.DataFrame(data_mn)

            if not df_villes.empty and not df_mn.empty:
                df_villes['tier'] = df_villes['item_id'].apply(extraire_tier)
                df_mn['tier']     = df_mn['item_id'].apply(extraire_tier)

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
