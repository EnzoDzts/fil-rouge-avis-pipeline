"""Analyse : stats pandas, mots, sentiment (naïf vs VADER), thèmes (TF-IDF + KMeans)."""
import re
from collections import Counter

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

MOTS_VIDES = set("""le la les un une des de du et en à au aux ce ces cet cette je tu il elle on nous vous ils elles
pour par sur dans avec sans que qui quoi est sont a ai as ont pas plus très mais ou où se sa son ses mon ma mes ton
ta tes leur leurs y ne n d l j c s qu m t été être avoir fait faire comme aussi tout tous toute toutes si car donc
alors même bien encore déjà peu trop moins quand dont cela ça ceci celui celle http https www com fr lien
sont était sera ont avait cest c'est qu'il qu'on n'est j'ai d'un d'une l'on y'a
the and that for with this you are was have not but its from they will can all out new one old lemmit reddit""".split())

LEXIQUE_POSITIF = {"excellent", "super", "top", "recommande", "bonne", "bon", "réactif", "enrichissant",
                   "génial", "parfait", "ambiance", "bien", "merci", "bravo", "heureux", "content",
                   "agréable", "efficace", "rapide", "ponctuel", "formidable", "magnifique", "sympa",
                   "excellente", "satisfait", "confortable", "propre", "gratuit", "réussi", "belle",
                   "meilleur", "meilleure", "utile", "intéressant", "passionnant", "chouette", "félicitations"}
LEXIQUE_NEGATIF = {"décevant", "médiocre", "catastrophique", "déconseille", "nul", "injoignable",
                   "élevés", "aucune", "mauvais", "problème", "retard", "retards", "annulé", "annulés",
                   "grève", "panne", "honte", "scandale", "galère", "pire", "inadmissible", "supprimé",
                   "supprimés", "bloqué", "bloqués", "chaos", "perturbations", "incident", "colère",
                   "marre", "ras-le-bol", "insupportable", "cher", "chers", "sale", "dangereux",
                   "dégradation", "fermeture", "pénible", "absurde", "ridicule", "inutile", "triste", "grave"}
NEGATIONS = {"pas", "jamais", "aucun", "aucune", "ni", "plus", "guère"}
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


MOTIF_URL = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|fr|net|org|info|php|html)\S*", re.I)
MOTIF_BOT = re.compile(r"automated archive|made with .*bot|\bbot\b.*original post|\[bot\]", re.I)
MOTS_VIDES |= {"spip", "php", "net", "org", "article", "rticle", "lang", "post", "original", "posted", "bot",
               "automated", "archive", "made", "online", "ligne", "lire", "voir", "via"}


def nettoyer_donnees(df: pd.DataFrame) -> pd.DataFrame:
    """Retire les messages de robots et les doublons de texte avant l'analyse."""
    masque_bot = df["texte"].str.contains(MOTIF_BOT, na=False)
    return df[~masque_bot].drop_duplicates(subset=["sujet", "texte"]).reset_index(drop=True)


def tokeniser(texte: str) -> list[str]:
    """Découpe un texte en mots minuscules, sans URL ni mots vides."""
    texte = MOTIF_URL.sub(" ", texte or "")
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", texte.lower())
    return [m for m in mots if m not in MOTS_VIDES and len(m) > 2]


def top_mots(textes, n: int = 20) -> list[tuple[str, int]]:
    """Retourne les n mots les plus fréquents d'une série de textes."""
    compteur = Counter()
    for t in textes:
        compteur.update(tokeniser(t))
    return compteur.most_common(n)


def top_bigrammes(textes, n: int = 15) -> list[tuple[str, int]]:
    """Retourne les n paires de mots consécutifs les plus fréquentes."""
    compteur = Counter()
    for t in textes:
        mots = tokeniser(t)
        compteur.update(f"{a} {b}" for a, b in zip(mots, mots[1:]))
    return compteur.most_common(n)


def sentiment_naif(texte: str) -> float:
    """Score naïf dans [-1, 1] : (positifs - négatifs) / mots trouvés, avec négations."""
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ'-]+", (texte or "").lower())
    pos = neg = 0
    for i, mot in enumerate(mots):
        inverse = i > 0 and mots[i - 1] in NEGATIONS  # « pas bien » inverse la polarité
        if mot in LEXIQUE_POSITIF:
            pos, neg = (pos, neg + 1) if inverse else (pos + 1, neg)
        elif mot in LEXIQUE_NEGATIF:
            pos, neg = (pos + 1, neg) if inverse else (pos, neg + 1)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


_VADER = SentimentIntensityAnalyzer()


def sentiment_vader(texte: str) -> float:
    """Score composé VADER dans [-1, 1] (conçu pour l'anglais : limité en français)."""
    return _VADER.polarity_scores(texte or "")["compound"]


def etiquette_sentiment(score: float) -> str:
    """Convertit un score en catégorie : négatif, neutre ou positif."""
    return "positif" if score > 0.2 else "négatif" if score < -0.2 else "neutre"


def ajouter_sentiments(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute sentiments, note finale, catégories et colonnes temporelles."""
    df = df.copy()
    df["sentiment_naif"] = df["texte"].apply(sentiment_naif)
    df["sentiment_vader"] = df["texte"].apply(sentiment_vader)
    df["note_estimee"] = (3 + 2 * df["sentiment_naif"]).round(1)  # -1..1 -> 1..5
    df["note_finale"] = df["note"].fillna(df["note_estimee"])
    df["categorie"] = df["sentiment_naif"].apply(etiquette_sentiment)
    df["jour_semaine"] = pd.Categorical(df["date"].dt.dayofweek.map(dict(enumerate(JOURS))), JOURS, ordered=True)
    df["heure"] = df["date"].dt.hour
    df["nb_mots"] = df["texte"].str.split().str.len()
    df["famille_source"] = df["source"].str.split(":").str[0]
    return df


def comparer_methodes(df: pd.DataFrame) -> pd.Series:
    """Corrélation des scores avec la note réelle ; sans note, naïf vs VADER."""
    reel = df.dropna(subset=["note"])
    if reel.empty:
        return pd.Series({"naif_vs_vader": df["sentiment_naif"].corr(df["sentiment_vader"])})
    return reel[["sentiment_naif", "sentiment_vader"]].corrwith(reel["note"])


def evolution(df: pd.DataFrame, frequence: str = "W") -> pd.DataFrame:
    """Note moyenne et volume par période (W=semaine, M=mois) et par sujet."""
    return (df.assign(periode=df["date"].dt.to_period(frequence).dt.to_timestamp())
              .groupby(["periode", "sujet"])["note_finale"].agg(note_moyenne="mean", nb_avis="count")
              .reset_index())


def heatmap_activite(df: pd.DataFrame) -> pd.DataFrame:
    """Nombre de messages par jour de semaine (lignes) et heure (colonnes)."""
    return df.pivot_table(index="jour_semaine", columns="heure", values="id", aggfunc="count",
                          fill_value=0, observed=False)


def top_auteurs(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Auteurs les plus actifs avec leur sentiment moyen et engagement total."""
    return (df.groupby("auteur").agg(messages=("id", "count"), sentiment=("sentiment_naif", "mean"),
                                     engagement=("engagement", "sum"))
              .sort_values("messages", ascending=False).head(n).round(2).reset_index())


def mots_par_sentiment(df: pd.DataFrame, n: int = 10) -> dict[str, list[tuple[str, int]]]:
    """Mots les plus fréquents dans les messages positifs et négatifs."""
    return {cat: top_mots(df.loc[df["categorie"] == cat, "texte"], n) for cat in ("positif", "négatif")}


def detecter_themes(df: pd.DataFrame, nb_themes: int = 6) -> pd.DataFrame:
    """Regroupe les textes en thèmes (TF-IDF + KMeans) et nomme chaque thème par ses mots-clés.

    Returns:
        DataFrame avec la colonne `theme` ajoutée (ex. « train · retard · grève »).
    """
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = df.copy()
    if len(df) < nb_themes * 5:
        df["theme"] = "Général"
        return df
    vecteur = TfidfVectorizer(tokenizer=tokeniser, lowercase=False, token_pattern=None,
                              min_df=3, max_df=0.5, max_features=3000)
    matrice = vecteur.fit_transform(df["texte"])
    modele = KMeans(n_clusters=nb_themes, n_init=5, random_state=42).fit(matrice)
    termes = vecteur.get_feature_names_out()
    noms = {}
    for i, centre in enumerate(modele.cluster_centers_):
        noms[i] = " · ".join(termes[j] for j in centre.argsort()[::-1][:3])
    df["theme"] = [noms[c] for c in modele.labels_]
    return df


def nuage_de_mots(textes):
    """Construit une image de nuage de mots à partir de textes français."""
    from wordcloud import WordCloud
    texte = " ".join(m for t in textes for m in tokeniser(t)) or "vide"
    return WordCloud(width=1000, height=420, background_color="white", colormap="winter",
                     max_words=120).generate(texte).to_image()


def alertes(df: pd.DataFrame, seuil: float = 2.5, min_avis: int = 10) -> pd.DataFrame:
    """Sujets dont la note moyenne (estimée ou réelle) passe sous le seuil."""
    synthese = df.groupby("sujet")["note_finale"].agg(["mean", "count"]).reset_index()
    return synthese[(synthese["mean"] < seuil) & (synthese["count"] >= min_avis)]
