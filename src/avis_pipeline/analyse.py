"""Analyse : statistiques pandas, fréquence de mots, sentiment (naïf vs VADER)."""
import re
from collections import Counter

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

MOTS_VIDES = set("""le la les un une des de du et en à au aux ce ces je tu il elle on nous vous ils
pour par sur dans avec sans que qui est sont a ai pas plus très mais ou où se sa son ses mon ma mes
y ne n d l j c s qu""".split())

LEXIQUE_POSITIF = {"excellent", "super", "top", "recommande", "bonne", "bon", "réactif", "enrichissant",
                   "génial", "parfait", "ambiance", "bien"}
LEXIQUE_NEGATIF = {"décevant", "médiocre", "catastrophique", "déconseille", "nul", "injoignable",
                   "élevés", "aucune", "mauvais", "problème"}


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
    mots = tokeniser(texte)
    pos = sum(m in LEXIQUE_POSITIF for m in mots)
    neg = sum(m in LEXIQUE_NEGATIF for m in mots)
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
    return df


def comparer_methodes(df: pd.DataFrame) -> pd.Series:
    """Corrélation de chaque score de sentiment avec la note (S6 : naïf vs lib)."""
    return df[["sentiment_naif", "sentiment_vader"]].corrwith(df["note"])


def evolution_mensuelle(df: pd.DataFrame) -> pd.DataFrame:
    """Note moyenne et nombre d'avis par mois et par entreprise."""
    return (df.assign(mois=df["date"].dt.to_period("M").dt.to_timestamp())
              .groupby(["mois", "entreprise"])["note"].agg(note_moyenne="mean", nb_avis="count")
              .reset_index())
