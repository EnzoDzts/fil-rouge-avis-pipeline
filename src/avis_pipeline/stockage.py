"""Stockage SQLite : schéma (sources, avis) et insertion sans doublons."""
import sqlite3
from contextlib import closing

import pandas as pd

from .config import CHEMIN_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS avis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    sujet TEXT NOT NULL,
    auteur TEXT,
    note INTEGER CHECK (note IS NULL OR note BETWEEN 1 AND 5),
    date TEXT NOT NULL,
    texte TEXT,
    id_externe TEXT NOT NULL,
    engagement INTEGER DEFAULT 0,
    url TEXT,
    type TEXT,
    UNIQUE (source_id, id_externe)
);
CREATE INDEX IF NOT EXISTS idx_avis_date ON avis(date);
CREATE INDEX IF NOT EXISTS idx_avis_sujet ON avis(sujet);
"""


def connecter(chemin=CHEMIN_DB) -> sqlite3.Connection:
    """Ouvre la base (créée si besoin) et applique le schéma."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin)
    conn.executescript(SCHEMA)
    return conn


def inserer_avis(avis: list[dict], chemin=CHEMIN_DB) -> int:
    """Insère les avis de façon incrémentale ; ignore les doublons.

    Returns:
        Le nombre d'avis réellement ajoutés.
    """
    with closing(connecter(chemin)) as conn:
        avant = conn.execute("SELECT COUNT(*) FROM avis").fetchone()[0]
        for a in avis:
            conn.execute("INSERT OR IGNORE INTO sources(nom) VALUES (?)", (a["source"],))
            source_id = conn.execute("SELECT id FROM sources WHERE nom=?", (a["source"],)).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO avis(source_id, sujet, auteur, note, date, texte, id_externe,"
                " engagement, url, type) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, a["sujet"], a["auteur"], a["note"], a["date"], a["texte"], a["id_externe"],
                 a.get("engagement", 0), a.get("url", ""), a.get("type", "")),
            )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM avis").fetchone()[0] - avant


def charger_avis(chemin=CHEMIN_DB) -> pd.DataFrame:
    """Charge tous les avis (jointure avec sources) dans un DataFrame."""
    with closing(connecter(chemin)) as conn:
        return pd.read_sql_query(
            "SELECT a.id, s.nom AS source, a.sujet, a.auteur, a.note, a.date, a.texte,"
            " a.engagement, a.url, a.type FROM avis a JOIN sources s ON s.id = a.source_id",
            conn, parse_dates=["date"],
        )


def anonymiser_base(chemin=CHEMIN_DB) -> int:
    """Pseudonymise les auteurs, masque les mentions et filtre les URL déjà en base.

    Returns:
        Le nombre de lignes modifiées.
    """
    from .collecte import anonymiser_texte, pseudonymiser, url_sure
    modifiees = 0
    with closing(connecter(chemin)) as conn:
        for id_, auteur, texte, url in conn.execute("SELECT id, auteur, texte, url FROM avis").fetchall():
            nouveau = (auteur if (auteur or "").startswith("u_") else pseudonymiser(auteur or ""),
                       anonymiser_texte(texte or ""), url_sure(url))
            if nouveau != (auteur, texte, url):
                conn.execute("UPDATE avis SET auteur=?, texte=?, url=? WHERE id=?", (*nouveau, id_))
                modifiees += 1
        conn.commit()
    return modifiees


def exporter_snapshot(chemin_csv, chemin=CHEMIN_DB) -> int:
    """Exporte la base en CSV (instantané versionnable, déjà pseudonymisé)."""
    with closing(connecter(chemin)) as conn:
        df = pd.read_sql_query(
            "SELECT s.nom AS source, a.sujet, a.auteur, a.note, a.date, a.texte, a.id_externe,"
            " a.engagement, a.url, a.type FROM avis a JOIN sources s ON s.id = a.source_id", conn)
    df.to_csv(chemin_csv, index=False)
    return len(df)


def amorcer_depuis_csv(chemin_csv, chemin=CHEMIN_DB) -> int:
    """Remplit la base depuis un CSV d'instantané (démarrage d'un déploiement sans base)."""
    df = pd.read_csv(chemin_csv).astype(object).where(lambda d: d.notna(), None)
    return inserer_avis(df.to_dict("records"), chemin)
