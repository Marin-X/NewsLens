"""Shared CSS + plotly base for all NewsLens pages."""
from __future__ import annotations

CHARCOAL = "#0d0d0d"
CHARCOAL_DEEP = "#0a0a0a"
EMERALD = "#2ecc71"
EMERALD_2 = "#1abc9c"
NEG_RED = "#e74c3c"
NEUTRAL = "#9aa0a6"
GOLD = "#d4a957"

PLOT_BG = "rgba(0,0,0,0)"            # transparent — inherits container bg
PLOT_FONT_COLOR = "#e8e8e8"
PLOT_AXIS_COLOR = "#9aa0a6"
PLOT_GRID = "rgba(255,255,255,0.05)"
PLOT_ZERO = "rgba(255,255,255,0.18)"

PAGE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --charcoal-900: #0a0a0a;
    --charcoal-800: #0d0d0d;
    --charcoal-700: #141414;
    --emerald-500: #2ecc71;
    --emerald-300: #1abc9c;
    --text-primary: #e8e8e8;
    --text-secondary: rgba(232, 232, 232, 0.65);
    --text-muted: rgba(232, 232, 232, 0.40);
    --glass-bg: rgba(22, 22, 22, 0.7);
    --glass-border: rgba(46, 204, 113, 0.22);
    --glass-border-hover: rgba(46, 204, 113, 0.40);
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
.stMarkdown, .stMarkdown p, .stMarkdown li,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: var(--text-primary) !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--text-secondary) !important;
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
section[data-testid="stSidebar"] {
    background-color: var(--charcoal-800) !important;
    border-right: 1px solid rgba(46, 204, 113, 0.15) !important;
}
section[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
section[data-testid="stSidebar"] a { color: var(--emerald-300) !important; }

div[data-testid="stMetric"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.4rem !important;
    transition: all 0.35s ease;
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
    gap: 4px !important;
    background: var(--charcoal-700) !important;
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
    background: var(--charcoal-800);
}
[data-testid="stDataFrame"] {
    border: 1px solid var(--glass-border) !important;
    border-radius: 10px !important;
}
[data-testid="stDataFrame"] * { color: var(--text-primary) !important; }

div[data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea {
    background: var(--charcoal-700) !important;
    color: var(--text-primary) !important;
    border-color: var(--glass-border) !important;
}
div[data-baseweb="popover"] { background: var(--charcoal-700) !important; }
div[data-baseweb="popover"] * { color: var(--text-primary) !important; }

hr {
    border: none !important; height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(46, 204, 113, 0.30), transparent) !important;
    margin: 2rem 0 !important;
}

@media (max-width: 768px) {
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    h1 { font-size: 1.7rem !important; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.05rem !important; }
    div[data-testid="stMetric"] { padding: 0.85rem 1rem !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
    }
    div[data-testid="stMetric"] label { font-size: 0.65rem !important; }
    [data-testid="stPlotlyChart"] { border-radius: 8px; }
}
</style>
"""


def chart_height(desktop: int, mobile: int | None = None) -> int:
    """Pick a plot height. We can't detect mobile from Python, so we err on the smaller side
    by capping desktop heights and letting CSS handle width responsiveness via Plotly's
    responsive=True. Returns the desktop height; the chart still scales horizontally on mobile."""
    return desktop


def plotly_layout(height: int = 380, **overrides) -> dict:
    """Common Plotly layout: transparent background, theme-safe text colors."""
    base = dict(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=PLOT_FONT_COLOR, family="DM Sans"),
        xaxis=dict(
            showgrid=False,
            linecolor="rgba(255,255,255,0.1)",
            tickfont=dict(color=PLOT_AXIS_COLOR),
        ),
        yaxis=dict(
            gridcolor=PLOT_GRID,
            zerolinecolor=PLOT_ZERO,
            tickfont=dict(color=PLOT_AXIS_COLOR),
        ),
        legend=dict(
            orientation="h", y=1.08, x=0.5, xanchor="center",
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOT_FONT_COLOR),
        ),
        hoverlabel=dict(
            bgcolor="rgba(14,14,14,0.95)",
            bordercolor="rgba(46, 204, 113, 0.3)",
            font=dict(color="#e8e8e8", family="JetBrains Mono"),
        ),
    )
    base.update(overrides)
    return base