"""Dashboard Streamlit : lancer avec `streamlit run dashboard.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

from avis_pipeline import analyse, ia, stockage

PALETTE = {"positif": "#2ecc9a", "neutre": "#8b93a7", "négatif": "#ff5c7a"}
SEQ = ["#7c5cff", "#2ec4ff", "#2ecc9a", "#ffb84d", "#ff5c7a", "#c77dff", "#4dd6c1"]

st.set_page_config(page_title="Observatoire d'avis", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
h1 {background: linear-gradient(90deg,#7c5cff,#2ec4ff); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; font-weight: 800;}
div[data-testid="stMetric"] {background:#1a1f2e; border:1px solid #2a3147; border-radius:14px;
    padding:14px 18px; box-shadow:0 2px 12px rgba(0,0,0,.25);}
div[data-testid="stMetricLabel"] {opacity:.7;}
button[data-baseweb="tab"] {font-weight:600;}
</style>""", unsafe_allow_html=True)


def style(fig, hauteur: int = 380):
    """Applique un style sombre cohérent à une figure Plotly."""
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=hauteur, margin=dict(l=10, r=10, t=50, b=10), colorway=SEQ,
                      legend=dict(orientation="h", y=-0.2))
    return fig


@st.cache_data(show_spinner="Analyse des messages…")
def charger() -> pd.DataFrame:
    """Charge la base, calcule sentiments et thèmes (mis en cache)."""
    df = analyse.ajouter_sentiments(stockage.charger_avis())
    return analyse.detecter_themes(df) if len(df) else df


df = charger()
st.title("📊 Observatoire d'avis")
st.caption("Pipeline Python : API publiques (Mastodon, Lemmy) → SQLite → pandas/NLP → Streamlit")
if df.empty:
    st.warning("Base vide. Lancez : `python -m avis_pipeline.cli` (ou `--demo`).")
    st.stop()

# ---------- Filtres ----------
with st.sidebar:
    st.header("🎛️ Filtres")
    sources = st.multiselect("Source", sorted(df["source"].unique()), default=sorted(df["source"].unique()))
    sujets = st.multiselect("Sujet", sorted(df["sujet"].unique()), default=sorted(df["sujet"].unique()))
    debut, fin = st.date_input("Période", (df["date"].min().date(), df["date"].max().date()))
    notes = st.slider("Note (réelle ou estimée)", 1.0, 5.0, (1.0, 5.0), step=0.5)
    types = st.multiselect("Type", sorted(df["type"].dropna().unique()), default=sorted(df["type"].dropna().unique()))
    mot = st.text_input("🔎 Mot-clé dans le texte")
    st.divider()
    st.caption("Notes estimées depuis le sentiment quand la source n'en fournit pas.")

f = df[df["source"].isin(sources) & df["sujet"].isin(sujets) & df["type"].isin(types)
       & df["date"].dt.date.between(debut, fin) & df["note_finale"].between(*notes)]
if mot:
    f = f[f["texte"].str.contains(mot, case=False, na=False)]
if f.empty:
    st.info("Aucun message ne correspond aux filtres.")
    st.stop()

# ---------- KPI ----------
part_neg = (f["categorie"] == "négatif").mean()
k = st.columns(5)
k[0].metric("Messages", f"{len(f):,}".replace(",", " "))
k[1].metric("Note moyenne", f"{f['note_finale'].mean():.2f} / 5")
k[2].metric("Messages négatifs", f"{part_neg:.0%}")
k[3].metric("Auteurs uniques", f["auteur"].nunique())
k[4].metric("Engagement total", f"{int(f['engagement'].sum()):,}".replace(",", " "))

for ligne in analyse.alertes(f).itertuples():
    st.error(f"🚨 Alerte : « {ligne.sujet} » a une note moyenne de {ligne.mean:.2f} ({ligne.count} messages)")

onglets = st.tabs(["🏠 Vue d'ensemble", "📈 Temporel", "💬 Textes & mots", "🧩 Thèmes", "👥 Auteurs", "🤖 IA", "🗂️ Explorer"])

with onglets[0]:
    a, b = st.columns(2)
    rep = f["categorie"].value_counts().reindex(["positif", "neutre", "négatif"]).fillna(0).reset_index()
    rep.columns = ["catégorie", "messages"]
    a.plotly_chart(style(px.pie(rep, names="catégorie", values="messages", hole=.55, color="catégorie",
                                color_discrete_map=PALETTE, title="Répartition du sentiment")), width="stretch")
    b.plotly_chart(style(px.histogram(f, x="note_finale", nbins=9, color="sujet",
                                      title="Distribution des notes", barmode="stack")), width="stretch")
    c, d = st.columns(2)
    vol = f.groupby(["sujet", "famille_source"]).size().reset_index(name="messages")
    c.plotly_chart(style(px.bar(vol, x="sujet", y="messages", color="famille_source",
                                title="Volume par sujet et source")), width="stretch")
    moy = f.groupby("sujet")["note_finale"].mean().sort_values().reset_index()
    d.plotly_chart(style(px.bar(moy, x="note_finale", y="sujet", orientation="h", color="note_finale",
                                color_continuous_scale=["#ff5c7a", "#ffb84d", "#2ecc9a"], range_color=[1, 5],
                                title="Note moyenne par sujet")), width="stretch")

with onglets[1]:
    freq = st.radio("Granularité", ["Semaine", "Mois", "Jour"], horizontal=True)
    code = {"Semaine": "W", "Mois": "M", "Jour": "D"}[freq]
    evo = analyse.evolution(f, code)
    a, b = st.columns(2)
    a.plotly_chart(style(px.line(evo, x="periode", y="note_moyenne", color="sujet", markers=True,
                                 title="Évolution de la note moyenne")), width="stretch")
    b.plotly_chart(style(px.area(evo, x="periode", y="nb_avis", color="sujet",
                                 title="Volume de messages")), width="stretch")
    heat = analyse.heatmap_activite(f)
    st.plotly_chart(style(px.imshow(heat, aspect="auto", color_continuous_scale="Purples",
                                    labels=dict(x="Heure", y="Jour", color="Messages"),
                                    title="Quand les gens s'expriment (jour × heure)"), 340), width="stretch")

with onglets[2]:
    a, b = st.columns(2)
    mots = analyse.top_mots(f["texte"], 20)
    a.plotly_chart(style(px.bar(x=[c for _, c in mots][::-1], y=[m for m, _ in mots][::-1], orientation="h",
                                labels={"x": "Occurrences", "y": ""}, title="Mots les plus fréquents"), 520),
                   width="stretch")
    bi = analyse.top_bigrammes(f["texte"], 20)
    b.plotly_chart(style(px.bar(x=[c for _, c in bi][::-1], y=[m for m, _ in bi][::-1], orientation="h",
                                labels={"x": "Occurrences", "y": ""}, title="Expressions fréquentes (2 mots)"), 520),
                   width="stretch")
    st.image(analyse.nuage_de_mots(f["texte"]))
    pos_neg = analyse.mots_par_sentiment(f)
    a, b = st.columns(2)
    for col, cat in ((a, "positif"), (b, "négatif")):
        col.markdown(f"**Mots des messages {cat}s**")
        col.write(", ".join(f"{m} ({n})" for m, n in pos_neg[cat]) or "–")
    st.plotly_chart(style(px.scatter(f, x="sentiment_naif", y="sentiment_vader", color="sujet", opacity=.6,
                                     hover_data=["texte"], title="Méthode naïve vs VADER (S6)")), width="stretch")
    st.caption("Corrélation naïf/VADER : " + ", ".join(f"{k}={v:.2f}" for k, v in analyse.comparer_methodes(f).items()))

with onglets[3]:
    th = f.groupby("theme").agg(messages=("id", "count"), note=("note_finale", "mean")).reset_index()
    a, b = st.columns(2)
    a.plotly_chart(style(px.treemap(th, path=["theme"], values="messages", color="note",
                                    color_continuous_scale=["#ff5c7a", "#ffb84d", "#2ecc9a"], range_color=[1, 5],
                                    title="Thèmes détectés (taille = volume, couleur = note)")), width="stretch")
    croise = f.groupby(["theme", "sujet"]).size().reset_index(name="messages")
    b.plotly_chart(style(px.bar(croise, x="messages", y="theme", color="sujet", orientation="h",
                                title="Thèmes par sujet")), width="stretch")
    choix = st.selectbox("Voir des exemples du thème", th["theme"])
    st.dataframe(f[f["theme"] == choix][["date", "sujet", "note_finale", "texte"]].head(15), hide_index=True)

with onglets[4]:
    a, b = st.columns(2)
    aut = analyse.top_auteurs(f, 15)
    a.plotly_chart(style(px.bar(aut, x="messages", y="auteur", orientation="h", color="sentiment",
                                color_continuous_scale=["#ff5c7a", "#8b93a7", "#2ecc9a"], range_color=[-1, 1],
                                title="Auteurs les plus actifs"), 480), width="stretch")
    b.plotly_chart(style(px.scatter(f, x="sentiment_naif", y="engagement", color="famille_source", opacity=.6,
                                    log_y=True, hover_data=["auteur"],
                                    title="Engagement vs sentiment"), 480), width="stretch")
    plus = f.sort_values("engagement", ascending=False).head(5)
    st.markdown("**Messages les plus populaires**")
    for r in plus.itertuples():
        st.markdown(f"> {r.texte[:280]}…  \n> — *{r.auteur}* · {r.sujet} · 👍 {r.engagement}")

with onglets[5]:
    st.subheader("Synthèse")
    st.info(ia.synthese_hebdo(f))
    st.caption("Définissez ANTHROPIC_API_KEY pour une synthèse générée par Claude ; sinon synthèse chiffrée locale.")

with onglets[6]:
    st.dataframe(f.sort_values("date", ascending=False)[
        ["date", "source", "sujet", "type", "auteur", "note_finale", "categorie", "theme", "engagement", "texte", "url"]],
        hide_index=True, column_config={"url": st.column_config.LinkColumn("lien")})
    st.download_button("⬇️ Exporter en CSV (filtré)", f.to_csv(index=False).encode("utf-8"),
                       "avis_filtres.csv", "text/csv")
