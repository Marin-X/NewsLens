"""Pull company news from Finnhub and persist to SQLite. Chunked by month."""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import finnhub
from dotenv import load_dotenv
from tqdm import tqdm

from db import get_conn
from universe import load_universe

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

API_KEY = os.getenv("FINNHUB_API_KEY")
if not API_KEY:
    raise RuntimeError("FINNHUB_API_KEY not set. Check .env at project root.")

# Finnhub free tier: 60 requests/min. Leave headroom.
SLEEP_BETWEEN_CALLS = 1.1
RATE_LIMIT_BACKOFF = 65.0
CHUNK_DAYS = 30  # Finnhub returns at most ~1 month of news per call cleanly


def _client() -> finnhub.Client:
    return finnhub.Client(api_key=API_KEY)


def _date_chunks(start: datetime, end: datetime, chunk_days: int = CHUNK_DAYS):
    """Yield (chunk_start, chunk_end) pairs covering [start, end] in chunk_days windows."""
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=chunk_days), end)
        yield cur, nxt
        cur = nxt


def _insert_articles(
        conn: sqlite3.Connection, ticker: str, raw_items: list[dict]
) -> int:
    """Insert deduped articles. Returns rows actually inserted."""
    now = datetime.now(timezone.utc)
    rows = []
    for item in raw_items:
        ts = item.get("datetime")
        if not ts:
            continue
        published = datetime.fromtimestamp(ts, tz=timezone.utc)
        rows.append(
            (
                ticker,
                item.get("headline") or "",
                item.get("summary") or "",
                item.get("source") or "",
                item.get("url") or "",
                published,
                now,
                item.get("id"),
            )
        )
    if not rows:
        return 0

    cur = conn.executemany(
        """
        INSERT OR IGNORE INTO articles
            (ticker, headline, summary, source, url, published, fetched_at, finnhub_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return cur.rowcount or 0


def _log_ingestion(
        conn: sqlite3.Connection,
        ticker: str,
        n_articles: int,
        status: str,
        error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_log (ticker, fetched_at, n_articles, status, error)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ticker, datetime.now(timezone.utc), n_articles, status, error),
    )


def fetch_ticker_chunk(
        ticker: str,
        start: datetime,
        end: datetime,
        client: finnhub.Client,
) -> list[dict]:
    """Pull company news for one ticker in a single chunk window."""
    return client.company_news(
        ticker,
        _from=start.strftime("%Y-%m-%d"),
        to=end.strftime("%Y-%m-%d"),
    )


def ingest(
        tickers: Iterable[str] | None = None,
        days_back: int = 90,
        limit: int | None = None,
) -> dict:
    """Ingest news for given tickers (or full S&P 500) over the lookback window."""
    if tickers is None:
        universe = load_universe()
        tickers = universe["ticker"].tolist()
    tickers = list(tickers)
    if limit:
        tickers = tickers[:limit]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    chunks = list(_date_chunks(start, end))
    n_calls = len(tickers) * len(chunks)
    eta_min = n_calls * SLEEP_BETWEEN_CALLS / 60.0
    log.info(
        "Ingesting %d tickers x %d chunks = %d API calls (~%.0f min)",
        len(tickers), len(chunks), n_calls, eta_min,
    )
    log.info("Window: %s -> %s", start.date(), end.date())

    client = _client()
    totals = {"tickers_ok": 0, "tickers_failed": 0, "articles_new": 0, "calls": 0}

    with get_conn() as conn:
        for ticker in tqdm(tickers, desc="Tickers"):
            ticker_inserted = 0
            ticker_failed = False
            for chunk_start, chunk_end in chunks:
                try:
                    raw = fetch_ticker_chunk(ticker, chunk_start, chunk_end, client)
                    inserted = _insert_articles(conn, ticker, raw)
                    ticker_inserted += inserted
                    totals["calls"] += 1
                except finnhub.FinnhubAPIException as e:
                    if "429" in str(e) or "limit" in str(e).lower():
                        log.warning("Rate-limited on %s, sleeping %.0fs", ticker, RATE_LIMIT_BACKOFF)
                        time.sleep(RATE_LIMIT_BACKOFF)
                        continue
                    log.error("API error on %s [%s..%s]: %s",
                              ticker, chunk_start.date(), chunk_end.date(), e)
                    _log_ingestion(conn, ticker, 0, "api_error", str(e))
                    ticker_failed = True
                    break
                except Exception as e:
                    log.error("Unexpected error on %s: %s", ticker, e)
                    _log_ingestion(conn, ticker, 0, "error", str(e))
                    ticker_failed = True
                    break
                time.sleep(SLEEP_BETWEEN_CALLS)

            if ticker_failed:
                totals["tickers_failed"] += 1
            else:
                _log_ingestion(conn, ticker, ticker_inserted, "ok")
                totals["tickers_ok"] += 1
                totals["articles_new"] += ticker_inserted

    log.info("Done. %s", totals)
    return totals


if __name__ == "__main__":
    # 90-day backfill across full S&P 500
    result = ingest(days_back=90)
    print("\nResult:", result)

    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        sample = conn.execute(
            "SELECT ticker, published, headline FROM articles "
            "ORDER BY published DESC LIMIT 5"
        ).fetchall()
    print(f"\nTotal articles in DB: {n}")
    print("\nMost recent 5:")
    for ticker, pub, headline in sample:
        print(f"  [{ticker}] {pub:%Y-%m-%d %H:%M}  {headline[:80]}")