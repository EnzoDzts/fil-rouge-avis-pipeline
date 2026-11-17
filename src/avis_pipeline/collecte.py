"""Collecte multi-sources via des API PUBLIQUES sans clé (Mastodon, Lemmy) + extras.

Toutes les fonctions renvoient des dictionnaires au même format (voir CHAMPS),
ce qui permet d'ajouter une source sans toucher au stockage ni à l'analyse.
"""
import csv
import hashlib
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta

from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .config import CHEMIN_CSV_BRUT, DELAI_ENTRE_REQUETES_S, USER_AGENT

journal = logging.getLogger(__name__)
CHAMPS = ["source", "sujet", "auteur", "note", "date", "texte", "id_externe", "engagement", "url", "type"]

INSTANCES_MASTODON = ["mastodon.social", "piaille.fr", "mamot.fr"]
INSTANCE_LEMMY = "jlai.lu"  # communauté francophone


MOTIF_MENTION = re.compile(r"@[\w.-]+(?:@[\w.-]+)?")


def pseudonymiser(auteur: str) -> str:
    """Remplace un identifiant par un pseudonyme stable (hachage salé) : protège les données personnelles.

    Le sel peut être fixé via la variable d'environnement PSEUDO_SEL.
    """
    sel = os.environ.get("PSEUDO_SEL", "observatoire-avis")
    return "u_" + hashlib.sha256(f"{sel}:{auteur}".encode()).hexdigest()[:10]


def anonymiser_texte(texte: str) -> str:
    """Masque les mentions @utilisateur présentes dans un texte."""
    return MOTIF_MENTION.sub("@utilisateur", texte)


def url_sure(url: str | None) -> str:
    """Ne conserve que les liens http(s) (refuse javascript:, data:, etc.)."""
    return url if url and url.lower().startswith(("http://", "https://")) else ""


def nettoyer_html(contenu: str) -> str:
    """Retire les balises HTML, masque les mentions et normalise les espaces."""
    texte = " ".join(BeautifulSoup(contenu or "", "html.parser").get_text(" ").split())
    return anonymiser_texte(texte)


def requete_json(url: str, params: dict | None = None, tentatives: int = 3):
    """GET JSON avec nouvelles tentatives (les API publiques sont parfois lentes).

    Returns:
        Le JSON décodé, ou None si toutes les tentatives échouent.
    """
    for essai in range(1, tentatives + 1):
        try:
            rep = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
            rep.raise_for_status()
            return rep.json()
        except (requests.RequestException, ValueError) as erreur:
            journal.warning("Tentative %d/%d échouée pour %s : %s", essai, tentatives, url, erreur)
            time.sleep(DELAI_ENTRE_REQUETES_S * essai)
    return None


def collecter_mastodon(hashtag: str, pages: int = 5, instance: str = "mastodon.social") -> list[dict]:
    """Messages publics français d'un hashtag (API Mastodon, pagination par max_id)."""
    url = f"https://{instance}/api/v1/timelines/tag/{quote(hashtag, safe='')}"
    resultats, max_id = [], None
    for _ in range(pages):
        params = {"limit": 40, **({"max_id": max_id} if max_id else {})}
        messages = requete_json(url, params)
        if not messages:
            break
        for m in messages:
            texte = nettoyer_html(m["content"])
            if m.get("language") == "fr" and len(texte) > 20 and not m.get("reblog"):
                resultats.append({
                    "source": f"mastodon:{instance}", "sujet": hashtag.lower(),
                    "auteur": pseudonymiser(m["account"]["acct"]), "note": None,
                    "date": m["created_at"][:19], "texte": texte, "id_externe": f"{instance}-{m['id']}",
                    "engagement": m["favourites_count"] + m["reblogs_count"] + m["replies_count"],
                    "url": url_sure(m.get("url")), "type": "message",
                })
        max_id = messages[-1]["id"]
        time.sleep(DELAI_ENTRE_REQUETES_S)
    return resultats


def collecter_lemmy(mot_cle: str, pages: int = 3, instance: str = INSTANCE_LEMMY) -> list[dict]:
    """Posts et commentaires français contenant un mot-clé (API Lemmy publique).

    Le score (upvotes - downvotes) sert de mesure d'engagement.
    """
    url = f"https://{instance}/api/v3/search"
    resultats = []
    for type_ in ("Posts", "Comments"):
        for page in range(1, pages + 1):
            data = requete_json(url, {"q": mot_cle, "type_": type_, "sort": "New", "limit": 40, "page": page})
            elements = (data or {}).get("posts" if type_ == "Posts" else "comments", [])
            if not elements:
                break
            for e in elements:
                if type_ == "Posts":
                    brut = f"{e['post']['name']}. {e['post'].get('body') or ''}"
                    identifiant, date, lien = f"p{e['post']['id']}", e["post"]["published"], e["post"].get("ap_id", "")
                else:
                    brut = e["comment"]["content"]
                    identifiant, date, lien = f"c{e['comment']['id']}", e["comment"]["published"], e["comment"].get("ap_id", "")
                texte = anonymiser_texte(" ".join(brut.split()))
                if len(texte) < 20 or e["comment" if type_ == "Comments" else "post"].get("removed"):
                    continue
                resultats.append({
                    "source": f"lemmy:{instance}", "sujet": mot_cle.lower(), "auteur": pseudonymiser(e["creator"]["name"]),
                    "note": None, "date": date[:19], "texte": texte[:2000],
                    "id_externe": f"{instance}-{identifiant}", "engagement": e["counts"]["score"],
                    "url": url_sure(lien), "type": "post" if type_ == "Posts" else "commentaire",
                })
            time.sleep(DELAI_ENTRE_REQUETES_S)
    return resultats


def collecter_tout(sujets: list[str], pages: int = 4) -> list[dict]:
    """Collecte chaque sujet sur toutes les sources (Mastodon x instances + Lemmy)."""
    avis = []
    for sujet in sujets:
        for instance in INSTANCES_MASTODON:
            avis += collecter_mastodon(sujet, pages, instance)
        avis += collecter_lemmy(sujet, max(1, pages // 2))
        journal.info("Sujet %s : %d avis cumulés", sujet, len(avis))
    return avis


_POSITIFS = ["Excellent service, très réactif.", "Équipe au top, je recommande.", "Très bonne expérience, merci.",
             "Super ambiance et personnel agréable."]
_NEUTRES = ["Correct sans plus.", "Quelques bons points, d'autres moins.", "Expérience moyenne."]
_NEGATIFS = ["Retard énorme, très décevant.", "Frais élevés pour un service médiocre.",
             "Organisation catastrophique, je déconseille.", "Aucune réponse, nul."]


def generer_donnees_demo(nb_avis: int = 300, graine: int = 42) -> list[dict]:
    """Génère des avis FICTIFS reproductibles pour tester hors ligne."""
    hasard = random.Random(graine)
    qualite = {"sncf": 0.45, "ratp": 0.5, "universite": 0.65, "emlv": 0.7}
    debut = datetime(2025, 1, 1)
    avis = []
    for i in range(nb_avis):
        sujet = hasard.choice(list(qualite))
        note = min(5, max(1, round(hasard.gauss(1 + 4 * qualite[sujet], 1.1))))
        phrases = _POSITIFS if note >= 4 else _NEUTRES if note == 3 else _NEGATIFS
        avis.append({
            "source": hasard.choice(["demo:google_maps", "demo:trustpilot"]), "sujet": sujet,
            "auteur": f"Utilisateur{hasard.randint(1, 500)}", "note": note,
            "date": (debut + timedelta(minutes=hasard.randint(0, 680 * 1440))).isoformat(timespec="seconds"),
            "texte": " ".join(hasard.sample(phrases, k=2)), "id_externe": f"demo-{i}",
            "engagement": hasard.randint(0, 30), "url": "", "type": "avis",
        })
    return avis


def sauvegarder_csv(avis: list[dict], chemin=CHEMIN_CSV_BRUT) -> None:
    """Sauvegarde les avis bruts au format CSV."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=CHAMPS)
        ecrivain.writeheader()
        ecrivain.writerows(avis)
