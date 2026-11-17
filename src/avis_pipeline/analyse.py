"""Analyse : statistiques pandas, fréquence de mots, sentiment (naïf vs VADER)."""
import re
from collections import Counter

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

MOTS_VIDES = set("""le la les un une des de du et en à au aux ce ces je tu il elle on nous vous ils
pour par sur dans avec sans que qui est sont a ai pas plus très mais ou où se sa son ses mon ma mes
y ne n d l j c s qu""".split())

LEXIQUE_POSITIF = {"excellent", "super", "top", "recommande", "bonne", "bon", "réactif", "enrichissant",
                   "génial", "parfait", "ambiance", "bien", "merci", "bravo", "heureux", "content",
                   "agréable", "efficace", "rapide", "ponctuel", "formidable", "magnifique", "sympa",
                   "excellente", "satisfait", "confortable", "propre", "gratuit", "réussi"}
LEXIQUE_NEGATIF = {"décevant", "médiocre", "catastrophique", "déconseille", "nul", "injoignable",
                   "élevés", "aucune", "mauvais", "problème", "retard", "retards", "annulé", "annulés",
                   "grève", "panne", "honte", "scandale", "galère", "pire", "inadmissible", "supprimé",
                   "supprimés", "bloqué", "bloqués", "chaos", "perturbations", "incident", "colère",
                   "marre", "ras-le-bol", "insupportable", "cher", "chers", "sale", "dangereux"}
NEGATIONS = {"pas", "jamais", "aucun", "aucune", "ni", "plus"}


def tokeniser(texte: str) -> list[str]:
    """Découpe un texte en mots minuscules sans mots vides."""
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", (texte or "").lower())
    return [m for m in mots if m not in MOTS_VIDES and len(m) > 2]


def top_mots(textes, n: int = 20) -> list[tuple[str, int]]:
    """Retourne les n mots les plus fréquents d'une série de textes."""
    compteur = Counter()
    for t in textes:
        compteur.update(tokeniser(t))
    return compteur.most_common(n)


def sentiment_naif(texte: str) -> float:
    """Score naïf dans [-1, 1] : (positifs - négatifs) / mots trouvés (lexique FR)."""
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ'-]+", (texte or "").lower())
    pos = neg = 0
    for i, mot in enumerate(mots):
        # une négation juste avant (« pas bien ») inverse la polarité du mot
        inverse = i > 0 and mots[i - 1] in NEGATIONS
        if mot in LEXIQUE_POSITIF:
            pos, neg = (pos, neg + 1) if inverse else (pos + 1, neg)
        elif mot in LEXIQUE_NEGATIF:
            pos, neg = (pos + 1, neg) if inverse else (pos, neg + 1)
    return 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)


_VADER = SentimentIntensityAnalyzer()


def sentiment_vader(texte: str) -> float:
    """Score composé VADER dans [-1, 1] (conçu pour l'anglais : limité en français)."""
    return _VADER.polarity_scores(texte or "")["compound"]


def ajouter_sentiments(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes sentiment_naif et sentiment_vader."""
    df = df.copy()
    df["sentiment_naif"] = df["texte"].apply(sentiment_naif)
    df["sentiment_vader"] = df["texte"].apply(sentiment_vader)
    # note affichée : vraie note si elle existe, sinon estimée (-1..1 -> 1..5) depuis le score naïf
    df["note_estimee"] = (3 + 2 * df["sentiment_naif"]).round(1)
    df["note_finale"] = df["note"].fillna(df["note_estimee"])
    return df


def comparer_methodes(df: pd.DataFrame) -> pd.Series:
    """Corrélation de chaque score avec la note réelle (S6 : naïf vs lib).

    Sans note réelle (données Mastodon), on compare les deux scores entre eux.
    """
    reel = df.dropna(subset=["note"])
    if reel.empty:
        return pd.Series({"naif_vs_vader": df["sentiment_naif"].corr(df["sentiment_vader"])})
    return reel[["sentiment_naif", "sentiment_vader"]].corrwith(reel["note"])


def evolution_mensuelle(df: pd.DataFrame) -> pd.DataFrame:
    """Note moyenne et nombre d'avis par mois et par entreprise."""
    return (df.assign(mois=df["date"].dt.to_period("M").dt.to_timestamp())
              .groupby(["mois", "entreprise"])["note_finale"].agg(note_moyenne="mean", nb_avis="count")
              .reset_index())


def nuage_de_mots(textes):
    """Construit une image de nuage de mots (WordCloud) à partir de textes français."""
    from wordcloud import WordCloud
    texte = " ".join(m for t in textes for m in tokeniser(t))
    return WordCloud(width=900, height=400, background_color="white").generate(texte).to_image()
