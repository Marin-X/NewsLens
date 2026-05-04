"""Page 4 — Backtest."""
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
    PAGE_CSS, EMERALD, EMERALD_2, NEG_RED, NEUTRAL, GOLD, plotly_layout,
)

st.set_page_config(
    page_title="NewsLens · Backtest",
    page_icon="https://marinxhemollari.com/frog-favicon.svg",
    layout="wide",
)
st.markdown(PAGE_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <style>
    .headline-card {
        background: linear-gradient(180deg, rgba(46,204,113,0.08), rgba(46,204,113,0.02));
        border: 1px solid rgba(46, 204, 113, 0.25);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 0.5rem 0 1.5rem 0;
    }
    .headline-label {
        color: #9aa0a6; text-transform: uppercase;
        letter-spacing: 1.2px; font-size: 0.75rem;
    }
    .headline-value {
        color: #2ecc71; font-family: 'JetBrains Mono', monospace;
        font-size: 1.4rem; font-weight: 500;
    }
    @media (max-width: 768px) {
        .headline-card { padding: 1rem 1rem; }
        .headline-value { font-size: 1.1rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=600)
def load_backtest() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_parquet(ROOT / "data" / "backtest_summary.parquet")
    ic = pd.read_parquet(ROOT / "data" / "backtest_ic_timeseries.parquet")
    dec = pd.read_parquet(ROOT / "data" / "backtest_decile_returns.parquet")
    ic["date"] = pd.to_datetime(ic["date"])
    dec["date"] = pd.to_datetime(dec["date"])
    return summary, ic, dec


st.markdown("# Backtest")
st.markdown(
    "<p style='color:#9aa0a6; font-size:1rem; margin-top:-0.5rem;'>"
    "Information coefficient, decile portfolios, and long-short evaluation across "
    "5 signal variants × 3 horizons × 2 execution conventions."
    "</p>", unsafe_allow_html=True,
)
st.markdown("---")

summary, ic_ts, decile_panel = load_backtest()

valid = summary.dropna(subset=["ic_tstat"]).copy()
best = valid.sort_values("ic_tstat", ascending=False).iloc[0]

st.markdown(
    f"""
    <div class="headline-card">
      <div class="headline-label">Headline finding</div>
      <div style="font-family: 'Cormorant Garamond', serif; font-size: 1.5rem;
                  color: #e8e8e8; margin-top: 0.3rem;">
        Best signal: <strong>{best['variant']}</strong> ·
        horizon <strong>{best['horizon']}</strong> ·
        convention <strong>{best['convention'].upper()}</strong>
      </div>
      <div style="margin-top: 0.75rem; color: #9aa0a6; font-size: 0.95rem;">
        IC mean <span class="headline-value">{best['ic_mean']:+.3f}</span>
        &nbsp;&nbsp;t-stat <span class="headline-value">{best['ic_tstat']:.2f}</span>
        &nbsp;&nbsp;LS Sharpe (ann) <span class="headline-value">{best['ls_sharpe_ann']:.2f}</span>
        &nbsp;&nbsp;hit rate <span class="headline-value">{best['ls_hit_rate']:.0%}</span>
      </div>
      <div style="margin-top: 0.6rem; color: #6b7280; font-size: 0.85rem;">
        n_obs = {int(best['n_obs']):,} &nbsp;·&nbsp;
        n_days = {int(best['n_days'])} &nbsp;·&nbsp;
        long turnover = {best['long_turnover']:.0%} &nbsp;·&nbsp;
        short turnover = {best['short_turnover']:.0%}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Full results grid (sorted by IC t-stat)")
show = summary.copy().sort_values("ic_tstat", ascending=False, na_position="last")
show = show[[
    "variant", "horizon", "convention", "n_obs", "n_days",
    "ic_mean", "ic_tstat", "ic_hit_rate",
    "ls_mean_bps", "ls_sharpe_ann", "ls_hit_rate",
    "long_turnover", "short_turnover",
]]
show.columns = [
    "Variant", "Horizon", "Conv.", "N obs", "N days",
    "IC mean", "IC t-stat", "IC hit",
    "LS bps", "LS Sharpe", "LS hit",
    "Long T/O", "Short T/O",
]
st.dataframe(
    show, use_container_width=True, hide_index=True, height=420,
    column_config={
        "IC mean": st.column_config.NumberColumn(format="%+.3f"),
        "IC t-stat": st.column_config.NumberColumn(format="%+.2f"),
        "IC hit": st.column_config.NumberColumn(format="%.2f"),
        "LS bps": st.column_config.NumberColumn(format="%+.1f"),
        "LS Sharpe": st.column_config.NumberColumn(format="%+.2f"),
        "LS hit": st.column_config.NumberColumn(format="%.2f"),
        "Long T/O": st.column_config.NumberColumn(format="%.2f"),
        "Short T/O": st.column_config.NumberColumn(format="%.2f"),
    },
)

st.markdown("---")
st.markdown("### Drill-down")

c1, c2, c3 = st.columns(3)
variants = sorted(summary["variant"].unique())
horizons = sorted(summary["horizon"].unique(), key=lambda h: int(h.replace("d", "")))
conventions = sorted(summary["convention"].unique())

with c1:
    variant = st.selectbox(
        "Variant", variants,
        index=variants.index(best["variant"]) if best["variant"] in variants else 0,
    )
with c2:
    horizon = st.selectbox(
        "Horizon", horizons,
        index=horizons.index(best["horizon"]) if best["horizon"] in horizons else 0,
    )
with c3:
    convention = st.selectbox(
        "Convention", conventions,
        index=conventions.index(best["convention"]) if best["convention"] in conventions else 0,
    )

row = summary[(summary["variant"] == variant) & (summary["horizon"] == horizon)
              & (summary["convention"] == convention)]
if row.empty or pd.isna(row.iloc[0]["ic_mean"]):
    st.warning("No backtest data for this combination.")
    st.stop()
row = row.iloc[0]

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("IC mean", f"{row['ic_mean']:+.3f}")
k2.metric("IC t-stat", f"{row['ic_tstat']:+.2f}")
k3.metric("LS mean (bps)", f"{row['ls_mean_bps']:+.1f}")
k4.metric("LS Sharpe (ann)", f"{row['ls_sharpe_ann']:+.2f}")
k5.metric("LS hit rate", f"{row['ls_hit_rate']:.0%}")

st.markdown(" ")

ic_sub = ic_ts[(ic_ts["variant"] == variant) & (ic_ts["horizon"] == horizon)
               & (ic_ts["convention"] == convention)].sort_values("date").copy()

st.markdown("### Information coefficient — daily time series")
ic_sub["ic_smooth"] = ic_sub["ic"].rolling(10, min_periods=3).mean()
fig = go.Figure()
fig.add_trace(go.Bar(
    x=ic_sub["date"], y=ic_sub["ic"], name="Daily IC",
    marker_color=[EMERALD if v >= 0 else NEG_RED for v in ic_sub["ic"]],
    opacity=0.55,
    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>IC: %{y:+.3f}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=ic_sub["date"], y=ic_sub["ic_smooth"],
    name="10d rolling mean", mode="lines",
    line=dict(color=GOLD, width=2),
    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>10d mean: %{y:+.3f}<extra></extra>",
))
fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1))
fig.update_layout(**plotly_layout(height=360, hovermode="x unified"))
fig.update_yaxes(title=dict(text="Spearman IC", font=dict(color="#9aa0a6", size=12)))
st.plotly_chart(fig, use_container_width=True)

dec_sub = decile_panel[(decile_panel["variant"] == variant)
                       & (decile_panel["horizon"] == horizon)
                       & (decile_panel["convention"] == convention)].copy()
if dec_sub.empty:
    st.warning("No decile data for this combination.")
    st.stop()

decile_means = dec_sub.groupby("decile")["ret"].mean().reset_index()
decile_means["bps"] = decile_means["ret"] * 1e4

pivot = dec_sub.pivot(index="date", columns="decile", values="ret").sort_index()
if 10 in pivot.columns and 1 in pivot.columns:
    ls_daily = (pivot[10] - pivot[1]).dropna()
    cumret = (1.0 + ls_daily).cumprod() - 1.0
else:
    ls_daily = pd.Series(dtype=float)
    cumret = pd.Series(dtype=float)

left, right = st.columns([1, 1])

with left:
    st.markdown("### Decile portfolios — mean forward return")
    colors = []
    n_dec = len(decile_means)
    for i, _ in decile_means.iterrows():
        frac = i / max(1, n_dec - 1)
        if frac < 0.5:
            colors.append(NEG_RED)
        elif frac > 0.7:
            colors.append(EMERALD)
        else:
            colors.append(NEUTRAL)
    fig2 = go.Figure(go.Bar(
        x=decile_means["decile"].astype(str), y=decile_means["bps"],
        marker_color=colors,
        hovertemplate="<b>D%{x}</b><br>Mean: %{y:+.1f} bps<extra></extra>",
    ))
    fig2.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1))
    fig2.update_layout(**plotly_layout(height=380, showlegend=False))
    fig2.update_xaxes(title=dict(text="Decile (1=lowest, 10=highest)",
                                 font=dict(color="#9aa0a6", size=12)))
    fig2.update_yaxes(title=dict(text="Mean return (bps)",
                                 font=dict(color="#9aa0a6", size=12)))
    st.plotly_chart(fig2, use_container_width=True)

with right:
    st.markdown("### Cumulative long-short return")
    if cumret.empty:
        st.info("Not enough decile coverage for LS curve.")
    else:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=cumret.index, y=cumret.values * 100,
            mode="lines", fill="tozeroy",
            line=dict(color=EMERALD_2, width=2),
            fillcolor="rgba(46, 204, 113, 0.12)",
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Cumulative: %{y:+.2f}%<extra></extra>",
        ))
        fig3.add_hline(y=0, line=dict(color="rgba(255,255,255,0.2)", width=1))
        fig3.update_layout(**plotly_layout(height=380, showlegend=False))
        fig3.update_yaxes(title=dict(text="Cumulative return (%)",
                                     font=dict(color="#9aa0a6", size=12)))
        st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")
st.caption(
    "IC = cross-sectional Spearman rank correlation between signal and forward return. "
    "Long-short = D10 (top decile by signal) minus D1 (bottom decile). "
    "Returns are pre-cost; long+short turnover would substantially "
    "erode the daily-rebalanced strategies."
)