"""Forward return computation: close-to-close and open-to-open at multiple horizons."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from prices import load_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("returns")

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "returns.parquet"
HORIZONS = (1, 5, 21)


def compute_forward_returns(prices: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    """Compute close-to-close and open-to-open forward returns at each horizon.

    Conventions
    -----------
    - Signal date is T (the date row).
    - Close-to-close: r_co_h = adj_close[T+h] / adj_close[T] - 1
        (textbook; assumes you can trade at the close of T)
    - Open-to-open:   r_oo_h = open[T+1+h] / open[T+1] - 1
        (realistic; signal generated EOD T, enter open T+1, exit open T+1+h)
    """
    df = prices[["date", "ticker", "open", "adj_close"]].copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    out = df[["date", "ticker"]].copy()

    for h in horizons:
        # Close-to-close: future adj_close shifted by -h
        future_close = df.groupby("ticker", sort=False)["adj_close"].shift(-h)
        out[f"fwd_co_{h}d"] = future_close / df["adj_close"] - 1.0

        # Open-to-open: enter at open T+1, exit at open T+1+h
        entry_open = df.groupby("ticker", sort=False)["open"].shift(-1)
        exit_open = df.groupby("ticker", sort=False)["open"].shift(-(1 + h))
        out[f"fwd_oo_{h}d"] = exit_open / entry_open - 1.0

    return out


def coverage_summary(returns: pd.DataFrame) -> pd.DataFrame:
    """Per-column non-null counts and basic stats."""
    rcols = [c for c in returns.columns if c.startswith("fwd_")]
    rows = []
    for c in rcols:
        s = returns[c].dropna()
        rows.append(
            {
                "column": c,
                "n_obs": len(s),
                "mean_bps": float(s.mean() * 1e4),
                "std_bps": float(s.std() * 1e4),
                "min": float(s.min()),
                "max": float(s.max()),
            }
        )
    return pd.DataFrame(rows)


def save_returns(df: pd.DataFrame) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    log.info("Saved -> %s", OUT_PATH)


def load_returns() -> pd.DataFrame:
    return pd.read_parquet(OUT_PATH)


if __name__ == "__main__":
    prices = load_prices()
    log.info("Loaded %d price rows", len(prices))

    returns = compute_forward_returns(prices)
    log.info("Computed forward returns: %s", returns.shape)

    save_returns(returns)

    print("\nCoverage summary:")
    print(coverage_summary(returns).to_string(index=False))

    print("\nSample (most recent 8 rows for AAPL):")
    aapl = returns[returns["ticker"] == "AAPL"].tail(8)
    print(aapl.to_string(index=False))