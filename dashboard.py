"""Observatoire d'avis : dashboard Streamlit. Lancer avec `streamlit run dashboard.py`."""
import html
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

from avis_pipeline import analyse, config, ia, stockage

# ---------------------------------------------------------------- Palette
BLEU, VERT, CORAIL, ARDOISE = "#1d4ed8", "#059669", "#e5484d", "#94a3b8"
PALETTE = {"positif": VERT, "neutre": ARDOISE, "négatif": CORAIL}
SEQ = ["#1d4ed8", "#059669", "#0ea5e9", "#14b8a6", "#6366f1", "#d97706", "#64748b"]
ECHELLE_NOTE = [CORAIL, "#f5c451", VERT]
px.defaults.color_discrete_sequence = SEQ

PAGES = ["Vue d'ensemble", "Évolution", "Textes et mots", "Thèmes", "Auteurs", "Intelligence artificielle", "Explorer"]
LIMITE_IA_SERVEUR = int(os.environ.get("IA_MAX_APPELS", 8))  # appels IA par session si la clé est celle du serveur

st.set_page_config(page_title="Observatoire d'avis", layout="wide")

# La clé peut venir des « Secrets » de l'hébergeur ; elle n'est jamais affichée.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ.setdefault("ANTHROPIC_API_KEY", st.secrets["ANTHROPIC_API_KEY"])
except Exception:  # pas de fichier de secrets en local : normal
    pass

st.markdown("""
<style>
html, body, [class*="css"] {font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;}
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1380px;}
header[data-testid="stHeader"] {background: transparent;}
.entete {display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;
    background: linear-gradient(115deg,#0f2f6b 0%,#1d4ed8 55%,#059669 140%); color:#fff;
    padding: 28px 34px; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 10px 28px rgba(29,78,216,.20);}
.entete h1 {margin:0; padding:0; font-size:1.9rem; font-weight:750; letter-spacing:-.02em; color:#fff;}
.entete p {margin:6px 0 0; font-size:.97rem; opacity:.88; max-width:640px;}
.entete .meta {text-align:right; font-size:.82rem; opacity:.9; line-height:1.7;}
.entete .meta b {font-size:1.05rem;}
.carte {background:#fff; border:1px solid #e2e8f2; border-radius:14px; padding:16px 20px; height:100%;
    box-shadow:0 1px 3px rgba(15,39,66,.05); border-top:3px solid #1d4ed8;}
.carte.vert {border-top-color:#059669;} .carte.corail {border-top-color:#e5484d;} .carte.gris {border-top-color:#94a3b8;}
.carte .lib {font-size:.76rem; text-transform:uppercase; letter-spacing:.07em; color:#5b6b82; font-weight:600;}
.carte .val {font-size:1.85rem; font-weight:750; color:#0f2742; letter-spacing:-.02em; margin-top:2px;}
.carte .sous {font-size:.8rem; color:#64748b; margin-top:2px;}
.titre-section {margin:26px 0 4px; font-size:1.12rem; font-weight:700; color:#0f2742;}
.sous-titre-section {margin:0 0 12px; font-size:.9rem; color:#5b6b82;}
.cle {background:#fff; border:1px solid #e2e8f2; border-left:4px solid #1d4ed8; border-radius:10px;
    padding:12px 16px; font-size:.92rem; color:#0f2742; height:100%;}
.cle.vert {border-left-color:#059669;} .cle.corail {border-left-color:#e5484d;}
.pastille {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;}
.pastille.ok {background:#d1fae5; color:#065f46;} .pastille.ko {background:#fef3c7; color:#92400e;}
div[data-testid="stPlotlyChart"] {background:#fff; border:1px solid #e2e8f2; border-radius:14px; padding:6px;
    box-shadow:0 1px 3px rgba(15,39,66,.05);}
section[data-testid="stSidebar"] {background:#fff; border-right:1px solid #e2e8f2;}
section[data-testid="stSidebar"] h2 {font-size:1.05rem; letter-spacing:-.01em;}
div[data-testid="stSegmentedControl"] button {font-weight:600;}
.pied {margin-top:36px; padding-top:14px; border-top:1px solid #e2e8f2; font-size:.8rem; color:#64748b;}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- Utilitaires
def echapper(texte: str) -> str:
    """Échappe les caractères markdown/HTML d'un texte externe (non fiable) avant affichage."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", str(texte))


def carte(libelle: str, valeur: str, sous: str = "", teinte: str = "") -> str:
    """Retourne le HTML d'une carte d'indicateur (valeurs calculées par l'application)."""
    return (f'<div class="carte {teinte}"><div class="lib">{html.escape(libelle)}</div>'
            f'<div class="val">{html.escape(valeur)}</div><div class="sous">{html.escape(sous)}</div></div>')


def section(titre: str, description: str = "") -> None:
    """Affiche un titre de section avec une courte description."""
    st.markdown(f'<div class="titre-section">{html.escape(titre)}</div>'
                f'<div class="sous-titre-section">{html.escape(description)}</div>', unsafe_allow_html=True)


def style(fig, hauteur: int = 380):
    """Applique un style clair et cohérent à une figure Plotly."""
    fig.update_layout(template="plotly_white", paper_bgcolor="#fff", plot_bgcolor="#fff",
                      font=dict(color="#0f2742", size=13), height=hauteur, margin=dict(l=12, r=12, t=56, b=12),
                      legend=dict(orientation="h", y=-0.22, title=None),
                      title=dict(font=dict(size=15, color="#0f2742"), x=0.02),
                      hoverlabel=dict(bgcolor="#fff", font_size=12))
    fig.update_xaxes(gridcolor="#eef2f8", zeroline=False)
    fig.update_yaxes(gridcolor="#eef2f8", zeroline=False)
    return fig


def tracer(fig, hauteur: int = 380) -> None:
    """Affiche une figure stylée pleine largeur."""
    st.plotly_chart(style(fig, hauteur), width="stretch")


@st.cache_data(show_spinner="Analyse des messages en cours")
def charger() -> pd.DataFrame:
    """Charge la base (amorcée depuis l'instantané si vide), nettoie, calcule sentiments et thèmes."""
    brut = stockage.charger_avis()
    snapshot = config.DOSSIER_DATA / "avis_snapshot.csv"
    if brut.empty and snapshot.exists():
        stockage.amorcer_depuis_csv(snapshot)
        brut = stockage.charger_avis()
    df = analyse.ajouter_sentiments(analyse.nettoyer_donnees(brut)) if len(brut) else brut
    return analyse.detecter_themes(df) if len(df) else df


df = charger()
if df.empty:
    st.warning("Base vide. Lancez la collecte : `python -m avis_pipeline.cli` (ou `--demo`).")
    st.stop()

# ---------------------------------------------------------------- Filtres
TOUS = {"source": sorted(df["source"].unique()), "sujet": sorted(df["sujet"].unique()),
        "type": sorted(df["type"].dropna().unique())}


def reinitialiser() -> None:
    """Remet tous les filtres à leur valeur par défaut."""
    for cle, valeurs in TOUS.items():
        st.session_state[f"f_{cle}"] = valeurs
    st.session_state["f_periode"] = (df["date"].min().date(), df["date"].max().date())
    st.session_state["f_notes"] = (1.0, 5.0)
    st.session_state["f_mot"] = ""


with st.sidebar:
    st.header("Filtres")
    sources = st.multiselect("Source", TOUS["source"], default=TOUS["source"], key="f_source")
    sujets = st.multiselect("Sujet", TOUS["sujet"], default=TOUS["sujet"], key="f_sujet")
    types = st.multiselect("Type de message", TOUS["type"], default=TOUS["type"], key="f_type")
    periode = st.date_input("Période", (df["date"].min().date(), df["date"].max().date()), key="f_periode")
    notes = st.slider("Note (réelle ou estimée)", 1.0, 5.0, (1.0, 5.0), step=0.5, key="f_notes")
    mot = st.text_input("Mot-clé dans le texte", key="f_mot")
    st.button("Réinitialiser les filtres", on_click=reinitialiser, width="stretch")
    st.caption("Les notes sont estimées par analyse de sentiment lorsque la source n'en fournit pas.")

debut, fin = (periode[0], periode[-1]) if isinstance(periode, tuple) and len(periode) else (periode, periode)
f = df[df["source"].isin(sources) & df["sujet"].isin(sujets) & df["type"].isin(types)
       & df["date"].dt.date.between(debut, fin) & df["note_finale"].between(*notes)]
if mot:
    f = f[f["texte"].str.contains(mot, case=False, na=False, regex=False)]

st.markdown(f"""<div class="entete"><div><h1>Observatoire d'avis</h1>
<p>Ce que les internautes disent des transports, de l'école et de l'université : collecte, analyse du langage
et synthèse par intelligence artificielle.</p></div>
<div class="meta"><b>{len(df):,}</b> messages analysés<br>{df['source'].nunique()} sources · {df['sujet'].nunique()} sujets<br>
du {df['date'].min():%d/%m/%Y} au {df['date'].max():%d/%m/%Y}</div></div>""".replace(",", " "),
            unsafe_allow_html=True)

if f.empty:
    st.info("Aucun message ne correspond aux filtres sélectionnés.")
    st.stop()

# ---------------------------------------------------------------- Indicateurs
part_neg = (f["categorie"] == "négatif").mean()
note_moy = f["note_finale"].mean()
colonnes = st.columns(5)
colonnes[0].markdown(carte("Messages", f"{len(f):,}".replace(",", " "), f"{len(f) / len(df):.0%} du total"), unsafe_allow_html=True)
colonnes[1].markdown(carte("Note moyenne", f"{note_moy:.2f} / 5", f"{note_moy - df['note_finale'].mean():+.2f} vs ensemble", "vert"), unsafe_allow_html=True)
colonnes[2].markdown(carte("Messages négatifs", f"{part_neg:.0%}", f"{(f['categorie'] == 'positif').mean():.0%} positifs", "corail"), unsafe_allow_html=True)
colonnes[3].markdown(carte("Auteurs distincts", f"{f['auteur'].nunique():,}".replace(",", " "), "pseudonymisés", "gris"), unsafe_allow_html=True)
colonnes[4].markdown(carte("Engagement", f"{int(f['engagement'].sum()):,}".replace(",", " "), "likes, partages, votes"), unsafe_allow_html=True)

for ligne in analyse.alertes(f).itertuples():
    st.error(f"Alerte : le sujet « {ligne.sujet} » a une note moyenne de {ligne.mean:.2f}/5 ({ligne.count} messages).")

st.write("")
page = st.segmented_control("Navigation", PAGES, default=PAGES[0], key="page", label_visibility="collapsed") or PAGES[0]

# ---------------------------------------------------------------- Pages
if page == PAGES[0]:
    par_sujet = f.groupby("sujet")["note_finale"].agg(["mean", "count"])
    par_sujet = par_sujet[par_sujet["count"] >= 10]
    section("Points clés", "Constats calculés automatiquement sur la sélection en cours.")
    cles = st.columns(3)
    if not par_sujet.empty:
        meilleur, pire = par_sujet["mean"].idxmax(), par_sujet["mean"].idxmin()
        cles[0].markdown(f'<div class="cle vert">Sujet le mieux perçu : <b>{html.escape(meilleur)}</b> '
                         f'(note {par_sujet.loc[meilleur, "mean"]:.2f}/5)</div>', unsafe_allow_html=True)
        cles[1].markdown(f'<div class="cle corail">Sujet le plus critiqué : <b>{html.escape(pire)}</b> '
                         f'(note {par_sujet.loc[pire, "mean"]:.2f}/5)</div>', unsafe_allow_html=True)
    jour_pic = f["jour_semaine"].value_counts().idxmax()
    cles[2].markdown(f'<div class="cle">Jour le plus actif : <b>{jour_pic}</b> · source principale : '
                     f'<b>{html.escape(f["famille_source"].value_counts().idxmax())}</b></div>', unsafe_allow_html=True)

    section("Perception globale", "Répartition du ton des messages et distribution des notes.")
    a, b = st.columns(2)
    rep = f["categorie"].value_counts().reindex(["positif", "neutre", "négatif"]).fillna(0).reset_index()
    rep.columns = ["catégorie", "messages"]
    with a:
        tracer(px.pie(rep, names="catégorie", values="messages", hole=.6, color="catégorie",
                      color_discrete_map=PALETTE, title="Répartition du sentiment"))
    with b:
        tracer(px.histogram(f, x="note_finale", nbins=9, color="sujet", title="Distribution des notes",
                            barmode="stack", labels={"note_finale": "Note", "count": "Messages"}))
    section("Comparaison", "Volume de messages et note moyenne selon le sujet.")
    c, d = st.columns(2)
    vol = f.groupby(["sujet", "famille_source"]).size().reset_index(name="messages")
    with c:
        tracer(px.bar(vol, x="sujet", y="messages", color="famille_source", title="Volume par sujet et par source",
                      labels={"sujet": "", "famille_source": "Source"}))
    moy = f.groupby("sujet")["note_finale"].mean().sort_values().reset_index()
    with d:
        tracer(px.bar(moy, x="note_finale", y="sujet", orientation="h", color="note_finale",
                      color_continuous_scale=ECHELLE_NOTE, range_color=[1, 5], title="Note moyenne par sujet",
                      labels={"note_finale": "Note", "sujet": ""}).update_coloraxes(showscale=False))

elif page == PAGES[1]:
    section("Évolution dans le temps", "Suivez la note moyenne et le volume de messages.")
    freq = st.radio("Granularité", ["Semaine", "Mois", "Jour"], horizontal=True)
    evo = analyse.evolution(f, {"Semaine": "W", "Mois": "M", "Jour": "D"}[freq])
    a, b = st.columns(2)
    with a:
        tracer(px.line(evo, x="periode", y="note_moyenne", color="sujet", markers=True,
                       title="Note moyenne", labels={"periode": "", "note_moyenne": "Note"}))
    with b:
        tracer(px.area(evo, x="periode", y="nb_avis", color="sujet", title="Volume de messages",
                       labels={"periode": "", "nb_avis": "Messages"}))
    section("Rythme d'expression", "Moments de la semaine où les internautes s'expriment le plus.")
    tracer(px.imshow(analyse.heatmap_activite(f), aspect="auto", color_continuous_scale=["#eff6ff", "#93c5fd", BLEU],
                     labels=dict(x="Heure", y="", color="Messages"), title="Jour et heure"), 340)

elif page == PAGES[2]:
    section("Vocabulaire", "Mots et expressions les plus employés dans les messages sélectionnés.")
    a, b = st.columns(2)
    mots = analyse.top_mots(f["texte"], 20)
    bi = analyse.top_bigrammes(f["texte"], 20)
    with a:
        tracer(px.bar(x=[c for _, c in mots][::-1], y=[m for m, _ in mots][::-1], orientation="h",
                      labels={"x": "Occurrences", "y": ""}, title="Mots les plus fréquents"), 520)
    with b:
        tracer(px.bar(x=[c for _, c in bi][::-1], y=[m for m, _ in bi][::-1], orientation="h",
                      labels={"x": "Occurrences", "y": ""}, title="Expressions de deux mots"), 520)
    section("Nuage de mots")
    st.image(analyse.nuage_de_mots(f["texte"]))
    section("Ton des messages", "Mots dominants dans les messages positifs puis négatifs.")
    pos_neg = analyse.mots_par_sentiment(f)
    a, b = st.columns(2)
    for colonne, cat, teinte in ((a, "positif", "vert"), (b, "négatif", "corail")):
        liste = ", ".join(f"{m} ({n})" for m, n in pos_neg[cat]) or "aucun"
        colonne.markdown(f'<div class="cle {teinte}"><b>Messages {cat}s</b><br>{html.escape(liste)}</div>', unsafe_allow_html=True)
    section("Méthodes de sentiment", "Comparaison entre le lexique français et VADER (conçu pour l'anglais).")
    tracer(px.scatter(f, x="sentiment_naif", y="sentiment_vader", color="sujet", opacity=.6,
                      title="Lexique français contre VADER", labels={"sentiment_naif": "Lexique FR", "sentiment_vader": "VADER"}))
    st.caption("Corrélation : " + ", ".join(f"{k} = {v:.2f}" for k, v in analyse.comparer_methodes(f).items()))

elif page == PAGES[3]:
    section("Thèmes détectés", "Regroupement automatique des messages (TF-IDF et KMeans), nommés par leurs mots-clés.")
    th = f.groupby("theme").agg(messages=("id", "count"), note=("note_finale", "mean")).reset_index()
    a, b = st.columns(2)
    with a:
        tracer(px.treemap(th, path=["theme"], values="messages", color="note", color_continuous_scale=ECHELLE_NOTE,
                          range_color=[1, 5], title="Taille = volume, couleur = note"))
    with b:
        tracer(px.bar(f.groupby(["theme", "sujet"]).size().reset_index(name="messages"), x="messages", y="theme",
                      color="sujet", orientation="h", title="Thèmes selon le sujet", labels={"theme": ""}))
    choix = st.selectbox("Exemples d'un thème", th["theme"])
    st.dataframe(f[f["theme"] == choix][["date", "sujet", "note_finale", "texte"]].head(15), hide_index=True)

elif page == PAGES[4]:
    section("Auteurs", "Identifiants pseudonymisés : aucun nom d'utilisateur réel n'est conservé.")
    a, b = st.columns(2)
    with a:
        tracer(px.bar(analyse.top_auteurs(f, 15), x="messages", y="auteur", orientation="h", color="sentiment",
                      color_continuous_scale=[CORAIL, "#cbd5e1", VERT], range_color=[-1, 1],
                      title="Auteurs les plus actifs", labels={"auteur": ""}), 480)
    with b:
        tracer(px.scatter(f, x="sentiment_naif", y="engagement", color="famille_source", opacity=.6, log_y=True,
                          title="Engagement selon le sentiment",
                          labels={"sentiment_naif": "Sentiment", "engagement": "Engagement"}), 480)
    section("Messages les plus populaires")
    for r in f.sort_values("engagement", ascending=False).head(5).itertuples():
        st.markdown(f"> {echapper(r.texte[:280])}  \n> Sujet : {echapper(r.sujet)} · engagement : {int(r.engagement)}")

elif page == PAGES[5]:
    section("Intelligence artificielle", "Synthèses rédigées par Claude à partir d'un échantillon des messages filtrés.")
    cle_saisie = st.text_input("Clé API Anthropic (facultative)", type="password", key="cle_api",
                               help="Conservée en mémoire pour la session uniquement, jamais enregistrée.")
    cle = ia.obtenir_cle(cle_saisie)
    cle_visiteur = bool(cle_saisie.strip())
    nb = st.session_state.get("nb_appels_ia", 0)
    restant = None if cle_visiteur else max(0, LIMITE_IA_SERVEUR - nb)
    if cle:
        st.markdown('<span class="pastille ok">Clé détectée</span>'
                    + ("" if restant is None else f" &nbsp; {restant} appel(s) restant(s) sur cette session"),
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="pastille ko">Aucune clé : résumé chiffré local uniquement</span>', unsafe_allow_html=True)
    st.info(ia.synthese_locale(f))
    st.caption(f"Les analyses portent sur {len(f)} messages filtrés (échantillon de {ia.MAX_MESSAGES_PROMPT} envoyé à Claude).")

    def lancer(cle_etat: str, fonction, *args) -> None:
        """Exécute un appel Claude, respecte la limite de session et affiche les erreurs proprement."""
        if restant is not None and restant <= 0:
            st.warning("Limite d'appels atteinte pour cette session. Saisissez votre propre clé pour continuer.")
            return
        try:
            with st.spinner("Claude analyse les messages"):
                st.session_state[cle_etat] = fonction(*args, cle)
            st.session_state["nb_appels_ia"] = nb + 1
        except ia.ErreurIA as erreur:
            st.error(str(erreur))

    a, b = st.columns(2)
    if a.button("Synthèse hebdomadaire", width="stretch"):
        lancer("ia_synthese", ia.synthese_hebdo, f)
    if b.button("Veille concurrentielle", width="stretch"):
        lancer("ia_veille", ia.veille_concurrentielle, f)
    for etat, titre in (("ia_synthese", "Synthèse hebdomadaire"), ("ia_veille", "Veille concurrentielle")):
        if etat in st.session_state:
            section(titre)
            st.markdown(ia.neutraliser_images(st.session_state[etat]))

    section("Réponse automatique à un message négatif", "Claude rédige une réponse courte et empathique.")
    negatifs = f[f["categorie"] == "négatif"].sort_values("engagement", ascending=False).head(30)
    if negatifs.empty:
        st.write("Aucun message négatif dans la sélection.")
    else:
        choix = st.selectbox("Message", negatifs.index,
                             format_func=lambda i: f"[{negatifs.loc[i, 'sujet']}] {negatifs.loc[i, 'texte'][:110]}")
        st.text(negatifs.loc[choix, "texte"])
        if st.button("Rédiger une réponse"):
            lancer("ia_reponse", ia.reponse_avis_negatif, negatifs.loc[choix, "texte"], negatifs.loc[choix, "sujet"])
        if "ia_reponse" in st.session_state:
            st.success(st.session_state["ia_reponse"])

elif page == PAGES[6]:
    section("Explorer les données", "Tableau complet des messages filtrés, exportable en CSV.")
    st.dataframe(f.sort_values("date", ascending=False)[
        ["date", "source", "sujet", "type", "auteur", "note_finale", "categorie", "theme", "engagement", "texte", "url"]],
        hide_index=True, column_config={"url": st.column_config.LinkColumn("Lien")})
    st.download_button("Exporter en CSV (sélection)", f.to_csv(index=False).encode("utf-8"), "avis_filtres.csv", "text/csv")

st.markdown('<div class="pied">Données : API publiques Mastodon et Lemmy (messages français, identifiants pseudonymisés). '
            'Les notes sont estimées par analyse de sentiment. Projet pédagogique EMLV MSID.</div>', unsafe_allow_html=True)
