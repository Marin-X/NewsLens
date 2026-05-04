"""NewsLens — main entry point."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

st.set_page_config(
    page_title="NewsLens",
    page_icon="https://marinxhemollari.com/frog-favicon.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --charcoal-900: #0a0a0a;
        --charcoal-800: #0d0d0d;
        --charcoal-700: #141414;
        --charcoal-600: #1a1a1a;
        --emerald-500: #2ecc71;
        --emerald-400: #27ae60;
        --emerald-300: #1abc9c;
        --text-primary: #e8e8e8;
        --text-secondary: rgba(232, 232, 232, 0.65);
        --text-muted: rgba(232, 232, 232, 0.40);
        --glass-bg: rgba(22, 22, 22, 0.7);
        --glass-border: rgba(46, 204, 113, 0.22);
        --glass-border-hover: rgba(46, 204, 113, 0.40);
    }

    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(24px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes shimmerSweep {
        0%   { background-position: -150% center; }
        100% { background-position: 250% center; }
    }
    @keyframes borderBreathe {
        0%, 100% { border-color: rgba(46, 204, 113, 0.22); }
        50%      { border-color: rgba(46, 204, 113, 0.42); }
    }
    @keyframes logoFloat {
        0%, 100% { transform: translateY(0px); }
        50%      { transform: translateY(-6px); }
    }

    html, body, [data-testid="stAppViewContainer"], .main, .stApp {
        background-color: var(--charcoal-900) !important;
        color: var(--text-primary) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    .main .block-container {
        padding-top: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1400px;
    }

    /* Make sure markdown/paragraph text is visible in any mode */
    .stMarkdown, .stMarkdown p, .stMarkdown li,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: var(--text-primary) !important;
    }
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--text-secondary) !important;
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--charcoal-800); }
    ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--emerald-400); }

    /* === Header banner === */
    .nl-header {
        background: linear-gradient(135deg,
            var(--charcoal-800) 0%, rgba(46, 204, 113, 0.22) 25%,
            var(--charcoal-700) 50%, rgba(26, 188, 156, 0.22) 75%,
            var(--charcoal-800) 100%);
        background-size: 400% 400%;
        animation: gradientShift 10s ease infinite,
                   fadeInUp 0.8s ease-out,
                   borderBreathe 6s ease-in-out infinite;
        border: 1px solid rgba(46, 204, 113, 0.28);
        border-radius: 16px;
        padding: 2.5rem 3rem;
        margin-bottom: 2rem;
        position: relative; overflow: hidden;
        box-shadow: 0 0 40px rgba(46, 204, 113, 0.15),
                    inset 0 1px 0 rgba(46, 204, 113, 0.10);
    }
    .nl-header::before {
        content: ''; position: absolute; inset: 0;
        background: radial-gradient(ellipse at 20% 50%, rgba(46, 204, 113, 0.14) 0%, transparent 65%);
        pointer-events: none; z-index: 0;
    }
    .nl-header::after {
        content: ''; position: absolute; inset: 0;
        background: linear-gradient(105deg, transparent 40%,
                                            rgba(46, 204, 113, 0.14) 50%,
                                            transparent 60%);
        background-size: 200% 100%;
        animation: shimmerSweep 7s ease-in-out infinite;
        pointer-events: none; z-index: 0;
    }
    .nl-header-content {
        display: flex; align-items: center; gap: 2.5rem;
        position: relative; z-index: 2; min-width: 0;
    }
    .nl-logo {
        width: 64px; height: 64px;
        animation: logoFloat 4s ease-in-out infinite;
        filter: drop-shadow(0 0 14px rgba(46, 204, 113, 0.55));
        flex-shrink: 0;
    }
    .nl-title-wrap { display: flex; flex-direction: column; min-width: 0; flex: 1; }
    .nl-title {
        font-family: 'Cormorant Garamond', serif;
        font-size: 3rem; font-weight: 700;
        letter-spacing: -0.02em; line-height: 1.1; margin: 0;
        display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.25rem;
    }
    .nl-title-plain { color: var(--text-primary); }
    .nl-title-accent {
        background: linear-gradient(135deg, #2ecc71 0%, #1abc9c 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .nl-subtitle {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.95rem; color: var(--text-secondary);
        margin-top: 0.35rem; font-weight: 300; letter-spacing: 0.02em;
    }
    .nl-version {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem; color: var(--emerald-500);
        background: rgba(46, 204, 113, 0.12);
        border: 1px solid rgba(46, 204, 113, 0.25);
        padding: 0.2rem 0.6rem; border-radius: 4px;
        letter-spacing: 0.05em;
        align-self: center; flex-shrink: 0; margin-left: 0.75rem;
    }

    h1 {
        font-family: 'Cormorant Garamond', serif !important;
        font-weight: 500 !important;
        font-size: 2.4rem !important;
        color: var(--text-primary) !important;
    }
    h2 {
        font-family: 'Cormorant Garamond', serif !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
    }
    h3 {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        color: var(--emerald-300) !important;
    }
    code, pre, .stCode { font-family: 'JetBrains Mono', monospace !important; }

    section[data-testid="stSidebar"] {
        background-color: var(--charcoal-800) !important;
        border-right: 1px solid rgba(46, 204, 113, 0.15) !important;
    }
    section[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
    section[data-testid="stSidebar"] a { color: var(--emerald-300) !important; }

    div[data-testid="stMetric"] {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        padding: 1.2rem 1.4rem !important;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="stMetric"]:hover {
        border-color: var(--glass-border-hover) !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(46, 204, 113, 0.25);
    }
    div[data-testid="stMetric"] label {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.72rem !important;
        color: var(--text-muted) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.4rem !important; font-weight: 600 !important;
        color: var(--emerald-500) !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: var(--text-secondary) !important;
        font-size: 0.78rem !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important; background: var(--charcoal-700) !important;
        border-radius: 10px !important; padding: 4px !important;
        flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.82rem !important;
        border-radius: 8px !important; padding: 8px 16px !important;
        color: var(--text-secondary) !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(46, 204, 113, 0.18) !important;
        color: var(--emerald-500) !important;
    }

    [data-testid="stPlotlyChart"] {
        border: 1px solid var(--glass-border); border-radius: 12px;
        overflow: hidden;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
        background: var(--charcoal-800);
    }
    [data-testid="stPlotlyChart"]:hover {
        border-color: var(--glass-border-hover);
        box-shadow: 0 4px 32px rgba(46, 204, 113, 0.15);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--glass-border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stDataFrame"] * {
        color: var(--text-primary) !important;
    }

    /* Selectbox / inputs */
    div[data-baseweb="select"] > div,
    .stTextInput input, .stTextArea textarea {
        background: var(--charcoal-700) !important;
        color: var(--text-primary) !important;
        border-color: var(--glass-border) !important;
    }
    div[data-baseweb="popover"] {
        background: var(--charcoal-700) !important;
    }
    div[data-baseweb="popover"] * {
        color: var(--text-primary) !important;
    }

    hr {
        border: none !important; height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(46, 204, 113, 0.30), transparent) !important;
        margin: 2rem 0 !important;
    }

    .nl-footer {
        text-align: center; color: var(--text-muted);
        font-family: 'DM Sans', sans-serif; font-size: 0.78rem;
        padding: 2rem 0 1rem;
    }
    .nl-footer a { color: var(--emerald-500); text-decoration: none; }
    .nl-footer a:hover { color: var(--emerald-300); }
    .nl-footer-mono {
        font-family: 'JetBrains Mono', monospace; font-size: 0.68rem;
        color: var(--text-muted); opacity: 0.6; margin-top: 0.5rem;
    }

    /* === MOBILE === */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .nl-header {
            padding: 1.5rem 1.25rem;
            border-radius: 12px;
        }
        .nl-header-content {
            gap: 1rem;
            flex-wrap: wrap;
        }
        .nl-logo { width: 44px; height: 44px; }
        .nl-title { font-size: 1.9rem; }
        .nl-subtitle { font-size: 0.82rem; }
        .nl-version { font-size: 0.62rem; padding: 0.15rem 0.45rem; }
        h1 { font-size: 1.7rem !important; }
        h2 { font-size: 1.4rem !important; }
        h3 { font-size: 1.05rem !important; }
        div[data-testid="stMetric"] {
            padding: 0.85rem 1rem !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
        }
        div[data-testid="stMetric"] label {
            font-size: 0.65rem !important;
        }
        [data-testid="stPlotlyChart"] {
            border-radius: 8px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="nl-header">
        <div class="nl-header-content">
            <img src="https://marinxhemollari.com/frog-logo.svg"
                 alt="NewsLens" class="nl-logo"
                 onerror="this.style.display='none'">
            <div class="nl-title-wrap">
                <div class="nl-title">
                    <span class="nl-title-plain">News</span><span class="nl-title-accent">Lens</span>
                    <span class="nl-version">v1.0</span>
                </div>
                <div class="nl-subtitle">
                    FinBERT sentiment as an equity alpha factor across the S&P 500
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("## Project")
st.markdown(
    "An end-to-end research pipeline that turns financial news into a tradeable equity factor: "
    "S&P 500 universe construction, Finnhub news ingestion at scale, "
    "ProsusAI/FinBERT transformer inference for sentiment, multi-variant signal engineering, "
    "and a full long-short backtest with information coefficient, decile portfolios, and turnover."
)

st.markdown("## Headline finding")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Best signal", "volume × 21d")
with c2:
    st.metric("IC t-stat", "+2.98")
with c3:
    st.metric("LS Sharpe (ann.)", "+2.63")
with c4:
    st.metric("Hit rate", "83%")

st.caption(
    "Volume-weighted FinBERT sentiment predicts 21-day forward returns on the S&P 500 at "
    "statistically significant levels (n_days = 65). Shorter horizons (1d, 5d) exhibit reversal, "
    "consistent with academic findings on slow news drift."
)

st.markdown("---")

st.markdown("## Navigate")
st.markdown(
    """
    Use the sidebar to move between sections. Each page renders directly from cached parquet
    outputs of the pipeline.

    - **1 · Overview** — pipeline summary, ingestion volume, sentiment distribution
    - **2 · Sentiment Explorer** — per-ticker article feed and FinBERT scores
    - **3 · Signal Construction** — variants, distributions, top/bottom names, persistence
    - **4 · Backtest** — IC time series, decile portfolios, long-short equity curve
    """
)

st.markdown("---")

st.markdown(
    """
    <div class="nl-footer">
        Built by <a href="https://marinxhemollari.com" target="_blank">Marin Xhemollari</a> ·
        FinBERT (ProsusAI) · pandas · plotly · Streamlit
        <div class="nl-footer-mono">newslens v1.0 · S&P 500 · 90-day window · CPU inference</div>
    </div>
    """,
    unsafe_allow_html=True,
)