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
