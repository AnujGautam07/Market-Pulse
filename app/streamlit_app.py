import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import time
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="MarketPulse - RAG Intelligence",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Pastel palette ────────────────────────────────────────────────────────────
# query=lavender, embed=sky, retrieve=peach, generate=mint, answer=rose
STEPS = [
    ("01", "Query",    "#c4b5fd", "rgba(196,181,253,0.08)"),
    ("02", "Embed",    "#93c5fd", "rgba(147,197,253,0.08)"),
    ("03", "Retrieve", "#fdba74", "rgba(253,186,116,0.08)"),
    ("04", "Generate", "#6ee7b7", "rgba(110,231,183,0.08)"),
    ("05", "Answer",   "#f9a8d4", "rgba(249,168,212,0.08)"),
]

# ── CSS ───────────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: radial-gradient(ellipse at 18% 12%, #0c0b22 0%, #060614 60%, #000000 100%);
    min-height: 100vh;
}
#MainMenu, footer, header { visibility: hidden; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #060614; }
::-webkit-scrollbar-thumb { background: #c4b5fd; border-radius: 2px; }

/* Hero */
.hero-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(2.8rem, 5.5vw, 4.8rem);
    font-weight: 700;
    background: linear-gradient(130deg, #c4b5fd 0%, #93c5fd 48%, #fdba74 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-align: center;
    letter-spacing: -2px;
    line-height: 1.0;
    margin-bottom: 0.5rem;
}
.hero-sub {
    color: #374151;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
}
.hero-tagline {
    color: #1f2937;
    text-align: center;
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    margin-bottom: 2rem;
}

/* Pipeline */
.pipe-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1.6rem 0 2rem 0;
}
.pipe-node { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.pipe-icon {
    width: 56px; height: 56px;
    border-radius: 50%;
    border: 1.5px solid #1f2937;
    background: #060614;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    color: #374151;
    letter-spacing: 0.05em;
    transition: all 0.45s cubic-bezier(0.4,0,0.2,1);
}
.pipe-icon.active {
    border-color: var(--c);
    color: var(--c);
    box-shadow: 0 0 18px color-mix(in srgb, var(--c) 40%, transparent),
                0 0 40px color-mix(in srgb, var(--c) 15%, transparent);
    background: var(--bg);
}
.pipe-icon.done {
    border-color: #86efac;
    color: #86efac;
    background: #052e16;
    box-shadow: 0 0 8px rgba(134,239,172,0.2);
}
.pipe-label {
    font-size: 0.6rem;
    color: #1f2937;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
    text-align: center;
}
.pipe-label.active { color: #d1d5db; }
.pipe-label.done   { color: #86efac; }
.pipe-conn {
    width: 72px; height: 1.5px;
    background: #111827;
    margin-bottom: 24px;
    flex-shrink: 0;
    transition: all 0.45s ease;
}
.pipe-conn.done {
    background: linear-gradient(90deg, #86efac55, #86efac);
    box-shadow: 0 0 5px rgba(134,239,172,0.3);
}

/* Thin divider */
.thinline {
    height: 1px;
    background: linear-gradient(90deg, transparent, #c4b5fd22, #93c5fd22, #c4b5fd22, transparent);
    margin: 1.4rem 0;
    border: none;
}

/* Glass card */
.gcard {
    background: rgba(255,255,255,0.022);
    border: 1px solid rgba(255,255,255,0.055);
    border-radius: 20px;
    padding: 1.5rem 1.7rem;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    margin-bottom: 1.1rem;
    animation: riseup 0.55s cubic-bezier(0.4,0,0.2,1) forwards;
}
@keyframes riseup {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
}

.ctitle {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin-bottom: 1.2rem;
}

/* Stat badges */
.statrow { display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 0.4rem 0 1rem 0; }
.statbadge {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 0.65rem 1.1rem;
    text-align: center;
    flex: 1;
    min-width: 80px;
}
.statval {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #c4b5fd, #93c5fd);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: block;
}
.statkey { font-size: 0.6rem; color: #4b5563; text-transform: uppercase; letter-spacing: 0.1em; }

/* Embed info box */
.embed-info {
    background: rgba(147,197,253,0.04);
    border: 1px solid rgba(147,197,253,0.12);
    border-radius: 12px;
    padding: 1rem 1.1rem;
    font-size: 0.74rem;
    color: #6b7280;
    line-height: 2;
}

/* News cards */
.newscard {
    background: rgba(253,186,116,0.035);
    border: 1px solid rgba(253,186,116,0.1);
    border-radius: 12px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    transition: border-color 0.2s;
}
.newscard:hover { border-color: rgba(253,186,116,0.2); }
.ntitle { color: #e5e7eb; font-size: 0.84rem; font-weight: 500; margin-bottom: 0.3rem; line-height: 1.45; }
.nmeta  { color: #4b5563; font-size: 0.67rem; }
.pos { color: #6ee7b7; }
.neg { color: #fca5a5; }
.neu { color: #4b5563; }

/* Rating badge */
.rbadge {
    border-radius: 9px;
    padding: 0.5rem 0.85rem;
    margin-bottom: 0.5rem;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
}

/* Answer */
.answer-body {
    color: #d1d5db;
    font-size: 0.94rem;
    line-height: 1.9;
    white-space: pre-wrap;
}
.query-echo {
    background: rgba(196,181,253,0.06);
    border-left: 2.5px solid #c4b5fd;
    padding: 0.6rem 1.1rem;
    border-radius: 0 10px 10px 0;
    color: #a5b4fc;
    font-size: 0.87rem;
    margin-bottom: 1.4rem;
    font-style: italic;
}

/* Streamlit overrides */
.stTextInput > div > div > input {
    background: rgba(255,255,255,0.035) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #f3f4f6 !important;
    border-radius: 11px !important;
    font-size: 0.93rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: rgba(196,181,253,0.45) !important;
    box-shadow: 0 0 0 2px rgba(196,181,253,0.1) !important;
}
.stSelectbox > div > div {
    background: rgba(255,255,255,0.035) !important;
    border-radius: 11px !important;
}
.stButton > button {
    background: linear-gradient(135deg, #a78bfa 0%, #818cf8 100%) !important;
    color: #f9fafb !important;
    border: none !important;
    border-radius: 11px !important;
    padding: 0.55rem 2.4rem !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    transition: all 0.3s !important;
}
.stButton > button:hover {
    box-shadow: 0 0 20px rgba(196,181,253,0.35) !important;
    transform: translateY(-2px) !important;
}
label, .stSelectbox label { color: #4b5563 !important; font-size: 0.76rem !important; }
div[data-testid="stStatusWidget"] { display: none; }
div[data-testid="stStatus"] > div:first-child {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
}
</style>
    """, unsafe_allow_html=True)


# ── Pipeline HTML ─────────────────────────────────────────────────────────────
def pipeline_html(active: int) -> str:
    out = '<div class="pipe-wrap">'
    for i, (icon, label, color, bg) in enumerate(STEPS):
        if i > 0:
            cls = "pipe-conn done" if i < active else "pipe-conn"
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


# ── Plotly charts ─────────────────────────────────────────────────────────────
def chart_price_surface(prices, company_name: str):
    if not prices:
        return None
    rows   = list(reversed(prices))
    dates  = [str(r['trade_date'])    for r in rows]
    closes = [float(r['close_price']) for r in rows]
    opens  = [float(r['open_price'])  for r in rows]
    x      = list(range(len(dates)))

    fig = go.Figure()
    fig.add_trace(go.Surface(
        z=[closes, opens], x=x, y=[0, 1],
        colorscale=[
            [0.0, '#1e1b4b'],
            [0.35, '#4c1d95'],
            [0.65, '#c4b5fd'],
            [1.0,  '#93c5fd'],
        ],
        showscale=False, opacity=0.78,
        customdata=[dates, dates],
        hovertemplate='%{customdata}<br>$%{z:.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter3d(
        x=x, y=[0]*len(dates), z=closes,
        mode='lines', line=dict(color='#c4b5fd', width=3),
        name='Close',
        hovertext=dates,
        hovertemplate='%{hovertext}<br>Close $%{z:.2f}<extra></extra>',
    ))
    _dark_3d(fig, height=340, title=f"{company_name}  2-Year Price Landscape")
    fig.update_layout(scene_camera=dict(eye=dict(x=1.6, y=-1.4, z=0.9)))
    return fig


def chart_embedding_3d(embedding, n_bg=140):
    vec = np.array(embedding, dtype=float)
    d   = len(vec) // 3
    mag = max(float(np.linalg.norm(vec)), 1e-9)
    q   = [
        float(np.linalg.norm(vec[:d]))     / mag * 10,
        float(np.linalg.norm(vec[d:2*d]))  / mag * 10,
        float(np.linalg.norm(vec[2*d:]))   / mag * 10,
    ]

    rng = np.random.default_rng(7)
    bx = rng.normal(0, 3.5, n_bg)
    by = rng.normal(0, 3.5, n_bg)
    bz = rng.normal(0, 3.5, n_bg)

    # colour background dots by distance from query point
    dist = np.sqrt((bx - q[0])**2 + (by - q[1])**2 + (bz - q[2])**2)

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=bx, y=by, z=bz, mode='markers',
        marker=dict(
            size=2.5,
            color=dist,
            colorscale=[
                [0.0, '#3b1f6b'],
                [0.5, '#1e3a5f'],
                [1.0, '#1f2937'],
            ],
            opacity=0.55,
            showscale=False,
        ),
        name='Document space',
        hovertemplate='Document vector<extra></extra>',
    ))
    # Soft concentric rings around query point
    for r, alpha in [(1.6, 0.18), (2.8, 0.08)]:
        theta = np.linspace(0, 2 * np.pi, 48)
        fig.add_trace(go.Scatter3d(
            x=q[0] + r * np.cos(theta),
            y=q[1] + r * np.sin(theta),
            z=[q[2]] * 48,
            mode='lines',
            line=dict(color=f'rgba(196,181,253,{alpha})', width=1.2),
            showlegend=False, hoverinfo='skip',
        ))
    fig.add_trace(go.Scatter3d(
        x=[q[0]], y=[q[1]], z=[q[2]], mode='markers',
        marker=dict(size=13, color='#c4b5fd', symbol='diamond',
                    line=dict(color='#f3f4f6', width=1.5)),
        name='Query',
        hovertemplate='Query embedding<br>768-dim projection<extra></extra>',
    ))
    _dark_3d(fig, height=330, title='Query Vector  768-dim Embedding Space  (3D projection)')
    fig.update_layout(
        scene_camera=dict(eye=dict(x=1.8, y=1.5, z=0.9)),
        legend=dict(font=dict(color='#6b7280', size=9), bgcolor='rgba(0,0,0,0)'),
        showlegend=True,
    )
    return fig


def chart_macro_bars(macro):
    if not macro:
        return None
    names  = [m['indicator_name'][:22] + ('...' if len(m['indicator_name']) > 22 else '') for m in macro]
    values = [float(m['value']) for m in macro]
    fig = go.Figure(go.Bar(
        y=names, x=values, orientation='h',
        marker=dict(
            color=values,
            colorscale=[[0, '#1e1b4b'], [0.45, '#a78bfa'], [1, '#93c5fd']],
            showscale=False,
        ),
        hovertemplate='%{y}<br>%{x:.4f}<extra></extra>',
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(color='#4b5563', gridcolor='rgba(255,255,255,0.04)', tickfont=dict(size=9)),
        yaxis=dict(color='#6b7280', tickfont=dict(size=9)),
        margin=dict(l=0, r=0, t=6, b=0), height=270,
        font=dict(family='Inter', size=9),
    )
    return fig


def chart_sentiment_gauge(score: float):
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=round(score, 3),
        number=dict(font=dict(color='#c4b5fd', size=28, family='Space Grotesk')),
        title=dict(text='Avg Sentiment', font=dict(color='#4b5563', size=10)),
        gauge=dict(
            axis=dict(range=[-1, 1], tickcolor='#1f2937',
                      tickfont=dict(color='#374151', size=8)),
            bar=dict(color='#c4b5fd', thickness=0.16),
            bgcolor='rgba(0,0,0,0)',
            bordercolor='rgba(255,255,255,0.06)',
            steps=[
                dict(range=[-1,   -0.25], color='rgba(252,165,165,0.12)'),
                dict(range=[-0.25, 0.25], color='rgba(75,85,99,0.06)'),
                dict(range=[ 0.25,  1.0], color='rgba(110,231,183,0.12)'),
            ],
        ),
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=40, b=5),
        height=210,
        font=dict(family='Inter'),
    )
    return fig


def _dark_3d(fig, height=340, title=''):
    scene = dict(
        xaxis=dict(showticklabels=False, backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='rgba(255,255,255,0.03)', color='#1f2937', title=''),
        yaxis=dict(showticklabels=False, backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='rgba(255,255,255,0.03)', title=''),
        zaxis=dict(showticklabels=True,  backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='rgba(255,255,255,0.05)', color='#4b5563', title=''),
        bgcolor='rgba(0,0,0,0)',
    )
    fig.update_layout(
        scene=scene,
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=38, b=0),
        height=height,
        title=dict(text=title, font=dict(color='#374151', size=10), x=0.5),
        showlegend=False,
        font=dict(family='Inter'),
    )


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


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    inject_css()

    st.markdown("""
    <div style="padding:2.8rem 0 0.6rem 0">
        <div class="hero-title">MarketPulse</div>
        <div class="hero-sub">Track A · RAG Intelligence Pipeline</div>
        <div class="hero-tagline">Z2004 DBMS Project · IIT Madras Zanzibar · 2026</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr class="thinline">', unsafe_allow_html=True)

    pipe_slot = st.empty()
    pipe_slot.markdown(pipeline_html(-1), unsafe_allow_html=True)

    st.markdown('<hr class="thinline">', unsafe_allow_html=True)

    # Query card
    st.markdown('<div class="gcard" style="border-color:rgba(196,181,253,0.18)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#c4b5fd">Step 01  Natural Language Query</div>', unsafe_allow_html=True)

    tickers = load_ticker_list()
    ticker_opts = ["No ticker filter"] + [f"{t}  {n}" for t, n in tickers]

    col_q, col_t = st.columns([3, 1])
    with col_q:
        query = st.text_input(
            "Ask the market anything",
            placeholder='"Why did NVDA rally this week?"  or  "What is the Fed rate outlook?"',
            key="q",
        )
    with col_t:
        raw_ticker = st.selectbox("Focus ticker", ticker_opts, key="tk")
        ticker = raw_ticker.split("  ")[0].strip() if raw_ticker != "No ticker filter" else None

    go_btn = st.button("Analyze", key="go")
    st.markdown('</div>', unsafe_allow_html=True)

    if not go_btn:
        _render_idle()
        return

    if not query.strip():
        st.warning("Please enter a question above.")
        return

    _execute_pipeline(query.strip(), ticker, pipe_slot)


def _execute_pipeline(query: str, ticker, pipe_slot):

    # Stage 0
    pipe_slot.markdown(pipeline_html(0), unsafe_allow_html=True)
    time.sleep(0.4)

    # Stage 1 - Embedding
    pipe_slot.markdown(pipeline_html(1), unsafe_allow_html=True)

    st.markdown('<div class="gcard" style="border-color:rgba(147,197,253,0.16)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#93c5fd">Step 02  Query Embedding  sentence-transformers / all-mpnet-base-v2</div>', unsafe_allow_html=True)

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
                <span class="statkey">Max tokens</span>
            </div>
        </div>
        <div class="embed-info">
            Architecture &nbsp;<span style="color:#93c5fd">MPNet</span><br>
            Pooling &nbsp;<span style="color:#c4b5fd">Mean CLS tokens</span><br>
            Similarity &nbsp;<span style="color:#fdba74">Cosine</span><br>
            DB index &nbsp;<span style="color:#6ee7b7">HNSW via pgvector</span>
        </div>
        """, unsafe_allow_html=True)

    with col_chart:
        with st.status("Encoding query into 768-dim vector space", expanded=False) as s:
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

    st.markdown('<div class="gcard" style="border-color:rgba(253,186,116,0.16)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#fdba74">Step 03  Context Retrieval  PostgreSQL + pgvector HNSW</div>', unsafe_allow_html=True)

    with st.status("Querying PostgreSQL  HNSW similarity + B-Tree lookups", expanded=False) as s:
        from app.db import (find_company, get_similar_news, get_recent_prices,
                            get_analyst_ratings, get_recent_economic_indicators)
        company_id, company_info = None, None
        if ticker:
            company_info = find_company(ticker)
            if company_info:
                company_id = company_info["company_id"]
        news    = get_similar_news(embedding, limit=5, company_id=company_id)
        macro   = get_recent_economic_indicators()
        prices  = list(get_recent_prices(company_id, limit=90))  if company_id else []
        ratings = list(get_analyst_ratings(company_id, limit=5)) if company_id else []
        s.update(label=f"Complete  {len(news)} articles, {len(prices)} price rows, {len(macro)} indicators", state="complete")

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        if prices:
            cname = company_info["name"] if company_info else (ticker or "")
            fig_p = chart_price_surface(prices, cname)
            if fig_p:
                st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown('<div style="color:#1f2937;font-size:0.78rem;padding:3rem 0;text-align:center">Select a ticker to render price landscape</div>', unsafe_allow_html=True)

        scores = [float(a.get("sentiment_score") or 0) for a in news] if news else []
        avg_s  = sum(scores) / len(scores) if scores else 0.0
        fig_g  = chart_sentiment_gauge(avg_s)
        if fig_g:
            st.plotly_chart(fig_g, use_container_width=True, config={"displayModeBar": False})

    with c2:
        st.markdown('<div style="color:#fdba74;font-size:0.64rem;font-weight:700;text-transform:uppercase;letter-spacing:0.16em;margin-bottom:0.8rem">Semantically Retrieved Articles</div>', unsafe_allow_html=True)
        if news:
            for art in news[:5]:
                sc  = float(art.get("sentiment_score") or 0)
                cls = "pos" if sc > 0.1 else ("neg" if sc < -0.1 else "neu")
                sc_txt = f'+{sc:.3f}' if sc >= 0 else f'{sc:.3f}'
                dt    = str(art["published_at"])[:10]
                title = art["title"][:90] + ("..." if len(art["title"]) > 90 else "")
                src   = art.get("source") or "unknown"
                st.markdown(f"""
                <div class="newscard">
                    <div class="ntitle">{title}</div>
                    <div class="nmeta">{dt} &nbsp;·&nbsp; {src} &nbsp;·&nbsp; <span class="{cls}">Sentiment {sc_txt}</span></div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#1f2937;font-size:0.8rem">No embedded articles found. Run app/embed_news.py first.</div>', unsafe_allow_html=True)

    with c3:
        st.markdown('<div style="color:#fdba74;font-size:0.64rem;font-weight:700;text-transform:uppercase;letter-spacing:0.16em;margin-bottom:0.8rem">Macro Indicators</div>', unsafe_allow_html=True)
        fig_m = chart_macro_bars(macro)
        if fig_m:
            st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

        if ratings:
            st.markdown('<div style="color:#fdba74;font-size:0.64rem;font-weight:700;text-transform:uppercase;letter-spacing:0.16em;margin:1rem 0 0.6rem 0">Analyst Ratings</div>', unsafe_allow_html=True)
            for r in ratings[:4]:
                rc = "#6ee7b7" if r["rating"] in ("Buy", "Outperform", "Overweight") \
                     else ("#fca5a5" if r["rating"] in ("Sell", "Underperform", "Underweight") \
                     else "#6b7280")
                st.markdown(f"""
                <div class="rbadge">
                    <div style="color:{rc};font-weight:600;font-size:0.76rem">{r['rating']}</div>
                    <div style="color:#374151;font-size:0.66rem">{r['analyst_firm']} · {str(r['rating_date'])[:10]}</div>
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
        context += "\nRecent Stock Prices (Close):\n"
        for p in prices[:5]:
            context += f"  {p['trade_date']}: ${p['close_price']} (Vol: {p['volume']})\n"
    if ratings:
        context += "\nAnalyst Ratings:\n"
        for r in ratings:
            context += f"  {r['rating_date']} | {r['analyst_firm']}: {r['rating']}\n"
    if news:
        context += "\nRelevant News Articles:\n"
        for n in news:
            context += f"  [{n['published_at'].date()}] {n['title']}\n  {n['content']}\n"
    context += "\nMacroeconomic Indicators:\n"
    for m in macro:
        context += f"  {m['indicator_name']}: {m['value']} {m['unit']} ({m['recorded_date']})\n"

    st.markdown('<div class="gcard" style="border-color:rgba(110,231,183,0.14)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#6ee7b7">Step 04  LLM Generation  Gemini 2.5 Flash</div>', unsafe_allow_html=True)

    g1, g2 = st.columns([1, 1])
    with g2:
        with st.expander("Context window sent to Gemini", expanded=False):
            st.code(context[:2500] + (" ...[truncated]" if len(context) > 2500 else ""), language="markdown")
        st.markdown(f"""
        <div style="font-size:0.7rem;color:#374151;line-height:2;margin-top:0.6rem">
            Context words &nbsp;<span style="color:#6ee7b7">{len(context.split())}</span><br>
            Articles retrieved &nbsp;<span style="color:#fdba74">{len(news)}</span><br>
            Price rows &nbsp;<span style="color:#93c5fd">{len(prices)}</span><br>
            Macro indicators &nbsp;<span style="color:#c4b5fd">{len(macro)}</span>
        </div>
        """, unsafe_allow_html=True)

    with g1:
        with st.status("Gemini reasoning over retrieved financial context", expanded=False) as s:
            from app.rag import generate_answer
            answer = generate_answer(query, context)
            s.update(label="Complete  Answer generated", state="complete")

    st.markdown('</div>', unsafe_allow_html=True)
    time.sleep(0.3)

    # Stage 4 - Answer (all done)
    pipe_slot.markdown(pipeline_html(5), unsafe_allow_html=True)

    st.markdown('<div class="gcard" style="border-color:rgba(249,168,212,0.2);box-shadow:0 0 50px rgba(249,168,212,0.04),0 0 100px rgba(196,181,253,0.03)">', unsafe_allow_html=True)
    st.markdown('<div class="ctitle" style="color:#f9a8d4">Step 05  RAG Answer</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="query-echo">"{query}"</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="answer-body">{answer}</div>', unsafe_allow_html=True)

    n_total = len(news) + len(prices) + len(macro) + len(ratings)
    st.markdown(f"""
    <div style="margin-top:2rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,0.04);
                color:#1f2937;font-size:0.68rem;display:flex;gap:2rem;flex-wrap:wrap">
        <span>{len(news)} articles</span>
        <span>{len(prices)} price rows</span>
        <span>{len(macro)} macro indicators</span>
        <span>{len(ratings)} analyst ratings</span>
        <span style="margin-left:auto;color:#111827">{n_total} total context items  MarketPulse RAG</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def _render_idle():
    st.markdown('<hr class="thinline" style="margin-top:2rem">', unsafe_allow_html=True)
    st.markdown('<div style="color:#1f2937;font-size:0.64rem;text-transform:uppercase;letter-spacing:0.22em;text-align:center;margin-bottom:1.2rem">Live Database Status</div>', unsafe_allow_html=True)

    stats, err = load_db_stats()
    if err:
        st.markdown(f'<div style="color:#fca5a5;font-size:0.8rem;text-align:center;padding:1rem">Connection error: {err}</div>', unsafe_allow_html=True)
        return

    items = [
        ("Companies",     f"{stats.get('companies', 0):,}",           "#c4b5fd"),
        ("Price Rows",    f"{stats.get('stock_prices', 0):,}",        "#93c5fd"),
        ("News Articles", f"{stats.get('news_articles', 0):,}",       "#fdba74"),
        ("Embedded",      f"{stats.get('embedded', 0):,}",            "#6ee7b7"),
        ("Macro Series",  f"{stats.get('economic_indicators', 0):,}", "#f9a8d4"),
        ("Ratings",       f"{stats.get('analyst_ratings', 0):,}",     "#a5b4fc"),
    ]
    cols = st.columns(6)
    for col, (label, val, color) in zip(cols, items):
        with col:
            st.markdown(f"""
            <div class="statbadge" style="border-color:{color}28">
                <span class="statval"
                      style="background:linear-gradient(135deg,{color},{color}77);
                             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                             background-clip:text;font-size:1.55rem">{val}</span>
                <span class="statkey">{label}</span>
            </div>
            """, unsafe_allow_html=True)

    # Architecture diagram
    st.markdown('<hr class="thinline" style="margin-top:2rem">', unsafe_allow_html=True)
    st.markdown('<div style="color:#1f2937;font-size:0.64rem;text-transform:uppercase;letter-spacing:0.2em;text-align:center;margin-bottom:1.2rem">Pipeline Architecture</div>', unsafe_allow_html=True)

    arch = [
        ("yfinance\nFRED\nNewsAPI",        "#6b7280", "Data Sources"),
        ("PostgreSQL\n7 tables\n3NF",      "#c4b5fd", "Relational DB"),
        ("pgvector\nHNSW index\n768-dim",  "#a5b4fc", "Vector Store"),
        ("MPNet\nSentence\nTransformer",   "#93c5fd", "Embeddings"),
        ("Gemini\n2.5 Flash\nLLM",         "#6ee7b7", "Generation"),
    ]

    html = '<div style="display:flex;justify-content:center;align-items:center;gap:0;flex-wrap:nowrap;overflow-x:auto;padding:0.4rem 1rem">'
    for i, (label, color, title) in enumerate(arch):
        if i > 0:
            html += f'<div style="width:44px;height:1px;background:linear-gradient(90deg,{color}33,{color}66);flex-shrink:0;margin-bottom:22px"></div>'
        lines = label.split('\n')
        html += f"""
        <div style="text-align:center;flex-shrink:0">
            <div style="font-size:0.58rem;color:#1f2937;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:7px">{title}</div>
            <div style="border:1px solid {color}33;border-radius:11px;padding:0.75rem 1rem;
                        background:{color}07;min-width:82px">
                {'<br>'.join(f'<span style="color:{color};font-size:0.7rem;font-family:Space Grotesk,monospace;font-weight:500">{l}</span>' for l in lines)}
            </div>
        </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
