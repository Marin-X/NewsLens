"""Page 1 — Overview."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "pages"))

from _shared import (  # noqa: E402
    PAGE_CSS, EMERALD, EMERALD_2, NEG_RED, NEUTRAL, plotly_layout,
)

st.set_page_config(
    page_title="NewsLens · Overview",
    page_icon="https://marinxhemollari.com/frog-favicon.svg",
    layout="wide",
)
st.markdown(PAGE_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_overview_data() -> dict:
    """Aggregate stats and daily sentiment time series from parquet."""
    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=95)

    articles = pd.read_parquet(ROOT / "data" / "articles.parquet")
    articles["published"] = pd.to_datetime(articles["published"], utc=True)
    articles = articles[articles["published"] > cutoff].copy()

    universe = pd.read_parquet(ROOT / "data" / "universe.parquet")[["ticker", "sector"]]

    n_articles = len(articles)
    n_scored = articles["label"].notna().sum()
    n_tickers = articles["ticker"].nunique()
    date_min = articles["published"].min()
    date_max = articles["published"].max()

    articles["day"] = articles["published"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    daily = articles.groupby(["day", "label"]).size().reset_index(name="n")

    sources = (
        articles[articles["source"].fillna("") != ""]
        .groupby("source").size().reset_index(name="n")
        .sort_values("n", ascending=False).head(10)
    )

    sector_dist = articles.merge(universe, on="ticker", how="left")
    sector_dist["sector"] = sector_dist["sector"].fillna("Unknown")
    sector_agg = sector_dist.groupby(["sector", "label"]).size().reset_index(name="n")

    return {
        "n_articles": int(n_articles),
        "n_scored": int(n_scored),
        "n_tickers": int(n_tickers),
        "date_min": date_min,
        "date_max": date_max,
        "daily": daily,
        "sources": sources,
        "sector_agg": sector_agg,
    }


st.markdown("# Overview")
st.markdown(
    "<p style='color:#9aa0a6; font-size:1rem; margin-top:-0.5rem;'>"
    "Aggregate view of the ingestion pipeline and sentiment distribution."
    "</p>", unsafe_allow_html=True,
)
st.markdown("---")

data = load_overview_data()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Articles ingested", f"{data['n_articles']:,}")
c2.metric("Sentiment scored", f"{data['n_scored']:,}")
c3.metric("Tickers covered", f"{data['n_tickers']}")
span_days = (pd.to_datetime(data["date_max"]) - pd.to_datetime(data["date_min"])).days
c4.metric("Window (days)", f"{span_days}")

st.caption(
    f"Window: {pd.to_datetime(data['date_min']).date()}  →  "
    f"{pd.to_datetime(data['date_max']).date()}"
)
st.markdown(" ")

st.markdown("### Daily article volume by sentiment label")
daily = data["daily"].copy()
pivot = daily.pivot_table(index="day", columns="label", values="n", fill_value=0)
for col in ("positive", "neutral", "negative"):
    if col not in pivot.columns:
        pivot[col] = 0
pivot = pivot[["positive", "neutral", "negative"]]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=pivot.index, y=pivot["positive"], name="Positive", mode="lines",
    stackgroup="one", line=dict(width=0.5, color=EMERALD),
    fillcolor="rgba(46, 204, 113, 0.55)",
))
fig.add_trace(go.Scatter(
    x=pivot.index, y=pivot["neutral"], name="Neutral", mode="lines",
    stackgroup="one", line=dict(width=0.5, color=NEUTRAL),
    fillcolor="rgba(154, 160, 166, 0.45)",
))
fig.add_trace(go.Scatter(
    x=pivot.index, y=pivot["negative"], name="Negative", mode="lines",
    stackgroup="one", line=dict(width=0.5, color=NEG_RED),
    fillcolor="rgba(231, 76, 60, 0.55)",
))
fig.update_layout(**plotly_layout(height=380, hovermode="x unified"))
fig.update_yaxes(title=dict(text="Articles", font=dict(color="#9aa0a6", size=12)))
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns([3, 2])

with left:
    st.markdown("### Sentiment by GICS sector")
    sec = data["sector_agg"].copy()
    sec_pivot = sec.pivot_table(index="sector", columns="label", values="n", fill_value=0)
    for col in ("positive", "neutral", "negative"):
        if col not in sec_pivot.columns:
            sec_pivot[col] = 0
    sec_pivot["total"] = sec_pivot.sum(axis=1)
    sec_pivot = sec_pivot.sort_values("total")

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(y=sec_pivot.index, x=sec_pivot["positive"],
                          name="Positive", orientation="h", marker_color=EMERALD))
    fig2.add_trace(go.Bar(y=sec_pivot.index, x=sec_pivot["neutral"],
                          name="Neutral", orientation="h", marker_color=NEUTRAL))
    fig2.add_trace(go.Bar(y=sec_pivot.index, x=sec_pivot["negative"],
                          name="Negative", orientation="h", marker_color=NEG_RED))
    fig2.update_layout(**plotly_layout(height=440, barmode="stack"))
    fig2.update_xaxes(gridcolor="rgba(255,255,255,0.05)", showgrid=True)
    fig2.update_yaxes(showgrid=False, automargin=True)
    st.plotly_chart(fig2, use_container_width=True)

with right:
    st.markdown("### Top 10 news sources")
    src = data["sources"]
    fig3 = go.Figure(go.Bar(
        y=src["source"][::-1], x=src["n"][::-1],
        orientation="h", marker_color=EMERALD_2,
    ))
    fig3.update_layout(**plotly_layout(height=440))
    fig3.update_xaxes(gridcolor="rgba(255,255,255,0.05)", showgrid=True)
    fig3.update_yaxes(showgrid=False, automargin=True)
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")
st.caption(
    "Source: Finnhub `company-news` endpoint. Sentiment scored locally with "
    "ProsusAI/finbert. Cached daily."
)