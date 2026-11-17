"""Configuration centrale du projet (chemins et constantes)."""
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_DATA = RACINE / "data"
CHEMIN_DB = DOSSIER_DATA / "avis.db"
CHEMIN_CSV_BRUT = DOSSIER_DATA / "avis_bruts.csv"
USER_AGENT = "Mozilla/5.0 (projet-pedagogique EMLV MSID)"
DELAI_ENTRE_REQUETES_S = 1.5
