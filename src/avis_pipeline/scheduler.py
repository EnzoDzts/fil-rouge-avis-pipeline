"""Collecte continue (APScheduler) avec alerte si la note moyenne d'un sujet chute.

Lancement : python -m avis_pipeline.scheduler --minutes 30
"""
import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from . import analyse, collecte, stockage
from .cli import SUJETS_PAR_DEFAUT

journal = logging.getLogger(__name__)


def cycle(sujets: list[str], pages: int, seuil: float) -> None:
    """Un cycle : collecte, insertion incrémentale, puis détection d'alertes."""
    nouveaux = stockage.inserer_avis(collecte.collecter_tout(sujets, pages))
    journal.info("Cycle terminé : %d nouveaux messages", nouveaux)
    df = analyse.ajouter_sentiments(stockage.charger_avis())
    for ligne in analyse.alertes(df, seuil).itertuples():
        journal.warning("ALERTE : %s a une note moyenne de %.2f (< %.1f)", ligne.sujet, ligne.mean, seuil)


def main() -> None:
    """Planifie `cycle` à intervalle régulier."""
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--minutes", type=int, default=30)
    parseur.add_argument("--pages", type=int, default=2)
    parseur.add_argument("--seuil", type=float, default=2.5)
    args = parseur.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    planificateur = BlockingScheduler()
    planificateur.add_job(cycle, "interval", minutes=args.minutes, args=[SUJETS_PAR_DEFAUT, args.pages, args.seuil],
                          next_run_time=__import__("datetime").datetime.now())
    planificateur.start()


if __name__ == "__main__":
    main()
