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

# --- ONGLETS ---
tab1, tab2 = st.tabs(["Arbitrage : Capes & Sacs", "Forge Royale : Sigils"])

# ==========================================
# ONGLET 1 : CAPES ET SACS
# ==========================================
with tab1:
    POIDS_OBJETS = {'T4': 1.1, 'T5': 1.6, 'T6': 2.2, 'T7': 3.1, 'T8': 4.2}

    ITEMS_TAB1 = [
        "T4_BAG", "T4_BAG@1", "T4_BAG@2", "T4_BAG@3", "T4_BAG@4",
        "T5_BAG", "T5_BAG@1", "T5_BAG@2", "T5_BAG@3", "T5_BAG@4",
        "T6_BAG", "T6_BAG@1", "T6_BAG@2", "T6_BAG@3", "T6_BAG@4",
        "T7_BAG", "T7_BAG@1", "T7_BAG@2", "T7_BAG@3", "T7_BAG@4",
        "T8_BAG", "T8_BAG@1", "T8_BAG@2", "T8_BAG@3", "T8_BAG@4",
        "T4_BAG_INSIGHT", "T4_BAG_INSIGHT@1", "T4_BAG_INSIGHT@2", "T4_BAG_INSIGHT@3", "T4_BAG_INSIGHT@4",
        "T5_BAG_INSIGHT", "T5_BAG_INSIGHT@1", "T5_BAG_INSIGHT@2", "T5_BAG_INSIGHT@3", "T5_BAG_INSIGHT@4",
        "T6_BAG_INSIGHT", "T6_BAG_INSIGHT@1", "T6_BAG_INSIGHT@2", "T6_BAG_INSIGHT@3", "T6_BAG_INSIGHT@4",
        "T7_BAG_INSIGHT", "T7_BAG_INSIGHT@1", "T7_BAG_INSIGHT@2", "T7_BAG_INSIGHT@3", "T7_BAG_INSIGHT@4",
        "T8_BAG_INSIGHT", "T8_BAG_INSIGHT@1", "T8_BAG_INSIGHT@2", "T8_BAG_INSIGHT@3", "T8_BAG_INSIGHT@4",
        "T4_CAPEITEM_HERETIC", "T4_CAPEITEM_HERETIC@1", "T4_CAPEITEM_HERETIC@2", "T4_CAPEITEM_HERETIC@3", "T4_CAPEITEM_HERETIC@4",
        "T5_CAPEITEM_HERETIC", "T5_CAPEITEM_HERETIC@1", "T5_CAPEITEM_HERETIC@2", "T5_CAPEITEM_HERETIC@3", "T5_CAPEITEM_HERETIC@4",
        "T6_CAPEITEM_HERETIC", "T6_CAPEITEM_HERETIC@1", "T6_CAPEITEM_HERETIC@2", "T6_CAPEITEM_HERETIC@3", "T6_CAPEITEM_HERETIC@4",
        "T7_CAPEITEM_HERETIC", "T7_CAPEITEM_HERETIC@1", "T7_CAPEITEM_HERETIC@2", "T7_CAPEITEM_HERETIC@3", "T7_CAPEITEM_HERETIC@4",
        "T8_CAPEITEM_HERETIC", "T8_CAPEITEM_HERETIC@1", "T8_CAPEITEM_HERETIC@2", "T8_CAPEITEM_HERETIC@3", "T8_CAPEITEM_HERETIC@4",
        "T4_CAPEITEM_UNDEAD", "T4_CAPEITEM_UNDEAD@1", "T4_CAPEITEM_UNDEAD@2", "T4_CAPEITEM_UNDEAD@3", "T4_CAPEITEM_UNDEAD@4",
        "T5_CAPEITEM_UNDEAD", "T5_CAPEITEM_UNDEAD@1", "T5_CAPEITEM_UNDEAD@2", "T5_CAPEITEM_UNDEAD@3", "T5_CAPEITEM_UNDEAD@4",
        "T6_CAPEITEM_UNDEAD", "T6_CAPEITEM_UNDEAD@1", "T6_CAPEITEM_UNDEAD@2", "T6_CAPEITEM_UNDEAD@3", "T6_CAPEITEM_UNDEAD@4",
        "T7_CAPEITEM_UNDEAD", "T7_CAPEITEM_UNDEAD@1", "T7_CAPEITEM_UNDEAD@2", "T7_CAPEITEM_UNDEAD@3", "T7_CAPEITEM_UNDEAD@4",
        "T8_CAPEITEM_UNDEAD", "T8_CAPEITEM_UNDEAD@1", "T8_CAPEITEM_UNDEAD@2", "T8_CAPEITEM_UNDEAD@3", "T8_CAPEITEM_UNDEAD@4",
        "T4_CAPEITEM_KEEPER", "T4_CAPEITEM_KEEPER@1", "T4_CAPEITEM_KEEPER@2", "T4_CAPEITEM_KEEPER@3", "T4_CAPEITEM_KEEPER@4",
        "T5_CAPEITEM_KEEPER", "T5_CAPEITEM_KEEPER@1", "T5_CAPEITEM_KEEPER@2", "T5_CAPEITEM_KEEPER@3", "T5_CAPEITEM_KEEPER@4",
        "T6_CAPEITEM_KEEPER", "T6_CAPEITEM_KEEPER@1", "T6_CAPEITEM_KEEPER@2", "T6_CAPEITEM_KEEPER@3", "T6_CAPEITEM_KEEPER@4",
        "T7_CAPEITEM_KEEPER", "T7_CAPEITEM_KEEPER@1", "T7_CAPEITEM_KEEPER@2", "T7_CAPEITEM_KEEPER@3", "T7_CAPEITEM_KEEPER@4",
        "T8_CAPEITEM_KEEPER", "T8_CAPEITEM_KEEPER@1", "T8_CAPEITEM_KEEPER@2", "T8_CAPEITEM_KEEPER@3", "T8_CAPEITEM_KEEPER@4",
        "T4_CAPEITEM_MORGANA", "T4_CAPEITEM_MORGANA@1", "T4_CAPEITEM_MORGANA@2", "T4_CAPEITEM_MORGANA@3", "T4_CAPEITEM_MORGANA@4",
        "T5_CAPEITEM_MORGANA", "T5_CAPEITEM_MORGANA@1", "T5_CAPEITEM_MORGANA@2", "T5_CAPEITEM_MORGANA@3", "T5_CAPEITEM_MORGANA@4",
        "T6_CAPEITEM_MORGANA", "T6_CAPEITEM_MORGANA@1", "T6_CAPEITEM_MORGANA@2", "T6_CAPEITEM_MORGANA@3", "T6_CAPEITEM_MORGANA@4",
        "T7_CAPEITEM_MORGANA", "T7_CAPEITEM_MORGANA@1", "T7_CAPEITEM_MORGANA@2", "T7_CAPEITEM_MORGANA@3", "T7_CAPEITEM_MORGANA@4",
        "T8_CAPEITEM_MORGANA", "T8_CAPEITEM_MORGANA@1", "T8_CAPEITEM_MORGANA@2", "T8_CAPEITEM_MORGANA@3", "T8_CAPEITEM_MORGANA@4",
        "T4_CAPEITEM_DEMON", "T4_CAPEITEM_DEMON@1", "T4_CAPEITEM_DEMON@2", "T4_CAPEITEM_DEMON@3", "T4_CAPEITEM_DEMON@4",
        "T5_CAPEITEM_DEMON", "T5_CAPEITEM_DEMON@1", "T5_CAPEITEM_DEMON@2", "T5_CAPEITEM_DEMON@3", "T5_CAPEITEM_DEMON@4",
        "T6_CAPEITEM_DEMON", "T6_CAPEITEM_DEMON@1", "T6_CAPEITEM_DEMON@2", "T6_CAPEITEM_DEMON@3", "T6_CAPEITEM_DEMON@4",
        "T7_CAPEITEM_DEMON", "T7_CAPEITEM_DEMON@1", "T7_CAPEITEM_DEMON@2", "T7_CAPEITEM_DEMON@3", "T7_CAPEITEM_DEMON@4",
        "T8_CAPEITEM_DEMON", "T8_CAPEITEM_DEMON@1", "T8_CAPEITEM_DEMON@2", "T8_CAPEITEM_DEMON@3", "T8_CAPEITEM_DEMON@4",
        "T4_CAPEITEM_AVALON", "T4_CAPEITEM_AVALON@1", "T4_CAPEITEM_AVALON@2", "T4_CAPEITEM_AVALON@3", "T4_CAPEITEM_AVALON@4",
        "T5_CAPEITEM_AVALON", "T5_CAPEITEM_AVALON@1", "T5_CAPEITEM_AVALON@2", "T5_CAPEITEM_AVALON@3", "T5_CAPEITEM_AVALON@4",
        "T6_CAPEITEM_AVALON", "T6_CAPEITEM_AVALON@1", "T6_CAPEITEM_AVALON@2", "T6_CAPEITEM_AVALON@3", "T6_CAPEITEM_AVALON@4",
        "T7_CAPEITEM_AVALON", "T7_CAPEITEM_AVALON@1", "T7_CAPEITEM_AVALON@2", "T7_CAPEITEM_AVALON@3", "T7_CAPEITEM_AVALON@4",
        "T8_CAPEITEM_AVALON", "T8_CAPEITEM_AVALON@1", "T8_CAPEITEM_AVALON@2", "T8_CAPEITEM_AVALON@3", "T8_CAPEITEM_AVALON@4",
        "T4_CAPEITEM_SMUGGLER", "T4_CAPEITEM_SMUGGLER@1", "T4_CAPEITEM_SMUGGLER@2", "T4_CAPEITEM_SMUGGLER@3", "T4_CAPEITEM_SMUGGLER@4",
        "T5_CAPEITEM_SMUGGLER", "T5_CAPEITEM_SMUGGLER@1", "T5_CAPEITEM_SMUGGLER@2", "T5_CAPEITEM_SMUGGLER@3", "T5_CAPEITEM_SMUGGLER@4",
        "T6_CAPEITEM_SMUGGLER", "T6_CAPEITEM_SMUGGLER@1", "T6_CAPEITEM_SMUGGLER@2", "T6_CAPEITEM_SMUGGLER@3", "T6_CAPEITEM_SMUGGLER@4",
        "T7_CAPEITEM_SMUGGLER", "T7_CAPEITEM_SMUGGLER@1", "T7_CAPEITEM_SMUGGLER@2", "T7_CAPEITEM_SMUGGLER@3", "T7_CAPEITEM_SMUGGLER@4",
        "T8_CAPEITEM_SMUGGLER", "T8_CAPEITEM_SMUGGLER@1", "T8_CAPEITEM_SMUGGLER@2", "T8_CAPEITEM_SMUGGLER@3", "T8_CAPEITEM_SMUGGLER@4",
    ]

    @st.cache_data(ttl=300)
    def fetch_data_tab1():
        all_villes, all_mn, all_histo = [], [], []
        chunk_size = 70
        for i in range(0, len(ITEMS_TAB1), chunk_size):
            chunk = ITEMS_TAB1[i:i+chunk_size]
            items_str = ','.join(chunk)
            url_villes = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={','.join(quote(l) for l in VILLES_ACHAT)}&qualities={QUALITES}"
            url_mn     = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={quote(MARCHE_NOIR)}&qualities={QUALITES}"
            url_histo  = f"https://europe.albion-online-data.com/api/v2/stats/history/{items_str}?locations={quote(MARCHE_NOIR)}&qualities={QUALITES}&time-scale=24"
            all_villes.extend(requests.get(url_villes, timeout=20).json())
            all_mn.extend(requests.get(url_mn, timeout=20).json())
            all_histo.extend(requests.get(url_histo, timeout=30).json())
        return all_villes, all_mn, all_histo

    @st.cache_data(ttl=300)
    def fetch_historique_item(item_id_raw, qualite):
        item_id = item_id_raw.split("@")[0]
        enchant = f"@{item_id_raw.split('@')[1]}" if "@" in item_id_raw else ""
        item_full = f"{item_id}{enchant}"
        url = (
            f"https://europe.albion-online-data.com/api/v2/stats/history/{item_full}"
            f"?locations={quote(MARCHE_NOIR)}&qualities={qualite}&time-scale=6"
         )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
        if data and data[0].get("data"):
                df = pd.DataFrame(data[0]["data"])
                    # Conversion sans timezone pour eviter le conflit
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
                df = df.sort_values("timestamp")
                # Filtre 7 derniers jours sans timezone
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=7)
                df = df[df["timestamp"] >= cutoff]
            return df
        return pd.DataFrame()
    def nettoyer_nom(item_id):
        nom = item_id.split("@")[0]
        nom = nom.replace("CAPEITEM_", "CAPE ")
        nom = nom.replace("BAG_INSIGHT", "SATCHEL")
        nom = nom.replace("_", " ")
        return nom

    def afficher_graphique(item_id_raw, qualite, nom_affiche):
        """Affiche le graphique style Albion pour un item."""
        df_histo = fetch_historique_item(item_id_raw, qualite)

        if df_histo.empty:
            st.warning("Pas assez de données historiques pour cet objet.")
            return

        prix_moyen = int(df_histo["avg_price"].mean())

        fig = go.Figure()

        # Ligne de prix moyen
        fig.add_hline(
            y=prix_moyen,
            line_dash="dot",
            line_color="#c8a96e",
            annotation_text=f"Moy: {prix_moyen:,}",
            annotation_font_color="#c8a96e",
            annotation_position="right"
        )

        # Barres de volume
        fig.add_trace(go.Bar(
            x=df_histo["timestamp"],
            y=df_histo["item_count"],
            name="Volume",
            marker_color="rgba(180,120,60,0.3)",
            yaxis="y2",
        ))

        # Ligne de prix + points
        fig.add_trace(go.Scatter(
            x=df_histo["timestamp"],
            y=df_histo["avg_price"],
            mode="lines+markers",
            name="Prix moyen",
            line=dict(color="#e8c97a", width=2),
            marker=dict(
                color="#e8c97a",
                size=8,
                symbol="circle",
                line=dict(color="#5c3d1e", width=2)
            ),
            hovertemplate="<b>%{x|%d/%m %H:%M}</b><br>Prix: %{y:,.0f}<extra></extra>"
        ))

        fig.update_layout(
            title=dict(
                text=f"Historique 7 jours — {nom_affiche}",
                font=dict(color="#e8c97a", size=16)
            ),
            paper_bgcolor="#2c1f0e",
            plot_bgcolor="#1e1408",
            font=dict(color="#c8a96e"),
            xaxis=dict(
                gridcolor="#3d2a10",
                tickformat="%d/%m",
                showgrid=True,
            ),
            yaxis=dict(
                gridcolor="#3d2a10",
                tickformat=",.0f",
                title="Prix (Silver)",
                title_font=dict(color="#c8a96e"),
            ),
            yaxis2=dict(
                overlaying="y",
                side="right",
                title="Volume",
                title_font=dict(color="#c8a96e"),
                showgrid=False,
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c8a96e")
            ),
            hovermode="x unified",
            height=350,
            margin=dict(l=60, r=60, t=50, b=40),
        )

        st.plotly_chart(fig, use_container_width=True)

    # ── ÉTAT SESSION ──────────────────────────────────────────────────────────
    if "df_resultats" not in st.session_state:
        st.session_state.df_resultats = None
    if "item_selectionne" not in st.session_state:
        st.session_state.item_selectionne = None

    if st.button("Lancer l'Analyse Arbitrage", use_container_width=True):
        with st.spinner("Extraction des donnees en cours..."):
            try:
                data_villes, data_mn, data_histo = fetch_data_tab1()

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
                                    "ville": entry["city"],
                                    "age_h": round(age_heures, 1),
                                    "item_id_raw": entry["item_id"],
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
                        "Objet":           nettoyer_nom(item_id),
                        "_item_id_raw":    achat_data["item_id_raw"],
                        "_qualite_int":    qualite,
                        "Enchant":         item_id.split("@")[1] if "@" in item_id else "0",
                        "Qualite":         DICO_QUALITES.get(qualite, qualite),
                        "Ville":           achat_data["ville"],
                        "Achat":           achat,
                        "Vente (MN)":      vente_mn,
                        "Profit Net":      profit,
                        "Profit TRAJET":   profit * qte_max,
                        "Score Liquidite": profit * volume,
                        "Vol/J":           volume,
                        "Stabilite %":     round((1 - (volume / (volume + 250))) * 100),
                        "Fraicheur":       f"{achat_data['age_h']} h",
                    })

                if not lignes:
                    st.warning(f"Aucune opportunite fraiche (<{heures_fraicheur}h) repondant aux criteres.")
                else:
                    df = pd.DataFrame(lignes).sort_values("Profit TRAJET", ascending=False).reset_index(drop=True)
                    df.index += 1
                    st.session_state.df_resultats = df
                    st.session_state.item_selectionne = None

            except Exception as e:
                st.error(f"Erreur : {e}")

    # ── AFFICHAGE TABLEAU + GRAPHIQUE ─────────────────────────────────────────
    if st.session_state.df_resultats is not None:
        df = st.session_state.df_resultats

        st.success(f"{len(df)} opportunites trouvees.")

        # Colonnes visibles (sans les colonnes internes _)
        cols_affichage = ["Objet", "Enchant", "Qualite", "Ville", "Achat",
                          "Vente (MN)", "Profit Net", "Profit TRAJET",
                          "Score Liquidite", "Vol/J", "Stabilite %", "Fraicheur"]

        df_affiche = df[cols_affichage].copy()
        for col in ["Achat", "Vente (MN)", "Profit Net", "Profit TRAJET", "Score Liquidite"]:
            df_affiche[col] = df_affiche[col].map("{:,.0f}".format)

        # Sélecteur d'objet pour le graphique
        options = ["(Sélectionne un objet pour voir son graphique)"] + [
            f"{row['Objet']} E{row['Enchant']} — {row['Qualite']}"
            for _, row in df[cols_affichage].iterrows()
        ]
        choix = st.selectbox("Clique sur un objet pour afficher son historique de prix :", options)

        if choix != options[0]:
            idx = options.index(choix) - 1
            ligne = df.iloc[idx]
            item_id_raw = ligne["_item_id_raw"]
            qualite_int = ligne["_qualite_int"]
            nom_affiche = f"{ligne['Objet']} (E{ligne['Enchant']}, {ligne['Qualite']})"
            afficher_graphique(item_id_raw, qualite_int, nom_affiche)

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
                msg = {"content": f"[ALERTE ARBITRAGE]\nObjet : {top['Objet']} (E{top['Enchant']}, {top['Qualite']})\nTrajet : {top['Ville']} → Marché Noir\nProfit Total : {top['Profit TRAJET']:,} Silver\n(Volume : {top['Vol/J']}/jour)"}
                requests.post(webhook_discord, json=msg)
                st.success("Alerte envoyee.")

# ==========================================
# ONGLET 2 : FORGE ROYALE
# ==========================================
with tab2:
    st.write("Calcul des marges de forge optimisees (Tetes, Torses, Bottes - Tous Enchantements et Qualites).")

    TIERS = ['T4', 'T5', 'T6', 'T7', 'T8']
    PARTIES = ['HEAD', 'ARMOR', 'SHOES']
    MATERIAUX = ['LEATHER', 'CLOTH', 'PLATE']
    ENCHANTS = ['', '@1', '@2', '@3', '@4']

    COUT_SIGILS = {
        'T4_HEAD': 2, 'T4_SHOES': 2, 'T4_ARMOR': 4,
        'T5_HEAD': 4, 'T5_SHOES': 4, 'T5_ARMOR': 8,
        'T6_HEAD': 8, 'T6_SHOES': 8, 'T6_ARMOR': 16,
        'T7_HEAD': 8, 'T7_SHOES': 8, 'T7_ARMOR': 16,
        'T8_HEAD': 8, 'T8_SHOES': 8, 'T8_ARMOR': 16,
    }

    ITEMS_BASES  = [f"{t}_{p}_{m}_SET1{e}" for t in TIERS for p in PARTIES for m in MATERIAUX for e in ENCHANTS]
    ITEMS_ROYALS = [f"{t}_{p}_{m}_ROYAL{e}" for t in TIERS for p in PARTIES for m in MATERIAUX for e in ENCHANTS]
    ITEMS_SIGILS = [f"QUESTITEM_TOKEN_ROYAL_{t}" for t in TIERS]
    ITEMS_TAB2   = ITEMS_SIGILS + ITEMS_BASES + ITEMS_ROYALS

    @st.cache_data(ttl=300)
    def fetch_data_tab2():
        all_villes, all_mn = [], []
        chunk_size = 40
        for i in range(0, len(ITEMS_TAB2), chunk_size):
            chunk = ITEMS_TAB2[i:i+chunk_size]
            items_str = ','.join(chunk)
            url_villes = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={','.join(quote(l) for l in VILLES_ACHAT)}&qualities={QUALITES}"
            url_mn     = f"https://europe.albion-online-data.com/api/v2/stats/prices/{items_str}?locations={quote(MARCHE_NOIR)}&qualities={QUALITES}"
            try:
                res_v = requests.get(url_villes, timeout=15)
                res_m = requests.get(url_mn, timeout=15)
                if res_v.status_code == 200: all_villes.extend(res_v.json())
                if res_m.status_code == 200: all_mn.extend(res_m.json())
            except Exception:
                pass
        return all_villes, all_mn

    def extraire_tier(item_id):
        for t in TIERS:
            if t in item_id: return t
        return 'Inconnu'

    def traduire_nom_piece(item_id):
        nom = item_id.split('@')[0]
        nom = nom.replace("_SET1", "").replace("_ROYAL", " ROYAL")
        nom = nom.replace("HEAD", "Tete").replace("ARMOR", "Torse").replace("SHOES", "Bottes")
        nom = nom.replace("LEATHER", "Cuir").replace("CLOTH", "Tissu").replace("PLATE", "Plaques")
        return nom

    if st.button("Lancer l'Analyse Forge Optimisee", use_container_width=True):
        with st.spinner("Extraction des donnees de forge en cours..."):
            try:
                data_villes, data_mn = fetch_data_tab2()
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
                        for col in ["Prix Base","Prix 1 Sigil","Cout Fabrication","Revente MN","Profit Net"]:
                            df_forge[col] = df_forge[col].map("{:,.0f}".format)
                        st.dataframe(df_forge, use_container_width=True, height=500)

            except Exception as e:
                st.error(f"Erreur : {e}")
