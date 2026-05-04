"""Page 3 — Signal Construction."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "pages"))

from _shared import (  # noqa: E402
    PAGE_CSS, EMERALD, EMERALD_2, NEG_RED, plotly_layout,
)

st.set_page_config(
    page_title="NewsLens · Signals",
    page_icon="https://marinxhemollari.com/frog-favicon.svg",
    layout="wide",
)
st.markdown(PAGE_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=600)
def load_signals() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "signals.parquet")
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df


VARIANT_DESCRIPTIONS = {
    "mean": "Equal-weight average of article compounds per ticker-day. Baseline.",
    "decay": "Intraday exponential decay (6h half-life) — newer articles within the day count more.",
    "volume": "Sentiment × log(1 + n_articles). Captures conviction via news volume.",
    "sector_relative": "Daily mean compound z-scored within GICS sector — removes sector-wide drift.",
    "composite": "Equal-weight blend of decay + volume + sector_relative (each z-scored first).",
}

st.markdown("# Signal Construction")
st.markdown(
    "<p style='color:#9aa0a6; font-size:1rem; margin-top:-0.5rem;'>"
    "Five variant constructions of the FinBERT-derived signal across daily, weekly, and monthly horizons."
    "</p>", unsafe_allow_html=True,
)
st.markdown("---")

signals = load_signals()
variants = sorted(signals["variant"].unique())
horizons = sorted(signals["horizon"].unique(), key=lambda h: int(h.replace("d", "")))

c1, c2 = st.columns([1, 1])
with c1:
    variant = st.selectbox(
        "Variant", variants,
        index=variants.index("composite") if "composite" in variants else 0,
    )
with c2:
    horizon = st.selectbox("Horizon", horizons, index=0)

st.caption(VARIANT_DESCRIPTIONS.get(variant, ""))
st.markdown(" ")

sub = signals[(signals["variant"] == variant) & (signals["horizon"] == horizon)].copy()
sub = sub.dropna(subset=["signal"])
if sub.empty:
    st.warning("No data for this variant × horizon combination.")
    st.stop()

latest_date = sub["date"].max()
latest = sub[sub["date"] == latest_date].copy()

st.markdown(f"### Latest snapshot — {latest_date:%Y-%m-%d}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Universe coverage", f"{len(latest)}")
k2.metric("Signal mean", f"{latest['signal'].mean():+.3f}")
k3.metric("Signal std", f"{latest['signal'].std():.3f}")
k4.metric("Median articles", f"{int(latest['n_articles'].median())}")

st.markdown(" ")

left, right = st.columns([3, 2])

with left:
    st.markdown("### Cross-sectional signal distribution (latest)")
    fig = go.Figure()
    fig.add_trace(
        go.Violin(
            y=latest["signal"], name=variant,
            box_visible=True, line_color=EMERALD_2,
            fillcolor="rgba(46, 204, 113, 0.15)",
            meanline_visible=True, points="outliers",
            marker=dict(color=EMERALD, opacity=0.6, size=4),
        )
    )
    fig.update_layout(**plotly_layout(height=420, showlegend=False))
    fig.update_yaxes(title=dict(text="Signal", font=dict(color="#9aa0a6", size=12)))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown("### Top 10 / Bottom 10")
    top = latest.nlargest(10, "signal")[["ticker", "signal", "n_articles"]]
    bot = latest.nsmallest(10, "signal")[["ticker", "signal", "n_articles"]]
    tabs = st.tabs(["Top 10 (long)", "Bottom 10 (short)"])
    with tabs[0]:
        df_show = top.copy()
        df_show.columns = ["Ticker", "Signal", "Articles"]
        df_show["Signal"] = df_show["Signal"].round(3)
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=380)
    with tabs[1]:
        df_show = bot.copy()
        df_show.columns = ["Ticker", "Signal", "Articles"]
        df_show["Signal"] = df_show["Signal"].round(3)
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=380)

st.markdown("---")
st.markdown("### Signal time series for a single ticker")
available_tickers = sorted(sub["ticker"].unique())
default_ticker = "AAPL" if "AAPL" in available_tickers else available_tickers[0]
ticker = st.selectbox("Ticker", available_tickers, index=available_tickers.index(default_ticker))
ts = sub[sub["ticker"] == ticker].sort_values("date")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=ts["date"], y=ts["signal"], mode="lines+markers",
    name=f"{variant} {horizon}",
    line=dict(color=EMERALD_2, width=1.6),
    marker=dict(size=5, color=[EMERALD if v >= 0 else NEG_RED for v in ts["signal"]]),
    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Signal: %{y:+.3f}<extra></extra>",
))
fig2.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1))
fig2.update_layout(**plotly_layout(height=360, showlegend=False))
fig2.update_yaxes(title=dict(text="Signal (z)", font=dict(color="#9aa0a6", size=12)))
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.markdown("### Signal persistence by variant (autocorrelation at lags 1–10d)")
st.caption(
    "Higher autocorrelation = signal persists across days (low turnover). "
    "Lower autocorrelation = mean-reverting (high turnover, costs eat the strategy)."
)

@st.cache_data(ttl=600)
def autocorr_by_variant(df: pd.DataFrame, max_lag: int = 10) -> pd.DataFrame:
    out = []
    for v in df["variant"].unique():
        sub_v = df[(df["variant"] == v) & (df["horizon"] == "1d")].copy()
        sub_v = sub_v.sort_values(["ticker", "date"])
        for lag in range(1, max_lag + 1):
            grouped = sub_v.groupby("ticker")["signal"]
            corrs = grouped.apply(lambda s: s.autocorr(lag) if len(s) > lag + 1 else np.nan)
            out.append({"variant": v, "lag": lag, "autocorr": corrs.dropna().mean()})
    return pd.DataFrame(out)

ac = autocorr_by_variant(signals)
fig3 = go.Figure()
palette = {
    "mean": "#9aa0a6", "decay": EMERALD_2,
    "volume": "#d4a957", "sector_relative": "#a78bfa",
    "composite": EMERALD,
}
for v in variants:
    sub_ac = ac[ac["variant"] == v]
    fig3.add_trace(go.Scatter(
        x=sub_ac["lag"], y=sub_ac["autocorr"],
        mode="lines+markers", name=v,
        line=dict(color=palette.get(v, "#888"), width=2),
        marker=dict(size=7),
    ))
fig3.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1))
fig3.update_layout(**plotly_layout(height=360))
fig3.update_xaxes(
    title=dict(text="Lag (days)", font=dict(color="#9aa0a6", size=12)),
    dtick=1,
)
fig3.update_yaxes(title=dict(text="Autocorrelation", font=dict(color="#9aa0a6", size=12)))
st.plotly_chart(fig3, use_container_width=True)

st.caption(
    "Computed on the 1d horizon, averaged across tickers. Volume-weighted "
    "signals typically decay slower because volume itself is sticky."
)