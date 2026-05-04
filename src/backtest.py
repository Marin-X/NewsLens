"""Backtest engine: IC, decile portfolios, long-short spread, turnover.

For every (variant, horizon, return_convention) combo we report:
  - Mean IC and IC t-statistic across days
  - Decile portfolio mean returns (D1..D10)
  - Long-short (D10 - D1) mean, std, Sharpe, hit rate
  - Average daily turnover of the long and short legs
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from returns import load_returns
from signals import OUT_PATH as SIGNALS_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backtest")

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
SUMMARY_PATH = OUT_DIR / "backtest_summary.parquet"
IC_TS_PATH = OUT_DIR / "backtest_ic_timeseries.parquet"
DECILE_PATH = OUT_DIR / "backtest_decile_returns.parquet"

N_DECILES = 10
ANNUALIZATION = 252


# ---------------------------------------------------------------------------
# Data joining
# ---------------------------------------------------------------------------

def _load_signals() -> pd.DataFrame:
    df = pd.read_parquet(SIGNALS_PATH)
    # Strip tz so we can join on tz-naive returns dates
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df[["date", "ticker", "variant", "horizon", "signal", "n_articles"]]


def join_signals_returns() -> pd.DataFrame:
    sig = _load_signals()
    ret = load_returns()
    merged = sig.merge(ret, on=["date", "ticker"], how="inner")
    log.info("Joined: %d rows, %d unique dates", len(merged), merged["date"].nunique())
    return merged


# ---------------------------------------------------------------------------
# IC computation
# ---------------------------------------------------------------------------

def _spearman_safe(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 5 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan
    rho, _ = spearmanr(x, y)
    return float(rho)


def daily_ic(df: pd.DataFrame, signal_col: str, return_col: str) -> pd.Series:
    """Spearman IC per date. Returns Series indexed by date."""
    work = df[["date", signal_col, return_col]].dropna()
    return (
        work.groupby("date")
        .apply(lambda g: _spearman_safe(g[signal_col].to_numpy(), g[return_col].to_numpy()))
        .rename("ic")
    )


# ---------------------------------------------------------------------------
# Decile portfolios
# ---------------------------------------------------------------------------

def assign_deciles(df: pd.DataFrame, signal_col: str, n: int = N_DECILES) -> pd.Series:
    """Cross-sectional decile rank per day. 1 = lowest signal, n = highest."""
    def _rank(g: pd.DataFrame) -> pd.Series:
        s = g[signal_col]
        if s.notna().sum() < n:
            return pd.Series(np.nan, index=g.index)
        return pd.Series(pd.qcut(s.rank(method="first"), q=n, labels=False), index=g.index) + 1
    return df.groupby("date", group_keys=False).apply(_rank)


def decile_returns(df: pd.DataFrame, return_col: str, decile_col: str = "decile") -> pd.DataFrame:
    """Mean forward return by date × decile."""
    work = df.dropna(subset=[return_col, decile_col]).copy()
    work[decile_col] = work[decile_col].astype(int)
    out = work.groupby(["date", decile_col])[return_col].mean().reset_index()
    out = out.rename(columns={return_col: "ret", decile_col: "decile"})
    return out


# ---------------------------------------------------------------------------
# Turnover
# ---------------------------------------------------------------------------

def leg_turnover(df: pd.DataFrame, signal_col: str, decile_col: str = "decile") -> dict:
    """Average fraction of long/short leg that changes per day."""
    df = df.dropna(subset=[decile_col]).copy()
    df[decile_col] = df[decile_col].astype(int)

    longs = (
        df[df[decile_col] == N_DECILES]
        .groupby("date")["ticker"].apply(set).sort_index()
    )
    shorts = (
        df[df[decile_col] == 1]
        .groupby("date")["ticker"].apply(set).sort_index()
    )

    def _avg(series: pd.Series) -> float:
        if len(series) < 2:
            return np.nan
        diffs = []
        prev = None
        for s in series:
            if prev is not None:
                changed = len(prev.symmetric_difference(s)) / max(1, len(prev | s))
                diffs.append(changed)
            prev = s
        return float(np.mean(diffs)) if diffs else np.nan

    return {"long_turnover": _avg(longs), "short_turnover": _avg(shorts)}


# ---------------------------------------------------------------------------
# Per-combo backtest
# ---------------------------------------------------------------------------

def run_one(
        df: pd.DataFrame, variant: str, horizon: str, convention: str
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Return (summary_row, ic_timeseries, decile_panel) for one combo."""
    h_days = int(horizon.replace("d", ""))
    return_col = f"fwd_{convention}_{h_days}d"

    sub = df[(df["variant"] == variant) & (df["horizon"] == horizon)].copy()
    sub = sub.dropna(subset=["signal", return_col])

    summary = {
        "variant": variant,
        "horizon": horizon,
        "convention": convention,
        "n_obs": len(sub),
        "n_days": sub["date"].nunique(),
    }

    if sub.empty or sub["date"].nunique() < 2:
        summary.update({
            "ic_mean": np.nan, "ic_std": np.nan, "ic_tstat": np.nan, "ic_hit_rate": np.nan,
            "ls_mean_bps": np.nan, "ls_std_bps": np.nan, "ls_sharpe_ann": np.nan,
            "ls_hit_rate": np.nan, "long_turnover": np.nan, "short_turnover": np.nan,
        })
        return summary, pd.DataFrame(), pd.DataFrame()

    # IC time series
    ic_ts = daily_ic(sub, "signal", return_col).dropna()
    ic_mean = ic_ts.mean()
    ic_std = ic_ts.std()
    ic_t = (ic_mean / ic_std * np.sqrt(len(ic_ts))) if ic_std and len(ic_ts) > 1 else np.nan
    ic_hit = float((ic_ts > 0).mean()) if len(ic_ts) else np.nan

    # Deciles + LS spread
    sub["decile"] = assign_deciles(sub, "signal")
    dec = decile_returns(sub, return_col)

    # Long-short per day = D10 - D1
    pivot = dec.pivot(index="date", columns="decile", values="ret")
    if N_DECILES in pivot.columns and 1 in pivot.columns:
        ls = (pivot[N_DECILES] - pivot[1]).dropna()
    else:
        ls = pd.Series(dtype=float)

    ls_mean_bps = float(ls.mean() * 1e4) if len(ls) else np.nan
    ls_std_bps = float(ls.std() * 1e4) if len(ls) > 1 else np.nan
    # Per-period Sharpe scaled: scale by sqrt(252 / h) so we annualize correctly
    if ls_std_bps and len(ls) > 1:
        sharpe = (ls.mean() / ls.std()) * np.sqrt(ANNUALIZATION / h_days)
    else:
        sharpe = np.nan
    ls_hit = float((ls > 0).mean()) if len(ls) else np.nan

    turnover = leg_turnover(sub, "signal")

    summary.update({
        "ic_mean": float(ic_mean) if pd.notna(ic_mean) else np.nan,
        "ic_std": float(ic_std) if pd.notna(ic_std) else np.nan,
        "ic_tstat": float(ic_t) if pd.notna(ic_t) else np.nan,
        "ic_hit_rate": ic_hit,
        "ls_mean_bps": ls_mean_bps,
        "ls_std_bps": ls_std_bps,
        "ls_sharpe_ann": float(sharpe) if pd.notna(sharpe) else np.nan,
        "ls_hit_rate": ls_hit,
        "long_turnover": turnover["long_turnover"],
        "short_turnover": turnover["short_turnover"],
    })

    ic_frame = ic_ts.reset_index().rename(columns={"index": "date"})
    ic_frame["variant"] = variant
    ic_frame["horizon"] = horizon
    ic_frame["convention"] = convention

    dec["variant"] = variant
    dec["horizon"] = horizon
    dec["convention"] = convention

    return summary, ic_frame, dec


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = join_signals_returns()
    variants = sorted(df["variant"].unique())
    horizons = sorted(df["horizon"].unique(), key=lambda h: int(h.replace("d", "")))
    conventions = ("co", "oo")

    summaries, ic_parts, dec_parts = [], [], []
    for v in variants:
        for h in horizons:
            for c in conventions:
                summary, ic_ts, dec = run_one(df, v, h, c)
                summaries.append(summary)
                if not ic_ts.empty:
                    ic_parts.append(ic_ts)
                if not dec.empty:
                    dec_parts.append(dec)

    summary_df = pd.DataFrame(summaries)
    ic_df = pd.concat(ic_parts, ignore_index=True) if ic_parts else pd.DataFrame()
    dec_df = pd.concat(dec_parts, ignore_index=True) if dec_parts else pd.DataFrame()
    return summary_df, ic_df, dec_df


if __name__ == "__main__":
    summary, ic_ts, dec = run_all()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_parquet(SUMMARY_PATH, index=False)
    if not ic_ts.empty:
        ic_ts.to_parquet(IC_TS_PATH, index=False)
    if not dec.empty:
        dec.to_parquet(DECILE_PATH, index=False)
    log.info("Saved summary, IC time series, decile panels to data/")

    # Pretty print: rank by IC t-stat
    pretty_cols = [
        "variant", "horizon", "convention", "n_obs", "n_days",
        "ic_mean", "ic_tstat", "ic_hit_rate",
        "ls_mean_bps", "ls_sharpe_ann", "ls_hit_rate",
        "long_turnover", "short_turnover",
    ]
    show = summary[pretty_cols].copy()
    for c in ("ic_mean", "ic_tstat", "ic_hit_rate", "ls_sharpe_ann", "ls_hit_rate",
              "long_turnover", "short_turnover"):
        show[c] = show[c].round(3)
    show["ls_mean_bps"] = show["ls_mean_bps"].round(1)

    print("\nFull backtest grid (sorted by IC t-stat desc):")
    show_sorted = show.sort_values("ic_tstat", ascending=False, na_position="last")
    print(show_sorted.to_string(index=False))

    print("\nTop 5 by long-short Sharpe:")
    top_sharpe = show.sort_values("ls_sharpe_ann", ascending=False, na_position="last").head(5)
    print(top_sharpe.to_string(index=False))