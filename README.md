# 📊 Observatoire d'avis — Data Pipeline 100 % Python

Projet Fil Rouge Avancé — EMLV MSID, Introduction à Python 2026-2027.
Collecte → Stockage → Analyse NLP → Dashboard interactif, uniquement avec des **API publiques sans clé**.

## Fonctionnalités
| Étape | Module | Contenu |
|---|---|---|
| Collecte | `collecte.py` | **Mastodon** (mastodon.social, piaille.fr, mamot.fr) + **Lemmy** (jlai.lu, posts et commentaires) ; messages français, pagination, nouvelles tentatives ; export CSV ; mode démo |
| Stockage | `stockage.py` | SQLite (`sources`, `avis`), index, insertion incrémentale sans doublon, engagement/URL/type |
| Analyse | `analyse.py` | Sentiment naïf FR (négations) vs VADER, note estimée, évolution, heatmap jour×heure, mots, bigrammes, nuage de mots, thèmes (TF-IDF + KMeans), auteurs, alertes |
| Dashboard | `dashboard.py` | Streamlit thème sombre, 7 onglets, 6 filtres, ~15 graphiques Plotly, export CSV |
| Extension IA | `ia.py` | **API Claude** : synthèse hebdomadaire, veille concurrentielle, réponse automatique aux messages négatifs (onglet 🤖 IA) ; clé via saisie dans l'app, `ANTHROPIC_API_KEY` ou `.env` |
| Collecte continue | `scheduler.py` | APScheduler : collecte périodique + alerte si la note moyenne d'un sujet chute |
| Déploiement | `Dockerfile` | Image prête à l'emploi |
| Exploration | `notebooks/S5_analyse_exploratoire.ipynb` | Notebook pandas documenté |

## Installation
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
```

## Activer l'IA (Claude)
Créez une clé sur https://console.anthropic.com puis, au choix : la coller dans l'onglet 🤖 IA du dashboard (gardée en mémoire de session), ou `cp .env.example .env` et la renseigner. `.env` est ignoré par git.

## Utilisation
```bash
python -m avis_pipeline.cli                              # collecte les sujets par défaut (~3 500 messages)
python -m avis_pipeline.cli --sujets sncf metro --pages 3
python -m avis_pipeline.cli --demo                       # données fictives hors ligne
streamlit run dashboard.py                               # dashboard sur http://localhost:8501
python -m avis_pipeline.scheduler --minutes 30           # collecte continue + alertes
pytest                                                   # tests
docker build -t avis . && docker run -p 8501:8501 avis
```

## Limites connues
- Les messages Mastodon/Lemmy n'ont pas de note : elle est **estimée** (1-5) depuis le sentiment naïf, une approximation.
- Seuls les messages français sont conservés (champ `language` Mastodon ; instance francophone pour Lemmy).
- VADER est conçu pour l'anglais ; piste d'amélioration : CamemBERT (HuggingFace).
- Les API publiques peuvent être lentes ou indisponibles : le collecteur réessaie puis s'arrête proprement.
