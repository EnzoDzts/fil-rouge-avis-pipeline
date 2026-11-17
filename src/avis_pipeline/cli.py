"""Ligne de commande : python -m avis_pipeline.cli --sujets sncf ratp --pages 4"""
import argparse
import logging

from . import collecte, stockage

SUJETS_PAR_DEFAUT = ["sncf", "ratp", "universite", "grève", "ecole", "emlv", "transports"]


def main() -> None:
    """Collecte (ou génère des données de démo), sauvegarde le CSV et alimente SQLite."""
    parseur = argparse.ArgumentParser(description="Pipeline de collecte d'avis (API publiques)")
    parseur.add_argument("--sujets", nargs="+", default=SUJETS_PAR_DEFAUT, help="hashtags / mots-clés")
    parseur.add_argument("--pages", type=int, default=4, help="pages par source et par sujet")
    parseur.add_argument("--demo", action="store_true", help="données fictives hors ligne")
    args = parseur.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    avis = collecte.generer_donnees_demo() if args.demo else collecte.collecter_tout(args.sujets, args.pages)
    if not avis:
        print("Aucun avis collecté (API indisponible ?). Essayez --demo.")
        return
    collecte.sauvegarder_csv(avis)
    print(f"{len(avis)} messages collectés, {stockage.inserer_avis(avis)} nouveaux insérés.")


if __name__ == "__main__":
    main()
