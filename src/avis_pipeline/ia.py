"""Intégration de l'API Claude (Anthropic) : synthèse, recommandations, réponses, veille.

La clé est lue (par ordre de priorité) : paramètre `cle` > variable d'environnement
ANTHROPIC_API_KEY > fichier .env. Elle n'est jamais écrite sur disque par l'application.
"""
import os

import pandas as pd
from dotenv import load_dotenv

from .config import RACINE

MODELE_PAR_DEFAUT = "claude-sonnet-5-5"
MAX_MESSAGES_PROMPT = 80  # on échantillonne pour rester rapide et économique

load_dotenv(RACINE / ".env")


class ErreurIA(Exception):
    """Erreur lisible renvoyée à l'utilisateur (clé absente, quota, réseau…)."""


def obtenir_cle(cle: str | None = None) -> str | None:
    """Retourne la clé API disponible, ou None."""
    return (cle or os.environ.get("ANTHROPIC_API_KEY") or "").strip() or None


def interroger_claude(consigne: str, contenu: str, cle: str | None = None,
                      modele: str = MODELE_PAR_DEFAUT, max_tokens: int = 6000) -> str:
    """Envoie une consigne + des données à Claude et renvoie sa réponse texte.

    Raises:
        ErreurIA: si la clé manque ou si l'appel échoue (message en français).
    """
    cle_api = obtenir_cle(cle)
    if not cle_api:
        raise ErreurIA("Aucune clé API : saisissez-la dans la barre latérale ou définissez ANTHROPIC_API_KEY.")
    import anthropic
    try:
        client = anthropic.Anthropic(api_key=cle_api)
        rep = client.messages.create(
            model=modele, max_tokens=max_tokens, system=consigne,
            messages=[{"role": "user", "content": contenu}],
        )
    except anthropic.AuthenticationError as e:
        raise ErreurIA("Clé API invalide.") from e
    except anthropic.RateLimitError as e:
        raise ErreurIA("Limite de requêtes atteinte, réessayez dans un instant.") from e
    except anthropic.APIConnectionError as e:
        raise ErreurIA("Impossible de joindre l'API Claude (réseau).") from e
    except anthropic.APIError as e:
        raise ErreurIA(f"Erreur de l'API Claude : {e}") from e
    texte = "".join(bloc.text for bloc in rep.content if bloc.type == "text").strip()
    if not texte:
        # ex. limite de tokens atteinte pendant le raisonnement : on le dit au lieu d'afficher du vide
        types = ", ".join(bloc.type for bloc in rep.content) or "aucun"
        raise ErreurIA(f"Claude a renvoyé une réponse vide (arrêt : {rep.stop_reason}, blocs : {types}). Réessayez.")
    return texte


def echantillon_pour_prompt(df: pd.DataFrame, n: int = MAX_MESSAGES_PROMPT) -> str:
    """Met en forme un échantillon représentatif de messages pour le prompt."""
    echantillon = df.sample(min(n, len(df)), random_state=1) if len(df) else df
    return "\n".join(f"- [{r.sujet} | {r.note_finale:.1f}/5 | {r.categorie}] {r.texte[:300]}"
                     for r in echantillon.itertuples())


def statistiques_pour_prompt(df: pd.DataFrame) -> str:
    """Résumé chiffré du jeu de données, joint aux prompts pour ancrer les réponses."""
    par_sujet = df.groupby("sujet")["note_finale"].agg(["count", "mean"]).round(2)
    lignes = [f"{s}: {int(r['count'])} messages, note moyenne {r['mean']}" for s, r in par_sujet.iterrows()]
    return (f"{len(df)} messages ({df['date'].min():%d/%m/%Y} → {df['date'].max():%d/%m/%Y}). "
            f"Part négative : {(df['categorie'] == 'négatif').mean():.0%}.\n" + "\n".join(lignes))


def synthese_locale(df: pd.DataFrame) -> str:
    """Synthèse chiffrée simple, utilisée si aucune clé n'est disponible."""
    if df.empty:
        return "Aucun message sur la période."
    pire = df.groupby("sujet")["note_finale"].mean().idxmin()
    return (f"{len(df)} messages, note moyenne {df['note_finale'].mean():.2f}/5, "
            f"{(df['note_finale'] <= 2).mean():.0%} de messages négatifs. Sujet le moins bien noté : {pire}.")


def synthese_hebdo(df: pd.DataFrame, cle: str | None = None) -> str:
    """Synthèse en français des thèmes, tendances et points d'alerte (Claude)."""
    consigne = ("Tu es analyste data. Rédige en français une synthèse structurée en markdown : "
                "1) Vue d'ensemble, 2) Thèmes récurrents (avec exemples), 3) Points positifs, "
                "4) Points de friction, 5) Recommandations concrètes. Reste factuel, appuie-toi uniquement "
                "sur les données fournies et signale les limites (notes estimées par analyse de sentiment).")
    return interroger_claude(consigne, f"Statistiques :\n{statistiques_pour_prompt(df)}\n\n"
                                       f"Échantillon de messages :\n{echantillon_pour_prompt(df)}", cle)


def reponse_avis_negatif(texte: str, sujet: str, cle: str | None = None) -> str:
    """Rédige une réponse professionnelle et empathique à un message négatif."""
    consigne = ("Tu es community manager. Rédige en français une réponse courte (3-4 phrases), "
                "empathique et professionnelle, sans promesse irréaliste ni information inventée.")
    return interroger_claude(consigne, f"Sujet : {sujet}\nMessage à traiter :\n{texte}", cle, max_tokens=2000)


def veille_concurrentielle(df: pd.DataFrame, cle: str | None = None) -> str:
    """Compare les sujets entre eux : perception, forces, faiblesses, opportunités."""
    consigne = ("Tu es consultant en veille concurrentielle. Compare en français les sujets fournis : "
                "tableau markdown (sujet, perception dominante, forces, faiblesses) puis 3 opportunités. "
                "Appuie-toi uniquement sur les données.")
    blocs = []
    for sujet, g in df.groupby("sujet"):
        blocs.append(f"### {sujet} (note moyenne {g['note_finale'].mean():.2f})\n{echantillon_pour_prompt(g, 15)}")
    return interroger_claude(consigne, statistiques_pour_prompt(df) + "\n\n" + "\n\n".join(blocs), cle, max_tokens=8000)
