"""Collecte des avis : scraping Trustpilot et génération de données de démo."""
import csv
import json
import logging
import random
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from .config import CHEMIN_CSV_BRUT, DELAI_ENTRE_REQUETES_S, USER_AGENT

journal = logging.getLogger(__name__)
CHAMPS = ["source", "entreprise", "auteur", "note", "date", "texte", "id_externe"]


def extraire_avis_depuis_html(html: str, entreprise: str) -> list[dict]:
    """Extrait les avis d'une page Trustpilot à partir du JSON __NEXT_DATA__.

    Args:
        html: code HTML de la page.
        entreprise: nom de l'entreprise (stocké avec chaque avis).

    Returns:
        Liste de dictionnaires (un par avis), vide si la structure est inconnue.
    """
    soupe = BeautifulSoup(html, "html.parser")
    balise = soupe.find("script", id="__NEXT_DATA__")
    if balise is None or not balise.string:
        return []
    try:
        reviews = json.loads(balise.string)["props"]["pageProps"]["reviews"]
    except (KeyError, json.JSONDecodeError):
        return []
    avis = []
    for r in reviews:
        avis.append({
            "source": "trustpilot",
            "entreprise": entreprise,
            "auteur": (r.get("consumer") or {}).get("displayName", "anonyme"),
            "note": int(r["rating"]),
            "date": r["dates"]["publishedDate"][:10],
            "texte": f'{r.get("title", "")}. {r.get("text", "")}'.strip(". "),
            "id_externe": r["id"],
        })
    return avis


def scraper_trustpilot(domaine: str, pages: int = 3) -> list[dict]:
    """Scrape les avis Trustpilot d'un domaine (ex. 'www.boursorama.com').

    S'arrête proprement si le site refuse la requête (403, blocage anti-bot).
    """
    resultats: list[dict] = []
    for page in range(1, pages + 1):
        url = f"https://fr.trustpilot.com/review/{domaine}?page={page}"
        try:
            rep = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            rep.raise_for_status()
        except requests.RequestException as erreur:
            journal.warning("Échec scraping %s : %s", url, erreur)
            break
        nouveaux = extraire_avis_depuis_html(rep.text, domaine)
        if not nouveaux:
            break
        resultats.extend(nouveaux)
        time.sleep(DELAI_ENTRE_REQUETES_S)
    return resultats


# Fragments de phrases pour générer des avis de démonstration plausibles.
_POSITIFS = ["Excellent service, très réactif.", "Équipe pédagogique au top, je recommande.",
             "Très bonne expérience, cursus enrichissant.", "Super campus et bonne ambiance."]
_NEUTRES = ["Correct sans plus.", "Quelques bons cours, d'autres moins intéressants.",
            "Expérience moyenne, peut mieux faire."]
_NEGATIFS = ["Administration injoignable, très décevant.", "Frais élevés pour un service médiocre.",
             "Organisation catastrophique, je déconseille.", "Aucune réponse à mes mails, nul."]


def generer_donnees_demo(nb_avis: int = 300, graine: int = 42) -> list[dict]:
    """Génère des avis synthétiques (reproductibles) pour tester sans réseau.

    Les données sont FICTIVES : elles servent uniquement à la démonstration.
    """
    hasard = random.Random(graine)
    ecoles = {"EMLV": 0.55, "ESSEC": 0.8, "ESCP": 0.75, "EDHEC": 0.7}
    sources = ["google_maps", "trustpilot"]
    debut = date(2025, 1, 1)
    avis = []
    for i in range(nb_avis):
        ecole = hasard.choice(list(ecoles))
        note = min(5, max(1, round(hasard.gauss(1 + 4 * ecoles[ecole], 1.1))))
        phrases = _POSITIFS if note >= 4 else _NEUTRES if note == 3 else _NEGATIFS
        avis.append({
            "source": hasard.choice(sources),
            "entreprise": ecole,
            "auteur": f"Utilisateur{hasard.randint(1, 500)}",
            "note": note,
            "date": (debut + timedelta(days=hasard.randint(0, 680))).isoformat(),
            "texte": " ".join(hasard.sample(phrases, k=2)),
            "id_externe": f"demo-{i}",
        })
    return avis


def sauvegarder_csv(avis: list[dict], chemin=CHEMIN_CSV_BRUT) -> None:
    """Sauvegarde les avis bruts au format CSV (livrable S3)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=CHAMPS)
        ecrivain.writeheader()
        ecrivain.writerows(avis)
