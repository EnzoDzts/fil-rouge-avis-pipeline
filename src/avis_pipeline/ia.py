"""Extension IA : synthèse hebdomadaire via l'API Claude (clé ANTHROPIC_API_KEY)."""
import os

import pandas as pd


def synthese_locale(df: pd.DataFrame) -> str:
    """Synthèse chiffrée simple, utilisée sans clé API."""
    if df.empty:
        return "Aucun avis sur la période."
    pire = df.groupby("sujet")["note_finale"].mean().idxmin()
    return (f"{len(df)} avis, note moyenne {df['note_finale'].mean():.2f}/5, "
            f"{(df['note_finale'] <= 2).mean():.0%} d'avis négatifs. Entreprise la moins bien notée : {pire}.")


def synthese_hebdo(df: pd.DataFrame, modele: str = "claude-sonnet-5-5") -> str:
    """Résume les avis récents avec Claude ; retombe sur la synthèse locale sans clé."""
    if not os.environ.get("ANTHROPIC_API_KEY") or df.empty:
        return synthese_locale(df)
    import anthropic
    extrait = "\n".join(f"- ({r.note_finale}/5, {r.sujet}) {r.texte}" for r in df.head(60).itertuples())
    rep = anthropic.Anthropic().messages.create(
        model=modele, max_tokens=500,
        messages=[{"role": "user", "content":
                   "Synthétise en français, en 5 puces, les thèmes récurrents de ces avis :\n" + extrait}],
    )
    return rep.content[0].text
