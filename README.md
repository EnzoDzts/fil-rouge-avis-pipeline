# Application Data Pipeline — Avis (Collecte · Stockage · Analyse · Dashboard)

Projet Fil Rouge Avancé — EMLV MSID, Introduction à Python 2026-2027. 100 % Python.

## Architecture
| Étape | Module | Contenu |
|---|---|---|
| Collecte | `src/avis_pipeline/collecte.py` | **API publique Mastodon** (messages français par hashtag, sans clé, pagination), scraper Trustpilot optionnel, export CSV, données de démo |
| Stockage | `stockage.py` | SQLite, tables `sources` et `avis`, insertion incrémentale (contrainte `UNIQUE`) |
| Analyse | `analyse.py` | Stats pandas, évolution mensuelle, top mots, nuage de mots, sentiment naïf (lexique FR + négations) vs VADER |
| Dashboard | `dashboard.py` | Streamlit + Plotly, filtres source/entreprise/date/note, graphiques dynamiques |
| Extension | `ia.py` | Synthèse via l'API Claude (repli sur une synthèse locale sans clé `ANTHROPIC_API_KEY`) |

## Installation
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Utilisation
```bash
export PYTHONPATH=src
python -m avis_pipeline.cli --mastodon sncf ratp universite --pages 6   # VRAIES données (API publique)
python -m avis_pipeline.cli --demo                                      # données fictives (hors ligne)
streamlit run dashboard.py
pytest
```

## Limites connues
- Les messages Mastodon n'ont pas de note : elle est **estimée** (1 à 5) depuis le sentiment naïf. C'est une approximation, pas une vraie note.
- Seuls les messages publics en français sont gardés (champ `language`).
- Le scraper Trustpilot est souvent bloqué (HTTP 403) : il s'arrête proprement. Respectez CGU et robots.txt.
- VADER est conçu pour l'anglais ; piste d'amélioration : CamemBERT.
