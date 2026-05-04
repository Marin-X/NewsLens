"""Page 2 — Sentiment Explorer."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "pages"))

from db import get_conn  # noqa: E402
from _shared import (  # noqa: E402
    PAGE_CSS, EMERALD, EMERALD_2, NEG_RED, GOLD, plotly_layout,
)

st.set_page_config(
    page_title="NewsLens · Sentiment Explorer",
    page_icon="https://marinxhemollari.com/frog-favicon.svg",
    layout="wide",
)
st.markdown(PAGE_CSS, unsafe_allow_html=True)


@st.cache_data(ttl=600)
def list_tickers() -> list[str]:
    cutoff = (pd.Timestamp.utcnow() - pd.Timedelta(days=95)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.ticker, COUNT(*) AS n
            FROM articles a JOIN sentiment s ON s.article_id = a.id
            WHERE a.published > ? GROUP BY a.ticker
            HAVING n > 0 ORDER BY n DESC
            """,
            (cutoff,),
        ).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=600)
def load_ticker_data(ticker: str) -> dict:
    cutoff = (pd.Timestamp.utcnow() - pd.Timedelta(days=95)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        articles = pd.read_sql_query(
            """
            SELECT a.published, a.headline, a.source, a.url,
                   s.label, s.compound, s.score_pos, s.score_neu, s.score_neg
            FROM articles a JOIN sentiment s ON s.article_id = a.id
            WHERE a.ticker = ? AND a.published > ?
            ORDER BY a.published DESC
            """,
            conn, params=(ticker, cutoff), parse_dates=["published"],
        )
    prices = pd.read_parquet(ROOT / "data" / "prices.parquet")
    prices = prices[prices["ticker"] == ticker].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[prices["date"] >= pd.Timestamp(cutoff)]
    return {"articles": articles, "prices": prices}


st.markdown("# Sentiment Explorer")
st.markdown(
    "<p style='color:#9aa0a6; font-size:1rem; margin-top:-0.5rem;'>"
    "Per-ticker article feed with FinBERT scores and price overlay."
    "</p>", unsafe_allow_html=True,
)
st.markdown("---")

tickers = list_tickers()
default_idx = tickers.index("AAPL") if "AAPL" in tickers else 0
ticker = st.selectbox("Ticker", tickers, index=default_idx)

data = load_ticker_data(ticker)
articles = data["articles"]
prices = data["prices"]

if articles.empty:
    st.warning(f"No scored articles for {ticker} in window.")
    st.stop()

label_counts = articles["label"].value_counts()
n_pos = int(label_counts.get("positive", 0))
n_neu = int(label_counts.get("neutral", 0))
n_neg = int(label_counts.get("negative", 0))
n_total = len(articles)
mean_compound = float(articles["compound"].mean())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Articles", f"{n_total:,}")
c2.metric("Positive", f"{n_pos}", f"{100 * n_pos / n_total:.1f}% of total", delta_color="off")
c3.metric("Neutral", f"{n_neu}", f"{100 * n_neu / n_total:.1f}% of total", delta_color="off")
c4.metric("Negative", f"{n_neg}", f"{100 * n_neg / n_total:.1f}% of total", delta_color="off")
c5.metric("Mean compound", f"{mean_compound:+.3f}")

st.caption(
    f"Window: {articles['published'].min():%Y-%m-%d} → "
    f"{articles['published'].max():%Y-%m-%d}"
)
st.markdown(" ")

st.markdown("### Daily mean sentiment vs. price")
daily = (
    articles.assign(day=articles["published"].dt.tz_convert("UTC").dt.normalize())
    .groupby("day").agg(compound=("compound", "mean"), n=("compound", "size"))
    .reset_index()
)
daily["day"] = daily["day"].dt.tz_localize(None)
daily["compound_smooth"] = daily["compound"].rolling(5, min_periods=1).mean()

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(
    go.Bar(
        x=daily["day"], y=daily["compound"],
        name="Daily mean", opacity=0.35,
        marker_color=[EMERALD if v >= 0 else NEG_RED for v in daily["compound"]],
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Compound: %{y:+.3f}<extra></extra>",
    ),
    secondary_y=False,
)
fig.add_trace(
    go.Scatter(
        x=daily["day"], y=daily["compound_smooth"],
        name="5d smoothed", mode="lines",
        line=dict(color=EMERALD_2, width=2),
        hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Smoothed: %{y:+.3f}<extra></extra>",
    ),
    secondary_y=False,
)
if not prices.empty:
    fig.add_trace(
        go.Scatter(
            x=prices["date"], y=prices["adj_close"],
            name="Adj close", mode="lines",
            line=dict(color=GOLD, width=1.6),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>$%{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
fig.update_layout(**plotly_layout(height=440, hovermode="x unified", bargap=0.05))
fig.update_yaxes(title_text="Compound", secondary_y=False,
                 title_font=dict(color="#9aa0a6", size=12))
fig.update_yaxes(title_text="Price ($)", secondary_y=True, showgrid=False,
                 title_font=dict(color="#9aa0a6", size=12))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Article feed")
table = articles.copy()
table["date"] = table["published"].dt.strftime("%Y-%m-%d %H:%M")
table["compound"] = table["compound"].round(3)
table = table[["date", "label", "compound", "headline", "source", "url"]]
table.columns = ["Date", "Label", "Compound", "Headline", "Source", "URL"]

st.dataframe(
    table, use_container_width=True, hide_index=True,
    column_config={
        "URL": st.column_config.LinkColumn("Link", display_text="open"),
        "Compound": st.column_config.NumberColumn(format="%+.3f"),
        "Label": st.column_config.TextColumn(width="small"),
        "Source": st.column_config.TextColumn(width="medium"),
    },
    height=480,
)
st.caption(f"Showing {len(table)} articles for {ticker}.")