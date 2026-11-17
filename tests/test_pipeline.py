"""Tests unitaires du pipeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from avis_pipeline import analyse, collecte, stockage


def test_pas_de_doublons(tmp_path):
    base = tmp_path / "t.db"
    avis = collecte.generer_donnees_demo(20)
    assert stockage.inserer_avis(avis, base) == 20
    assert stockage.inserer_avis(avis, base) == 0
    assert len(stockage.charger_avis(base)) == 20


def test_sentiment_naif_signe():
    assert analyse.sentiment_naif("Excellent service, je recommande") > 0
    assert analyse.sentiment_naif("Nul et décevant") < 0


def test_extraction_html_invalide():
    assert collecte.extraire_avis_depuis_html("<html></html>", "x") == []


def test_top_mots():
    assert analyse.top_mots(["service service rapide"], 1) == [("service", 2)]


def test_nettoyer_html_mastodon():
    assert collecte.nettoyer_html("<p>Le <b>train</b> est   en retard</p>") == "Le train est en retard"


def test_sentiment_negation():
    assert analyse.sentiment_naif("ce n'est pas bien") <= 0 or analyse.sentiment_naif("pas bien") < 0


def test_note_nulle_acceptee(tmp_path):
    base = tmp_path / "m.db"
    avis = [{"source": "mastodon", "entreprise": "sncf", "auteur": "a", "note": None,
             "date": "2026-01-01", "texte": "retard encore", "id_externe": "1"}]
    assert stockage.inserer_avis(avis, base) == 1
