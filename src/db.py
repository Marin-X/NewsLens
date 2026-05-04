"""SQLite schema and connection helpers."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "news.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT    NOT NULL,
    headline    TEXT    NOT NULL,
    summary     TEXT,
    source      TEXT,
    url         TEXT,
    published   TIMESTAMP NOT NULL,
    fetched_at  TIMESTAMP NOT NULL,
    finnhub_id  INTEGER,
    UNIQUE(ticker, finnhub_id)
);

CREATE INDEX IF NOT EXISTS idx_articles_ticker_published
    ON articles(ticker, published);

CREATE INDEX IF NOT EXISTS idx_articles_published
    ON articles(published);

CREATE TABLE IF NOT EXISTS sentiment (
    article_id  INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    label       TEXT    NOT NULL,
    score_pos   REAL    NOT NULL,
    score_neu   REAL    NOT NULL,
    score_neg   REAL    NOT NULL,
    compound    REAL    NOT NULL,
    scored_at   TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT    NOT NULL,
    fetched_at  TIMESTAMP NOT NULL,
    n_articles  INTEGER NOT NULL,
    status      TEXT    NOT NULL,
    error       TEXT
);
"""


def _adapt_datetime(dt: datetime) -> str:
    """Store all datetimes as ISO-8601 UTC strings."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _convert_timestamp(blob: bytes) -> datetime:
    """Parse stored ISO-8601 string back to aware UTC datetime."""
    return datetime.fromisoformat(blob.decode())


sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("TIMESTAMP", _convert_timestamp)


def get_conn() -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        DB_PATH,
        isolation_level=None,  # autocommit
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if missing."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")