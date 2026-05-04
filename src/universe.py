"""S&P 500 ticker universe loader, cached as parquet."""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "universe.parquet"
CACHE_TTL_DAYS = 7
HEADERS = {
    "User-Agent": "NewsLens/0.1 (educational project; contact: marin@example.com)"
}


def fetch_sp500() -> pd.DataFrame:
    """Pull current S&P 500 constituents from Wikipedia."""
    resp = requests.get(WIKI_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    df.columns = [c.strip() for c in df.columns]
    # Normalize tickers for Yahoo/Finnhub (BRK.B -> BRK-B)
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    df = df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]].copy()
    df.columns = ["ticker", "name", "sector", "sub_industry"]
    df["fetched_at"] = datetime.now(timezone.utc)
    return df


def load_universe(force_refresh: bool = False) -> pd.DataFrame:
    """Return cached universe; refetch if cache is stale or missing."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not force_refresh and CACHE_PATH.exists():
        df = pd.read_parquet(CACHE_PATH)
        age_days = (datetime.now(timezone.utc) - df["fetched_at"].max()).days
        if age_days < CACHE_TTL_DAYS:
            return df

    df = fetch_sp500()
    df.to_parquet(CACHE_PATH, index=False)
    return df


if __name__ == "__main__":
    df = load_universe(force_refresh=True)
    print(f"Loaded {len(df)} tickers")
    print(df.head())
    print(f"\nSectors ({df['sector'].nunique()}):")
    print(df["sector"].value_counts())