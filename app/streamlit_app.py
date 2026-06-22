import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import re
import time
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="MarketPulse",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Pastel palette (light theme) ─────────────────────────────────────────────
STEPS = [
    ("01", "Query",    "#7c3aed", "rgba(124,58,237,0.12)"),
    ("02", "Embed",    "#2563eb", "rgba(37,99,235,0.12)"),
    ("03", "Retrieve", "#ea580c", "rgba(234,88,12,0.12)"),
    ("04", "Generate", "#059669", "rgba(5,150,105,0.12)"),
    ("05", "Answer",   "#db2777", "rgba(219,39,119,0.12)"),
]

C_LAV  = "#c4b5fd"
C_SKY  = "#93c5fd"
C_PEACH= "#fdba74"
C_MINT = "#6ee7b7"
C_ROSE = "#f9a8d4"


# ── CSS ───────────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(145deg, #f5f3ff 0%, #fdf4ff 40%, #eff6ff 100%);
    min-height: 100vh;
}
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #ede9fe !important;
}
#MainMenu, footer, header { visibility: hidden; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #f5f3ff; }
::-webkit-scrollbar-thumb { background: #c4b5fd; border-radius: 3px; }

/* Hero */
.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(2.4rem, 5vw, 4rem);
    font-weight: 700;
    background: linear-gradient(130deg, #7c3aed 0%, #2563eb 55%, #0891b2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-align: center;
    letter-spacing: -2px;
    line-height: 1.05;
    margin-bottom: 0.3rem;
}
.hero-sub {
    color: #6d28d9;
    text-align: center;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.26em;
    text-transform: uppercase;
    margin-bottom: 0.15rem;
}
.hero-tagline {
    color: #9ca3af;
    text-align: center;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    margin-bottom: 1.6rem;
}

/* Pipeline */
.pipe-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1.2rem 0 1.6rem 0;
    background: #ffffff;
    border-radius: 16px;
    border: 1px solid #ede9fe;
    box-shadow: 0 2px 16px rgba(124,58,237,0.06);
    margin-bottom: 1rem;
}
.pipe-node { display: flex; flex-direction: column; align-items: center; gap: 7px; }
.pipe-icon {
    width: 52px; height: 52px;
    border-radius: 50%;
    border: 1.5px solid #e5e7eb;
    background: #f9fafb;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', monospace;
    font-size: 0.74rem;
    font-weight: 700;
    color: #9ca3af;
    transition: all 0.4s cubic-bezier(0.4,0,0.2,1);
}
.pipe-icon.active {
    border-color: var(--c);
    color: var(--c);
    background: var(--bg);
    box-shadow: 0 0 16px color-mix(in srgb, var(--c) 30%, transparent),
                0 4px 12px color-mix(in srgb, var(--c) 15%, transparent);
}
.pipe-icon.done {
    border-color: #059669;
    color: #059669;
    background: rgba(5,150,105,0.08);
}
.pipe-label {
    font-size: 0.58rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
}
.pipe-label.active { color: #4b5563; }
.pipe-label.done   { color: #059669; }
.pipe-conn {
    width: 60px; height: 1.5px;
    background: #e5e7eb;
    margin-bottom: 22px;
    flex-shrink: 0;
    transition: all 0.4s ease;
}
.pipe-conn.done {
    background: linear-gradient(90deg, #a7f3d0, #059669);
}

/* Divider */
.thinline {
    height: 1px;
    background: linear-gradient(90deg, transparent, #c4b5fd55, #93c5fd55, #c4b5fd55, transparent);
    margin: 1.2rem 0;
    border: none;
}

/* Glass card (on light bg = white with soft shadow) */
.gcard {
    background: #ffffff;
    border: 1px solid #ede9fe;
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 2px 20px rgba(124,58,237,0.06);
    margin-bottom: 1rem;
    animation: riseup 0.45s cubic-bezier(0.4,0,0.2,1) forwards;
}
@keyframes riseup {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}

.ctitle {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin-bottom: 1rem;
}

/* Stat badges */
.statrow { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0.3rem 0 0.9rem 0; }
.statbadge {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    text-align: center;
    flex: 1;
    min-width: 76px;
}
.statval {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #7c3aed, #2563eb);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: block;
}
.statkey { font-size: 0.58rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.1em; }

/* Embed info */
.embed-info {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.72rem;
    color: #374151;
    line-height: 2.1;
}

/* News/match cards */
.newscard {
    background: #fffbf5;
    border: 1px solid #fed7aa;
    border-left: 3px solid #fdba74;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.55rem;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.newscard:hover { box-shadow: 0 2px 12px rgba(253,186,116,0.2); }
.ntitle { color: #1e1b4b; font-size: 0.82rem; font-weight: 500; margin-bottom: 0.25rem; line-height: 1.45; }
.nmeta  { color: #9ca3af; font-size: 0.64rem; margin-bottom: 0.4rem; }

/* Match score bar */
.match-bar-wrap { background: #f3f4f6; border-radius: 4px; height: 5px; margin-top: 4px; overflow: hidden; }
.match-bar-fill { height: 5px; border-radius: 4px; }

/* Rating badge */
.rbadge {
    border-radius: 9px;
    padding: 0.45rem 0.8rem;
    margin-bottom: 0.45rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
}

/* Answer */
.answer-body {
    color: #1e1b4b;
    font-size: 0.9rem;
    line-height: 1.85;
}
.answer-body h2 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #7c3aed;
    margin: 1.4rem 0 0.5rem 0;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #ede9fe;
}
.answer-body h2:first-child { margin-top: 0; }
.answer-body p { margin: 0 0 0.8rem 0; color: #374151; }
.answer-body ol, .answer-body ul { padding-left: 1.2rem; margin: 0 0 0.8rem 0; color: #374151; }
.answer-body li { margin-bottom: 0.35rem; }
.query-echo {
    background: #ede9fe;
    border-left: 3px solid #7c3aed;
    padding: 0.55rem 1rem;
    border-radius: 0 10px 10px 0;
    color: #4c1d95;
    font-size: 0.84rem;
    margin-bottom: 1.2rem;
    font-style: italic;
    font-weight: 500;
}

/* Sources box */
.sources-box {
    background: #f5f3ff;
    border: 1px solid #c4b5fd;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-top: 1.4rem;
}
.sources-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #7c3aed;
    margin-bottom: 0.6rem;
}
.source-item {
    font-size: 0.72rem;
    color: #4b5563;
    padding: 0.25rem 0;
    border-bottom: 1px solid #ede9fe;
    line-height: 1.5;
}
.source-item:last-child { border-bottom: none; }

/* Chat history bubbles */
.chat-user {
    background: #ede9fe;
    border: 1px solid #c4b5fd;
    border-radius: 14px 14px 4px 14px;
    padding: 0.65rem 1rem;
    margin: 0.35rem 0 0.35rem 20%;
    color: #4c1d95;
    font-size: 0.83rem;
    font-weight: 500;
}
.chat-assistant-preview {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 4px 14px 14px 14px;
    padding: 0.65rem 1rem;
    margin: 0.35rem 20% 0.35rem 0;
    color: #374151;
    font-size: 0.8rem;
    line-height: 1.55;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05);
}
.chat-label {
    font-size: 0.58rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 0.2rem;
}

/* Streamlit widget overrides */
.stTextInput > div > div > input {
    background: #ffffff !important;
    border: 1.5px solid #e5e7eb !important;
    color: #1e1b4b !important;
    border-radius: 12px !important;
    font-size: 0.91rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}
.stTextInput > div > div > input:focus {
    border-color: #a78bfa !important;
    box-shadow: 0 0 0 3px rgba(167,139,250,0.15) !important;
}
.stTextInput > div > div > input::placeholder { color: #9ca3af !important; }
.stSelectbox > div > div {
    background: #ffffff !important;
    border-radius: 12px !important;
    border: 1.5px solid #e5e7eb !important;
}
.stButton > button {
    background: linear-gradient(135deg, #7c3aed 0%, #2563eb 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.55rem 2rem !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    transition: all 0.25s !important;
    box-shadow: 0 2px 12px rgba(124,58,237,0.25) !important;
}
.stButton > button:hover {
    box-shadow: 0 4px 20px rgba(124,58,237,0.35) !important;
    transform: translateY(-1px) !important;
}
label { color: #374151 !important; font-size: 0.74rem !important; font-weight: 500 !important; }
div[data-testid="stStatusWidget"] { display: none; }
div[data-testid="stStatus"] > div:first-child {
    background: #f9fafb !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
    color: #374151 !important;
}

/* Sidebar */
.sidebar-stat {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.4rem 0; border-bottom: 1px solid #f3f4f6;
    font-size: 0.72rem;
}
.sidebar-stat-key { color: #9ca3af; }
.sidebar-stat-val { font-weight: 600; color: #4c1d95; font-family: 'Space Grotesk', sans-serif; }
</style>
    """, unsafe_allow_html=True)


# ── Pipeline HTML ─────────────────────────────────────────────────────────────
def pipeline_html(active: int) -> str:
    out = '<div class="pipe-wrap">'
    for i, (icon, label, color, bg) in enumerate(STEPS):
        if i > 0:
            cls = "pipe-conn done" if i <= active else "pipe-conn"
            out += f'<div class="{cls}"></div>'
        if i == active:
            attrs = f'class="pipe-icon active" style="--c:{color};--bg:{bg}"'
            lc    = "pipe-label active"
        elif i < active:
            attrs = 'class="pipe-icon done"'
            lc    = "pipe-label done"
        else:
            attrs = 'class="pipe-icon"'
            lc    = "pipe-label"
        out += f'<div class="pipe-node"><div {attrs}>{icon}</div><div class="{lc}">{label}</div></div>'
    out += '</div>'
    return out


# ── Charts ────────────────────────────────────────────────────────────────────
def chart_candlestick(prices, company_name: str):
    if not prices:
        return None
    rows   = list(reversed(prices))
    dates  = [str(r['trade_date'])    for r in rows]
    opens  = [float(r['open_price'])  for r in rows]
    highs  = [float(r['high_price'])  for r in rows]
    lows   = [float(r['low_price'])   for r in rows]
    closes = [float(r['close_price']) for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=dates, open=opens, high=highs, low=lows, close=closes,
        name=company_name,
        increasing=dict(line=dict(color='#059669', width=1.2),
                        fillcolor='rgba(5,150,105,0.55)'),
        decreasing=dict(line=dict(color='#db2777', width=1.2),
                        fillcolor='rgba(219,39,119,0.45)'),
        whiskerwidth=0.5,
    ))
    # 20-day SMA
    if len(closes) >= 20:
        sma = [sum(closes[max(0,i-19):i+1]) / min(i+1,20) for i in range(len(closes))]
        fig.add_trace(go.Scatter(
            x=dates, y=sma, mode='lines',
            line=dict(color='#7c3aed', width=1.5, dash='dot'),
            name='20-day SMA', opacity=0.7,
        ))
    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0.9)',
        xaxis=dict(
            color='#9ca3af', gridcolor='rgba(0,0,0,0.04)',
            tickfont=dict(size=8), showgrid=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            color='#9ca3af', gridcolor='rgba(0,0,0,0.05)',
            tickfont=dict(size=8), tickprefix='$',
        ),
        legend=dict(font=dict(size=9, color='#6b7280'), bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=0, r=0, t=32, b=0),
        height=310,
        title=dict(
            text=f'{company_name}  Daily OHLCV',
            font=dict(color='#374151', size=10, family='Space Grotesk'),
            x=0.5,
        ),
        font=dict(family='Inter'),
    )
    return fig


def chart_match_scores(news):
    if not news:
        return None
    titles = []
    scores = []
    for art in news:
        t = art['title'][:42] + ('...' if len(art['title']) > 42 else '')
        titles.append(t)
        dist = float(art.get('distance') or 1.0)
        scores.append(round(max(0.0, (1 - dist)) * 100, 1))

    colors = []
    for s in scores:
        if s >= 70:
            colors.append('#7c3aed')
        elif s >= 50:
            colors.append('#a78bfa')
        else:
            colors.append('#c4b5fd')

    fig = go.Figure(go.Bar(
        y=titles[::-1], x=scores[::-1], orientation='h',
        marker=dict(color=colors[::-1], line=dict(width=0)),
        text=[f'{s}%' for s in scores[::-1]],
        textposition='outside',
        textfont=dict(size=9, color='#6b7280'),
        hovertemplate='%{y}<br>Match score: %{x:.1f}%<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        xaxis=dict(
            range=[0, 115],
            color='#9ca3af', tickfont=dict(size=8), ticksuffix='%',
            showgrid=True, gridcolor='rgba(0,0,0,0.05)',
        ),
        yaxis=dict(color='#374151', tickfont=dict(size=8)),
        margin=dict(l=0, r=30, t=28, b=0),
        height=220,
        title=dict(text='Semantic Match Scores', font=dict(color='#374151', size=10, family='Space Grotesk'), x=0.5),
        font=dict(family='Inter'),
    )
    return fig


def chart_embedding_3d(embedding, n_bg=130):
    vec = np.array(embedding, dtype=float)
    d   = len(vec) // 3
    mag = max(float(np.linalg.norm(vec)), 1e-9)
    q   = [
        float(np.linalg.norm(vec[:d]))    / mag * 10,
        float(np.linalg.norm(vec[d:2*d])) / mag * 10,
        float(np.linalg.norm(vec[2*d:]))  / mag * 10,
    ]
    rng = np.random.default_rng(7)
    bx = rng.normal(0, 3.5, n_bg)
    by = rng.normal(0, 3.5, n_bg)
    bz = rng.normal(0, 3.5, n_bg)
    dist = np.sqrt((bx - q[0])**2 + (by - q[1])**2 + (bz - q[2])**2)

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=bx, y=by, z=bz, mode='markers',
        marker=dict(
            size=2.4,
            color=dist,
            colorscale=[[0, '#a78bfa'], [0.5, '#93c5fd'], [1, '#e0e7ff']],
            opacity=0.5, showscale=False,
        ),
        hovertemplate='Document vector<extra></extra>',
        showlegend=False,
    ))
    for r, alpha in [(1.5, 0.25), (2.7, 0.1)]:
        theta = np.linspace(0, 2 * np.pi, 48)
        fig.add_trace(go.Scatter3d(
            x=q[0] + r * np.cos(theta),
            y=q[1] + r * np.sin(theta),
            z=[q[2]] * 48,
            mode='lines',
            line=dict(color=f'rgba(124,58,237,{alpha})', width=1.2),
            showlegend=False, hoverinfo='skip',
        ))
    fig.add_trace(go.Scatter3d(
        x=[q[0]], y=[q[1]], z=[q[2]], mode='markers',
        marker=dict(size=13, color='#7c3aed', symbol='diamond',
                    line=dict(color='#ffffff', width=2)),
        name='Query vector',
        hovertemplate='Query embedding<br>768-dim projection<extra></extra>',
    ))
    scene = dict(
        xaxis=dict(showticklabels=False, backgroundcolor='rgba(245,243,255,0.4)',
                   gridcolor='rgba(0,0,0,0.05)', color='#9ca3af', title=''),
        yaxis=dict(showticklabels=False, backgroundcolor='rgba(245,243,255,0.4)',
                   gridcolor='rgba(0,0,0,0.05)', title=''),
        zaxis=dict(showticklabels=True,  backgroundcolor='rgba(245,243,255,0.4)',
                   gridcolor='rgba(0,0,0,0.06)', color='#6b7280', title=''),
        bgcolor='rgba(249,250,251,0.6)',
    )
    fig.update_layout(
        scene=scene,
        paper_bgcolor='rgba(255,255,255,0)',
        margin=dict(l=0, r=0, t=36, b=0),
        height=310,
        title=dict(text='Query Vector  768-dim Embedding Space', font=dict(color='#374151', size=10), x=0.5),
        legend=dict(font=dict(color='#6b7280', size=9), bgcolor='rgba(255,255,255,0.6)'),
        showlegend=True,
        font=dict(family='Inter'),
    )
    return fig


def chart_macro_bars(macro):
    if not macro:
        return None
    names  = [m['indicator_name'][:20] + ('...' if len(m['indicator_name']) > 20 else '') for m in macro]
    values = [float(m['value']) for m in macro]
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation='h',
        marker=dict(
            color=values,
            colorscale=[[0, '#ddd6fe'], [0.45, '#a78bfa'], [1, '#2563eb']],
            showscale=False, line=dict(width=0),
        ),
        hovertemplate='%{y}<br>%{x:.4f}<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(255,255,255,0)',
        xaxis=dict(color='#9ca3af', gridcolor='rgba(0,0,0,0.05)', tickfont=dict(size=8)),
        yaxis=dict(color='#374151', tickfont=dict(size=8)),
        margin=dict(l=0, r=0, t=28, b=0), height=260,
        title=dict(text='Macro Indicators', font=dict(color='#374151', size=10, family='Space Grotesk'), x=0.5),
        font=dict(family='Inter', size=9),
    )
    return fig


# ── Answer parser ─────────────────────────────────────────────────────────────
def parse_answer(text: str):
    patterns = [
        r'##\s*Sources?\s*\n',
        r'\*\*Sources?\*\*[\s:]*\n',
        r'Sources?:\s*\n',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return text[:m.start()].strip(), text[m.end():].strip()
    return text.strip(), None


def _match_pct(art) -> float:
    dist = float(art.get('distance') or 1.0)
    return round(max(0.0, (1 - dist)) * 100, 1)


def _match_color(pct: float) -> str:
    if pct >= 70:
        return '#7c3aed'
    if pct >= 50:
        return '#a78bfa'
    return '#c4b5fd'


# ── DB helpers ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_ticker_list():
    try:
        from app.db import get_db_connection
        from psycopg2.extras import RealDictCursor
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT ticker, name FROM companies ORDER BY ticker;")
            rows = cur.fetchall()
        conn.close()
        return [(r['ticker'], r['name']) for r in rows]
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def load_db_stats():
    try:
        from app.db import get_db_connection
        conn = get_db_connection()
        stats = {}
        with conn.cursor() as cur:
            for t in ['companies', 'stock_prices', 'news_articles',
                      'economic_indicators', 'analyst_ratings']:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                stats[t] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM news_articles WHERE embedding IS NOT NULL")
            stats['embedded'] = cur.fetchone()[0]
        conn.close()
        return stats, None
    except Exception as e:
        return {}, str(e)


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:700;
                    color:#4c1d95;letter-spacing:-0.5px;margin-bottom:0.2rem">
            MarketPulse
        </div>
        <div style="font-size:0.6rem;color:#9ca3af;text-transform:uppercase;
                    letter-spacing:0.2em;margin-bottom:1.4rem">
            RAG Intelligence
        </div>
        """, unsafe_allow_html=True)

        tickers = load_ticker_list()
        ticker_opts = ["No filter"] + [f"{t}  {n}" for t, n in tickers]
        raw = st.selectbox("Focus ticker", ticker_opts, key="tk")
        ticker = raw.split("  ")[0].strip() if raw != "No filter" else None

        st.markdown('<div style="margin:0.8rem 0 0.4rem 0">', unsafe_allow_html=True)
        if st.button("New Conversation", key="new_chat"):
            st.session_state.chat_history = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<hr class="thinline" style="margin:1rem 0">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.18em;color:#9ca3af;margin-bottom:0.6rem">Live Database</div>', unsafe_allow_html=True)

        stats, err = load_db_stats()
        if not err:
            items = [
                ("Companies",   stats.get('companies', 0)),
                ("Price rows",  stats.get('stock_prices', 0)),
                ("Articles",    stats.get('news_articles', 0)),
                ("Embedded",    stats.get('embedded', 0)),
                ("Macro rows",  stats.get('economic_indicators', 0)),
                ("Ratings",     stats.get('analyst_ratings', 0)),
            ]
            for label, val in items:
                st.markdown(f"""
                <div class="sidebar-stat">
                    <span class="sidebar-stat-key">{label}</span>
                    <span class="sidebar-stat-val">{val:,}</span>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<hr class="thinline" style="margin:1rem 0">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.18em;color:#9ca3af;margin-bottom:0.5rem">Pipeline</div>', unsafe_allow_html=True)

        pipe_info = [
            (C_LAV,   "01 Query",    "Natural language input"),
            (C_SKY,   "02 Embed",    "MPNet 768-dim vector"),
            (C_PEACH, "03 Retrieve", "HNSW cosine search"),
            (C_MINT,  "04 Generate", "Gemini 2.5 Flash"),
            (C_ROSE,  "05 Answer",   "Structured response"),
        ]
        for color, step, desc in pipe_info:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:0.55rem;padding:0.32rem 0;
                        border-bottom:1px solid #f3f4f6">
                <div style="width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0"></div>
                <div>
                    <div style="font-size:0.64rem;font-weight:600;color:#374151">{step}</div>
                    <div style="font-size:0.58rem;color:#9ca3af">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        return ticker


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    inject_css()

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    ticker = render_sidebar()

    # Hero
    st.markdown("""
    <div style="padding:2rem 0 0.4rem 0">
        <div class="hero-title">MarketPulse</div>
        <div class="hero-sub">RAG Intelligence Platform</div>
        <div class="hero-tagline">Z2004 DBMS  ·  IIT Madras Zanzibar  ·  Track A  ·  2026</div>
    </div>
    """, unsafe_allow_html=True)

    pipe_slot = st.empty()
    pipe_slot.markdown(pipeline_html(-1), unsafe_allow_html=True)

    # Chat history
    if st.session_state.chat_history:
        st.markdown('<hr class="thinline">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.58rem;font-weight:700;text-transform:uppercase;letter-spacing:0.18em;color:#9ca3af;margin-bottom:0.6rem">Conversation History</div>', unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            if msg['role'] == 'user':
                ticker_tag = f' &nbsp;<span style="font-size:0.6rem;background:#ede9fe;color:#7c3aed;border-radius:6px;padding:1px 6px">{msg.get("ticker","")}</span>' if msg.get('ticker') else ''
                st.markdown(f"""
                <div style="text-align:right">
                    <div class="chat-label" style="color:#7c3aed;text-align:right">You{ticker_tag}</div>
                    <div class="chat-user">{msg['content']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                preview = msg['content'][:240].strip()
                if len(msg['content']) > 240:
                    preview += '...'
                st.markdown(f"""
                <div>
                    <div class="chat-label" style="color:#059669">MarketPulse</div>
                    <div class="chat-assistant-preview">{preview}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('<hr class="thinline">', unsafe_allow_html=True)

    # Query input
    st.markdown('<div class="gcard" style="border-color:#ede9fe">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#7c3aed">Ask the market anything</div>', unsafe_allow_html=True)

    example_qs = [
        '"Why did NVDA rally this week?"',
        '"What is the Fed rate outlook for Tech stocks?"',
        '"How is AAPL performing compared to analyst expectations?"',
        '"What macro factors are affecting energy stocks?"',
    ]
    st.markdown(f'<div style="font-size:0.68rem;color:#9ca3af;margin-bottom:0.7rem">Try: {example_qs[len(st.session_state.chat_history) % len(example_qs)]}</div>', unsafe_allow_html=True)

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "Question",
            placeholder="e.g. Why did NVDA rally? What is the Fed rate outlook?",
            key="q",
            label_visibility="collapsed",
        )
    with col_btn:
        go_btn = st.button("Analyze", key="go", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if not go_btn:
        if not st.session_state.chat_history:
            _render_idle()
        return

    if not query.strip():
        st.warning("Please enter a question above.")
        return

    _execute_pipeline(query.strip(), ticker, pipe_slot)


# ── Pipeline execution ────────────────────────────────────────────────────────
def _execute_pipeline(query: str, ticker, pipe_slot):

    # Stage 0 - Query
    pipe_slot.markdown(pipeline_html(0), unsafe_allow_html=True)
    st.session_state.chat_history.append({'role': 'user', 'content': query, 'ticker': ticker})
    time.sleep(0.35)

    # Stage 1 - Embedding
    pipe_slot.markdown(pipeline_html(1), unsafe_allow_html=True)

    st.markdown('<div class="gcard" style="border-color:#dbeafe">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#2563eb">Step 02  Query Embedding  all-mpnet-base-v2</div>', unsafe_allow_html=True)

    col_info, col_chart = st.columns([1, 2])
    with col_info:
        st.markdown("""
        <div class="statrow">
            <div class="statbadge">
                <span class="statval">768</span>
                <span class="statkey">Dimensions</span>
            </div>
            <div class="statbadge">
                <span class="statval">512</span>
                <span class="statkey">Token limit</span>
            </div>
        </div>
        <div class="embed-info">
            Architecture &nbsp;<span style="color:#2563eb;font-weight:600">MPNet</span><br>
            Pooling &nbsp;<span style="color:#7c3aed;font-weight:600">Mean CLS tokens</span><br>
            Similarity &nbsp;<span style="color:#ea580c;font-weight:600">Cosine distance</span><br>
            Index &nbsp;<span style="color:#059669;font-weight:600">HNSW via pgvector</span>
        </div>
        """, unsafe_allow_html=True)

    with col_chart:
        with st.status("Encoding query into 768-dim vector space...", expanded=False) as s:
            from app.rag import generate_embedding
            embedding = generate_embedding(query)
            s.update(label=f"Complete  {len(embedding)}-dim vector generated", state="complete")
        fig_e = chart_embedding_3d(embedding)
        if fig_e:
            st.plotly_chart(fig_e, use_container_width=True, config={"displayModeBar": False})

    st.markdown('</div>', unsafe_allow_html=True)
    time.sleep(0.3)

    # Stage 2 - Retrieval
    pipe_slot.markdown(pipeline_html(2), unsafe_allow_html=True)

    st.markdown('<div class="gcard" style="border-color:#ffedd5">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#ea580c">Step 03  Context Retrieval  PostgreSQL + pgvector HNSW</div>', unsafe_allow_html=True)

    with st.status("Running HNSW similarity search + B-Tree lookups...", expanded=False) as s:
        from app.db import (find_company, get_similar_news, get_recent_prices,
                            get_analyst_ratings, get_recent_economic_indicators)
        company_id, company_info = None, None
        if ticker:
            company_info = find_company(ticker)
            if company_info:
                company_id = company_info["company_id"]
        news    = get_similar_news(embedding, limit=5, company_id=company_id)
        macro   = get_recent_economic_indicators()
        prices  = list(get_recent_prices(company_id, limit=90)) if company_id else []
        ratings = list(get_analyst_ratings(company_id, limit=5)) if company_id else []
        s.update(label=f"Retrieved: {len(news)} articles  {len(prices)} price rows  {len(macro)} macro indicators", state="complete")

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        if prices:
            cname = company_info["name"] if company_info else (ticker or "")
            fig_p = chart_candlestick(prices, cname)
            if fig_p:
                st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
            fig_ms = chart_match_scores(news)
            if fig_ms:
                st.plotly_chart(fig_ms, use_container_width=True, config={"displayModeBar": False})
        else:
            fig_ms = chart_match_scores(news)
            if fig_ms:
                st.plotly_chart(fig_ms, use_container_width=True, config={"displayModeBar": False})
            st.markdown('<div style="color:#9ca3af;font-size:0.76rem;padding:1rem 0;text-align:center">Select a ticker to see candlestick chart</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div style="color:#ea580c;font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.16em;margin-bottom:0.7rem">Semantically Retrieved Articles</div>', unsafe_allow_html=True)
        if news:
            for art in news[:5]:
                pct   = _match_pct(art)
                color = _match_color(pct)
                dt    = str(art.get("published_at", ""))[:10]
                src   = (art.get("source") or "unknown")[:30]
                title = art["title"][:85] + ("..." if len(art["title"]) > 85 else "")
                bar_w = int(pct)
                st.markdown(f"""
                <div class="newscard">
                    <div class="ntitle">{title}</div>
                    <div class="nmeta">{dt}  ·  {src}</div>
                    <div style="display:flex;align-items:center;gap:0.5rem;margin-top:5px">
                        <div class="match-bar-wrap" style="flex:1">
                            <div class="match-bar-fill" style="width:{bar_w}%;background:linear-gradient(90deg,{color}88,{color})"></div>
                        </div>
                        <span style="font-size:0.65rem;font-weight:700;color:{color};min-width:36px">{pct}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#9ca3af;font-size:0.78rem">No embedded articles found. Run embed_news.py first.</div>', unsafe_allow_html=True)

    with c3:
        fig_m = chart_macro_bars(macro)
        if fig_m:
            st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

        if ratings:
            st.markdown('<div style="color:#ea580c;font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.16em;margin:0.8rem 0 0.5rem 0">Analyst Ratings</div>', unsafe_allow_html=True)
            for r in ratings[:4]:
                rc = "#059669" if r["rating"] in ("Buy", "Outperform", "Overweight") \
                     else ("#db2777" if r["rating"] in ("Sell", "Underperform", "Underweight") \
                     else "#6b7280")
                st.markdown(f"""
                <div class="rbadge">
                    <div style="color:{rc};font-weight:700;font-size:0.74rem">{r['rating']}</div>
                    <div style="color:#9ca3af;font-size:0.63rem">{r['analyst_firm'][:28]}</div>
                    <div style="color:#9ca3af;font-size:0.6rem">{str(r['rating_date'])[:10]}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    time.sleep(0.3)

    # Stage 3 - Generation
    pipe_slot.markdown(pipeline_html(3), unsafe_allow_html=True)

    context = ""
    if company_info:
        context += f"Company: {company_info['name']} ({company_info['ticker']})\n"
    if prices:
        context += "\nRecent Stock Prices (OHLCV, most recent first):\n"
        for p in prices[:10]:
            context += f"  {p['trade_date']}: Open ${p['open_price']}  High ${p['high_price']}  Low ${p['low_price']}  Close ${p['close_price']}  Vol {p['volume']}\n"
    if ratings:
        context += "\nAnalyst Ratings:\n"
        for r in ratings:
            context += f"  {r['rating_date']} | {r['analyst_firm']}: {r['rating']}\n"
    if news:
        context += "\nRelevant News Articles (numbered for citation):\n"
        for i, n in enumerate(news, 1):
            pub = str(n.get('published_at', ''))[:10]
            src = n.get('source', 'unknown')
            context += f"\n[{i}] {n['title']}\n    Source: {src}  Date: {pub}\n    {(n.get('content') or '')[:400]}\n"
    context += "\nMacroeconomic Indicators (FRED):\n"
    for m in macro:
        context += f"  {m['indicator_name']}: {m['value']} {m['unit']} (as of {m['recorded_date']})\n"

    st.markdown('<div class="gcard" style="border-color:#d1fae5">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#059669">Step 04  LLM Generation  Gemini 2.5 Flash</div>', unsafe_allow_html=True)

    g1, g2 = st.columns([1, 1])
    with g2:
        with st.expander("Context window sent to Gemini", expanded=False):
            st.code(context[:2800] + (" ...[truncated]" if len(context) > 2800 else ""), language="markdown")
        st.markdown(f"""
        <div style="font-size:0.7rem;color:#6b7280;line-height:2.1;margin-top:0.6rem">
            Context words &nbsp;<span style="color:#059669;font-weight:600">{len(context.split())}</span><br>
            Articles retrieved &nbsp;<span style="color:#ea580c;font-weight:600">{len(news)}</span><br>
            Price rows &nbsp;<span style="color:#2563eb;font-weight:600">{len(prices)}</span><br>
            Macro indicators &nbsp;<span style="color:#7c3aed;font-weight:600">{len(macro)}</span><br>
            Analyst ratings &nbsp;<span style="color:#db2777;font-weight:600">{len(ratings)}</span>
        </div>
        """, unsafe_allow_html=True)

    with g1:
        with st.status("Gemini reasoning over retrieved financial context...", expanded=False) as s:
            from app.rag import generate_answer
            answer = generate_answer(query, context)
            s.update(label="Answer generated", state="complete")

    st.markdown('</div>', unsafe_allow_html=True)
    time.sleep(0.3)

    # Stage 4 - Answer
    pipe_slot.markdown(pipeline_html(5), unsafe_allow_html=True)

    st.markdown('<div class="gcard" style="border-color:#fce7f3;box-shadow:0 4px 30px rgba(219,39,119,0.07)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#db2777">Step 05  RAG Answer</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="query-echo">"{query}"</div>', unsafe_allow_html=True)

    answer_body, sources_text = parse_answer(answer)

    # Render structured answer as markdown
    st.markdown(answer_body)

    # Sources section
    if sources_text:
        source_lines = [l.strip() for l in sources_text.splitlines() if l.strip()]
        items_html = ''.join(
            f'<div class="source-item">{line}</div>' for line in source_lines
        )
        st.markdown(f"""
        <div class="sources-box">
            <div class="sources-title">Sources &amp; Data References</div>
            {items_html}
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div style="margin-top:1.6rem;padding-top:0.8rem;border-top:1px solid #f3f4f6;
                display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center">
        <span style="font-size:0.65rem;color:#9ca3af">{len(news)} articles retrieved</span>
        <span style="font-size:0.65rem;color:#9ca3af">{len(prices)} price rows</span>
        <span style="font-size:0.65rem;color:#9ca3af">{len(macro)} macro indicators</span>
        <span style="font-size:0.65rem;color:#9ca3af">{len(ratings)} analyst ratings</span>
        <span style="margin-left:auto;font-size:0.62rem;color:#c4b5fd;font-weight:600">MarketPulse RAG</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Add to history
    st.session_state.chat_history.append({'role': 'assistant', 'content': answer_body[:500]})


# ── Idle state ────────────────────────────────────────────────────────────────
def _render_idle():
    st.markdown('<hr class="thinline" style="margin-top:1.5rem">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.22em;color:#9ca3af;text-align:center;margin-bottom:1.1rem">Live Database Status</div>', unsafe_allow_html=True)

    stats, err = load_db_stats()
    if err:
        st.markdown(f'<div style="color:#db2777;font-size:0.8rem;text-align:center;padding:1rem">Connection error: {err}</div>', unsafe_allow_html=True)
        return

    items = [
        ("Companies",    f"{stats.get('companies',0):,}",           "#7c3aed"),
        ("Price Rows",   f"{stats.get('stock_prices',0):,}",        "#2563eb"),
        ("Articles",     f"{stats.get('news_articles',0):,}",       "#ea580c"),
        ("Embedded",     f"{stats.get('embedded',0):,}",            "#059669"),
        ("Macro Rows",   f"{stats.get('economic_indicators',0):,}", "#db2777"),
        ("Ratings",      f"{stats.get('analyst_ratings',0):,}",     "#0891b2"),
    ]
    cols = st.columns(6)
    for col, (label, val, color) in zip(cols, items):
        with col:
            st.markdown(f"""
            <div class="statbadge" style="border-color:{color}33;border-top:3px solid {color}">
                <span class="statval"
                      style="background:linear-gradient(135deg,{color},{color}99);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                             background-clip:text;font-size:1.4rem">{val}</span>
                <span class="statkey">{label}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="thinline" style="margin-top:1.8rem">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.2em;color:#9ca3af;text-align:center;margin-bottom:1rem">System Architecture</div>', unsafe_allow_html=True)

    arch = [
        ("yfinance\nFRED\nNewsAPI",       "#9ca3af", "Data Sources"),
        ("PostgreSQL\n7 tables\n3NF",     "#7c3aed", "Relational DB"),
        ("pgvector\nHNSW index\n768-dim", "#2563eb", "Vector Store"),
        ("MPNet\nSentence\nTransformer",  "#0891b2", "Embeddings"),
        ("Gemini\n2.5 Flash\nLLM",        "#059669", "Generation"),
    ]
    html = '<div style="display:flex;justify-content:center;align-items:center;gap:0;flex-wrap:nowrap;overflow-x:auto;padding:0.2rem 0.5rem">'
    for i, (label, color, title) in enumerate(arch):
        if i > 0:
            html += f'<div style="width:40px;height:1.5px;background:linear-gradient(90deg,{color}44,{color}88);flex-shrink:0;margin-bottom:20px"></div>'
        lines = label.split('\n')
        html += f"""
        <div style="text-align:center;flex-shrink:0">
            <div style="font-size:0.56rem;color:#9ca3af;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px">{title}</div>
            <div style="border:1.5px solid {color}44;border-top:2.5px solid {color};border-radius:10px;padding:0.65rem 0.9rem;
                        background:{color}07;min-width:76px;box-shadow:0 2px 10px {color}10">
                {'<br>'.join(f'<span style="color:{color};font-size:0.68rem;font-family:Space Grotesk,monospace;font-weight:600">{l}</span>' for l in lines)}
            </div>
        </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
