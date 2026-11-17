"""Tests unitaires du pipeline."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from avis_pipeline import analyse, collecte, stockage


def avis_exemple(i="1", texte="retard encore une fois"):
    return {"source": "mastodon:x", "sujet": "sncf", "auteur": "a", "note": None, "date": "2026-01-01T10:00:00",
            "texte": texte, "id_externe": i, "engagement": 3, "url": "", "type": "message"}


def test_pas_de_doublons(tmp_path):
    base = tmp_path / "t.db"
    avis = collecte.generer_donnees_demo(20)
    assert stockage.inserer_avis(avis, base) == 20
    assert stockage.inserer_avis(avis, base) == 0
    assert len(stockage.charger_avis(base)) == 20


def test_note_nulle_acceptee(tmp_path):
    assert stockage.inserer_avis([avis_exemple()], tmp_path / "m.db") == 1


def test_sentiment_naif_signe():
    assert analyse.sentiment_naif("Excellent service, je recommande") > 0
    assert analyse.sentiment_naif("Nul et décevant") < 0


def test_sentiment_negation():
    assert analyse.sentiment_naif("pas bien du tout") < 0


def test_nettoyer_html():
    assert collecte.nettoyer_html("<p>Le <b>train</b> est   en retard</p>") == "Le train est en retard"


def test_top_mots_et_bigrammes():
    assert analyse.top_mots(["service service rapide"], 1) == [("service", 2)]
    assert analyse.top_bigrammes(["train retard train retard"], 1)[0][0] == "train retard"


def test_pipeline_analyse_complete(tmp_path):
    base = tmp_path / "d.db"
    stockage.inserer_avis(collecte.generer_donnees_demo(120), base)
    df = analyse.ajouter_sentiments(stockage.charger_avis(base))
    assert {"categorie", "jour_semaine", "heure", "note_finale"} <= set(df.columns)
    assert analyse.heatmap_activite(df).shape[0] == 7
    assert "theme" in analyse.detecter_themes(df).columns
    assert isinstance(analyse.evolution(df, "M"), pd.DataFrame)


def test_alertes():
    df = pd.DataFrame({"sujet": ["a"] * 12, "note_finale": [1.0] * 12})
    assert len(analyse.alertes(df)) == 1


def test_collecte_api_indisponible(monkeypatch):
    monkeypatch.setattr(collecte, "requete_json", lambda *a, **k: None)
    assert collecte.collecter_mastodon("sncf", 2) == []
    assert collecte.collecter_lemmy("sncf", 1) == []
