"""Point d'entrée en ligne de commande : python -m avis_pipeline.cli collecte --demo."""
import argparse
import logging

from . import collecte, stockage


def main() -> None:
    """Exécute la collecte, sauvegarde le CSV brut et alimente SQLite."""
    parseur = argparse.ArgumentParser(description="Pipeline de collecte d'avis")
    parseur.add_argument("--demo", action="store_true", help="utiliser des données fictives")
    parseur.add_argument("--domaine", default="www.boursorama.com", help="domaine Trustpilot")
    parseur.add_argument("--pages", type=int, default=3)
    args = parseur.parse_args()
    logging.basicConfig(level=logging.INFO)

    avis = collecte.generer_donnees_demo() if args.demo else collecte.scraper_trustpilot(args.domaine, args.pages)
    if not avis:
        print("Aucun avis collecté (site bloqué ?). Relancez avec --demo.")
        return
    collecte.sauvegarder_csv(avis)
    print(f"{len(avis)} avis collectés, {stockage.inserer_avis(avis)} nouveaux insérés.")


if __name__ == "__main__":
    main()
