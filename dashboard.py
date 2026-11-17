"""Dashboard Streamlit : lancer avec `streamlit run dashboard.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import plotly.express as px
import streamlit as st

from avis_pipeline import analyse, ia, stockage

st.set_page_config(page_title="Dashboard avis", layout="wide")
st.title("Dashboard d'analyse d'avis")


@st.cache_data
def charger():
    """Charge les avis et calcule les sentiments (mis en cache)."""
    return analyse.ajouter_sentiments(stockage.charger_avis())


df = charger()
if df.empty:
    st.warning("Base vide. Lancez : python -m avis_pipeline.cli --demo")
    st.stop()

# --- Filtres latéraux ---
st.sidebar.header("Filtres")
sources = st.sidebar.multiselect("Source", sorted(df["source"].unique()), default=sorted(df["source"].unique()))
entreprises = st.sidebar.multiselect("Entreprise", sorted(df["entreprise"].unique()), default=sorted(df["entreprise"].unique()))
debut, fin = st.sidebar.date_input("Période", (df["date"].min().date(), df["date"].max().date()))
notes = st.sidebar.slider("Note (réelle ou estimée)", 1.0, 5.0, (1.0, 5.0), step=0.5)

filtre = df[df["source"].isin(sources) & df["entreprise"].isin(entreprises)
            & df["date"].between(str(debut), str(fin)) & df["note_finale"].between(*notes)]

col1, col2, col3 = st.columns(3)
col1.metric("Avis", len(filtre))
col2.metric("Note moyenne", f"{filtre['note_finale'].mean():.2f}" if len(filtre) else "–")
col3.metric("Sentiment moyen (VADER)", f"{filtre['sentiment_vader'].mean():.2f}" if len(filtre) else "–")

g1, g2 = st.columns(2)
g1.plotly_chart(px.histogram(filtre, x="note_finale", nbins=9, color="entreprise", barmode="group",
                             title="Distribution des notes (estimées si absentes)"), width="stretch")
g2.plotly_chart(px.line(analyse.evolution_mensuelle(filtre), x="mois", y="note_moyenne", color="entreprise",
                        title="Évolution mensuelle de la note moyenne"), width="stretch")

mots = analyse.top_mots(filtre["texte"], 15)
st.plotly_chart(px.bar(x=[m for m, _ in mots], y=[c for _, c in mots],
                       labels={"x": "Mot", "y": "Occurrences"}, title="Mots les plus fréquents"),
                width="stretch")

st.subheader("Nuage de mots")
st.image(analyse.nuage_de_mots(filtre["texte"]))
st.subheader("Synthèse IA")
st.write(ia.synthese_hebdo(filtre))
st.subheader("Corrélation sentiment / note")
st.dataframe(analyse.comparer_methodes(filtre).rename("corrélation"))
st.dataframe(filtre.sort_values("date", ascending=False).head(100))
