"""Signal construction: convert article-level sentiment into daily per-ticker alpha factors.

Five signal variants, three rolling horizons, cross-sectional z-scoring, and
decay-weighted forward fill across non-news days.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from db import get_conn
from universe import load_universe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("signals")

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "signals.parquet"

# Signal hyperparameters
INTRADAY_HALFLIFE_HOURS = 6.0      # exponential decay within a trading day
CARRY_HALFLIFE_DAYS = 2.0          # decay-weighted forward fill across silent days
CARRY_MAX_DAYS = 5                 # cap how far we carry stale sentiment
ROLLING_HORIZONS = (1, 5, 21)      # daily, weekly, monthly


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_scored() -> pd.DataFrame:
    """Pull scored articles + sector metadata into one DataFrame."""
    universe = load_universe()[["ticker", "sector"]]

    with get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT a.id, a.ticker, a.published,
                   s.compound, s.score_pos, s.score_neg, s.score_neu, s.label
            FROM articles a
            JOIN sentiment s ON s.article_id = a.id
            """,
            conn,
            parse_dates=["published"],
        )

    df = df.merge(universe, on="ticker", how="left")
    df["sector"] = df["sector"].fillna("Unknown")
    df["date"] = df["published"].dt.tz_convert("UTC").dt.normalize()
    log.info("Loaded %d scored articles across %d tickers", len(df), df["ticker"].nunique())
    return df


# ---------------------------------------------------------------------------
# Variant 1: equal-weight mean
# ---------------------------------------------------------------------------

def signal_mean(df: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight average compound per ticker-day."""
    g = df.groupby(["date", "ticker"], as_index=False).agg(
        raw=("compound", "mean"),
        n_articles=("compound", "size"),
    )
    g["variant"] = "mean"
    return g


# ---------------------------------------------------------------------------
# Variant 2: intraday exponential decay (vectorized)
# ---------------------------------------------------------------------------

def signal_decay(df: pd.DataFrame, halflife_hours: float = INTRADAY_HALFLIFE_HOURS) -> pd.DataFrame:
    """Exponentially weight intraday articles so newer ones dominate the day's score."""
    lam = np.log(2.0) / halflife_hours
    work = df[["date", "ticker", "published", "compound"]].copy()

    # Latest article timestamp per ticker-day, broadcast back to each row
    work["latest"] = work.groupby(["date", "ticker"])["published"].transform("max")
    work["hours_back"] = (work["latest"] - work["published"]).dt.total_seconds() / 3600.0
    work["weight"] = np.exp(-lam * work["hours_back"])
    work["wc"] = work["weight"] * work["compound"]

    g = work.groupby(["date", "ticker"], as_index=False).agg(
        wc_sum=("wc", "sum"),
        w_sum=("weight", "sum"),
        n_articles=("compound", "size"),
    )
    g["raw"] = g["wc_sum"] / g["w_sum"].replace(0, np.nan)
    g["variant"] = "decay"
    return g[["date", "ticker", "raw", "n_articles", "variant"]]


# ---------------------------------------------------------------------------
# Variant 3: volume-scaled
# ---------------------------------------------------------------------------

def signal_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Sentiment * log(1 + n_articles). Captures conviction via news volume."""
    g = df.groupby(["date", "ticker"], as_index=False).agg(
        mean_compound=("compound", "mean"),
        n_articles=("compound", "size"),
    )
    g["raw"] = g["mean_compound"] * np.log1p(g["n_articles"])
    g["variant"] = "volume"
    return g[["date", "ticker", "raw", "n_articles", "variant"]]


# ---------------------------------------------------------------------------
# Variant 4: sector-relative z-score
# ---------------------------------------------------------------------------

def signal_sector_relative(df: pd.DataFrame) -> pd.DataFrame:
    """Daily mean compound, z-scored within GICS sector per day."""
    daily = df.groupby(["date", "ticker", "sector"], as_index=False).agg(
        mean_compound=("compound", "mean"),
        n_articles=("compound", "size"),
    )

    grouped = daily.groupby(["date", "sector"])["mean_compound"]
    daily["sector_mean"] = grouped.transform("mean")
    daily["sector_std"] = grouped.transform("std").replace(0, np.nan)
    daily["raw"] = (daily["mean_compound"] - daily["sector_mean"]) / daily["sector_std"]
    daily["variant"] = "sector_relative"
    return daily[["date", "ticker", "raw", "n_articles", "variant"]]


# ---------------------------------------------------------------------------
# Variant 5: composite (decay + volume + sector-relative, equal-weight blend)
# ---------------------------------------------------------------------------

def signal_composite(
        decay: pd.DataFrame, volume: pd.DataFrame, sector_rel: pd.DataFrame
) -> pd.DataFrame:
    """Equal-weight blend of three z-scored signals."""
    def _z(s: pd.DataFrame) -> pd.DataFrame:
        s = s.copy()
        grouped = s.groupby("date")["raw"]
        s["z"] = (s["raw"] - grouped.transform("mean")) / grouped.transform("std").replace(0, np.nan)
        return s[["date", "ticker", "z", "n_articles"]]

    a = _z(decay).rename(columns={"z": "z_decay", "n_articles": "n_a"})
    b = _z(volume).rename(columns={"z": "z_vol", "n_articles": "n_b"})
    c = _z(sector_rel).rename(columns={"z": "z_sec", "n_articles": "n_c"})

    out = a.merge(b, on=["date", "ticker"], how="outer").merge(c, on=["date", "ticker"], how="outer")
    out["raw"] = out[["z_decay", "z_vol", "z_sec"]].mean(axis=1, skipna=True)
    out["n_articles"] = out[["n_a", "n_b", "n_c"]].max(axis=1)
    out["variant"] = "composite"
    return out[["date", "ticker", "raw", "n_articles", "variant"]]


# ---------------------------------------------------------------------------
# Cross-sectional z-score (per day, per variant)
# ---------------------------------------------------------------------------

def cross_sectional_z(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score `raw` within each (date, variant) cohort."""
    grouped = df.groupby(["date", "variant"])["raw"]
    mu = grouped.transform("mean")
    sd = grouped.transform("std").replace(0, np.nan)
    df = df.copy()
    df["z_score"] = (df["raw"] - mu) / sd
    return df


# ---------------------------------------------------------------------------
# Decay-weighted forward fill across silent days (explicit iteration)
# ---------------------------------------------------------------------------

def carry_forward(
        df: pd.DataFrame,
        halflife_days: float = CARRY_HALFLIFE_DAYS,
        max_days: int = CARRY_MAX_DAYS,
) -> pd.DataFrame:
    """For each ticker × variant, carry sentiment forward up to `max_days`,
    decaying exponentially. Adds rows; n_articles=0 on carried rows."""
    if df.empty:
        return df

    lam = np.log(2.0) / halflife_days
    full_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D", tz="UTC")
    n_dates = len(full_dates)
    out_parts = []

    for (ticker, variant), group in df.groupby(["ticker", "variant"], sort=False):
        g = group.set_index("date").reindex(full_dates)
        g.index.name = "date"
        g["ticker"] = ticker
        g["variant"] = variant

        observed = g["raw"].notna().to_numpy()
        idx = np.arange(n_dates)
        last_obs_pos = np.where(observed, idx, np.nan)
        last_obs_pos = pd.Series(last_obs_pos).ffill().to_numpy()
        days_since = idx - last_obs_pos
        days_since = np.where(np.isnan(days_since), np.inf, days_since)

        last_raw = g["raw"].ffill().to_numpy()
        last_z = g["z_score"].ffill().to_numpy()
        weight = np.exp(-lam * np.where(np.isfinite(days_since), days_since, 0.0))
        within = days_since <= max_days

        carried_raw = np.where(within, last_raw * weight, np.nan)
        carried_z = np.where(within, last_z * weight, np.nan)

        g["raw"] = np.where(observed, g["raw"].to_numpy(), carried_raw)
        g["z_score"] = np.where(observed, g["z_score"].to_numpy(), carried_z)
        g["n_articles"] = g["n_articles"].fillna(0).astype(int)

        out_parts.append(g.reset_index())

    out = pd.concat(out_parts, ignore_index=True)
    return out.dropna(subset=["raw"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Rolling horizons
# ---------------------------------------------------------------------------

def add_rolling_horizons(df: pd.DataFrame, horizons=ROLLING_HORIZONS) -> pd.DataFrame:
    """For each (ticker, variant), expand into 1d/5d/21d rolling means of z_score."""
    parts = []
    df = df.sort_values(["variant", "ticker", "date"])
    for h in horizons:
        sub = df.copy()
        if h == 1:
            sub["signal"] = sub["z_score"]
        else:
            sub["signal"] = (
                sub.groupby(["variant", "ticker"])["z_score"]
                .transform(lambda x: x.rolling(h, min_periods=max(1, h // 2)).mean())
            )
        sub["horizon"] = f"{h}d"
        parts.append(sub)
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_signals() -> pd.DataFrame:
    df = load_scored()

    log.info("Building variant: mean")
    s_mean = signal_mean(df)
    log.info("Building variant: decay")
    s_decay = signal_decay(df)
    log.info("Building variant: volume")
    s_volume = signal_volume(df)
    log.info("Building variant: sector_relative")
    s_sector = signal_sector_relative(df)
    log.info("Building variant: composite")
    s_composite = signal_composite(s_decay, s_volume, s_sector)

    all_variants = pd.concat([s_mean, s_decay, s_volume, s_sector, s_composite], ignore_index=True)
    all_variants = cross_sectional_z(all_variants)

    log.info("Carrying sentiment forward (halflife=%.1fd, max=%dd)", CARRY_HALFLIFE_DAYS, CARRY_MAX_DAYS)
    carried = carry_forward(all_variants)

    log.info("Expanding rolling horizons: %s", list(ROLLING_HORIZONS))
    final = add_rolling_horizons(carried)

    final["built_at"] = datetime.now(timezone.utc)
    log.info("Final signal frame: %d rows, %d variants × %d horizons",
             len(final), final["variant"].nunique(), final["horizon"].nunique())
    return final


def save_signals(df: pd.DataFrame) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    log.info("Saved -> %s", OUT_PATH)


if __name__ == "__main__":
    signals = build_signals()
    save_signals(signals)

    print("\nVariant × horizon coverage:")
    pivot = signals.pivot_table(
        index="variant", columns="horizon", values="signal", aggfunc="count", fill_value=0
    )
    print(pivot)

    print("\nTop 5 most positive composite-1d signals (most recent date):")
    latest = signals[(signals["variant"] == "composite") & (signals["horizon"] == "1d")]
    latest = latest[latest["date"] == latest["date"].max()]
    print(
        latest.nlargest(5, "signal")[["ticker", "n_articles", "raw", "z_score", "signal"]]
        .to_string(index=False)
    )

    print("\nTop 5 most negative composite-1d signals (most recent date):")
    print(
        latest.nsmallest(5, "signal")[["ticker", "n_articles", "raw", "z_score", "signal"]]
        .to_string(index=False)
    )