"""yfinance OHLCV puller with caching to parquet."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf
from tqdm import tqdm

from universe import load_universe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prices")

# Quiet yfinance noise
for _name in ("yfinance", "urllib3", "peewee"):
    logging.getLogger(_name).setLevel(logging.WARNING)

PRICES_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.parquet"
DEFAULT_LOOKBACK_DAYS = 365
BATCH_SIZE = 50  # tickers per yfinance call; bigger = fewer calls but bigger payload


def _normalize_yf_frame(df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Convert yfinance's wide multi-ticker frame into long format."""
    if df.empty:
        return pd.DataFrame()

    # Single ticker -> flat columns; multi-ticker -> MultiIndex columns (Field, Ticker)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.stack(level=1, future_stack=True).reset_index()
        df = df.rename(columns={"Date": "date", "level_1": "ticker", "Ticker": "ticker"})
    else:
        df = df.reset_index().rename(columns={"Date": "date"})
        df["ticker"] = tickers[0]

    rename_map = {
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
    }
    df = df.rename(columns=rename_map)

    # Some yfinance versions return only 'Close' (already adjusted via auto_adjust=True)
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]

    keep = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    df = df[[c for c in keep if c in df.columns]].copy()

    # Ensure tz-naive UTC dates (yfinance gives tz-naive trading days)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.dropna(subset=["close"]).reset_index(drop=True)


def fetch_batch(tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    """Pull OHLCV for a batch of tickers."""
    raw = yf.download(
        tickers=tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=False,   # keep both close and adj_close
        progress=False,
        threads=True,
        group_by="column",
    )
    return _normalize_yf_frame(raw, tickers)


def fetch_prices(
        tickers: Iterable[str] | None = None,
        days_back: int = DEFAULT_LOOKBACK_DAYS,
        batch_size: int = BATCH_SIZE,
) -> pd.DataFrame:
    """Pull OHLCV for all tickers across the requested window."""
    if tickers is None:
        tickers = load_universe()["ticker"].tolist()
    tickers = list(tickers)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    log.info("Fetching %d tickers, %s -> %s", len(tickers), start.date(), end.date())

    all_parts = []
    for i in tqdm(range(0, len(tickers), batch_size), desc="Batches"):
        batch = tickers[i : i + batch_size]
        try:
            df = fetch_batch(batch, start, end)
            if not df.empty:
                all_parts.append(df)
        except Exception as e:
            log.warning("Batch failed (%s..%s): %s", batch[0], batch[-1], e)

    if not all_parts:
        log.error("No price data returned.")
        return pd.DataFrame()

    out = pd.concat(all_parts, ignore_index=True)
    out = out.drop_duplicates(subset=["ticker", "date"]).sort_values(["ticker", "date"])
    log.info("Got %d rows across %d tickers", len(out), out["ticker"].nunique())
    return out


def save_prices(df: pd.DataFrame) -> None:
    PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PRICES_PATH, index=False)
    log.info("Saved -> %s", PRICES_PATH)


def load_prices() -> pd.DataFrame:
    return pd.read_parquet(PRICES_PATH)


if __name__ == "__main__":
    df = fetch_prices()
    save_prices(df)

    print("\nShape:", df.shape)
    print("Date range:", df["date"].min().date(), "->", df["date"].max().date())
    print("Tickers:", df["ticker"].nunique())
    print("\nSample:")
    print(df.tail(8).to_string(index=False))