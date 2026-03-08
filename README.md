# Market-Pulse

AI-powered fintech platform that explains stock market movements by linking structured market data (prices, analyst ratings, macro indicators) with news articles through a RAG (Retrieval-Augmented Generation) pipeline.

Repository: https://github.com/AnujGautam07/Market-Pulse.git

---

## Final Submission

Z2004 Database Management Systems · IIT Madras Zanzibar · Track A (RAG Pipeline)
Team: Nidheesh Deepu Nair (ZDA24B013) · Anuj Gautam (ZDA24B033) · Shreyash Kumar Pandey (ZDA24B004)

---

## 1. Repository Structure

```
Market-Pulse/
├── schema/
│   ├── schema.sql              # DDL: 7 tables, 3NF, pgvector extension, HNSW + B-Tree indexes
│   └── ER-diagram.pdf          # Entity-Relationship diagram
├── data/
│   ├── fetch_real_data.py      # Live data fetcher (yfinance, Yahoo RSS, Google RSS, FRED, NewsAPI)
│   ├── import_data.sql         # Loads all CSVs into the schema via \copy
│   ├── companies.csv
│   ├── sectors.csv
│   ├── stock_prices.csv        # 2-year daily OHLCV for 50 tickers (~25,050 rows)
│   ├── news_articles.csv       # Articles from Yahoo Finance RSS + Google News RSS + NewsAPI
│   ├── article_company.csv     # Many-to-many: article <-> company
│   ├── analyst_ratings.csv     # Analyst upgrades/downgrades (yfinance)
│   ├── economic_indicators.csv # 8 FRED macroeconomic series (2022-present)
│   └── data.csv                # Combined long-format dataset
├── queries/
│   ├── queries.sql             # 14 labelled queries demonstrating SQL features
│   ├── performance.sql         # EXPLAIN ANALYZE and index optimization notes
│   └── verify.sql              # Integrity and row-count checks
├── app/
│   ├── db.py                   # PostgreSQL connection and all query functions
│   ├── rag.py                  # Sentence-transformer embeddings + Gemini LLM
│   ├── main.py                 # CLI entry point
│   ├── embed_news.py           # Populates pgvector embeddings for all news articles
│   ├── streamlit_app.py        # Streamlit web frontend (interactive RAG pipeline UI)
│   ├── test_cases.py           # 3 core test cases
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Template for API keys and DB credentials
│   └── .env                    # Local secrets (never commit)
├── report/
│   ├── MarketPulse_Milestone3_Report.pdf
│   └── 3NF,justification_notes.pdf
├── demo/                       # 5-minute screen-recorded demo video
├── setup_mac.sh                # One-shot setup script for macOS
└── README.md
```

---

## 2. Prerequisites

- **PostgreSQL 18** via Homebrew (`postgresql@18`). Start with `brew services start postgresql@18`.
- **pgvector extension** installed into PostgreSQL (needed for `VECTOR(768)` and HNSW index).
- **Python 3.9+** (the venv in this repo uses Python 3.9).
- API keys (free tier, no credit card required):
  - `GEMINI_API_KEY` from Google AI Studio (optional; app falls back gracefully without it)
  - `FRED_API_KEY` from fred.stlouisfed.org/docs/api/api_key.html
  - `NEWSAPI_KEY` from newsapi.org/register (100 requests/day free)

> All psql commands below require `-U <your-os-username>`. On macOS with Homebrew Postgres the
> superuser is your macOS username, not `postgres`. Maintenance operations (DROP/CREATE DATABASE)
> must connect to `-d postgres` because you cannot drop the database you are connected to.

---

## 3. Setup and Run (End-to-End)

All commands are run from the `Market-Pulse/` project root.

### Step 1 - Create virtual environment and install dependencies

```bash
python3 -m venv venv
PYTHONPATH=. venv/bin/pip install -r app/requirements.txt
```

### Step 2 - Set environment variables

```bash
cp app/.env.example app/.env
# Edit app/.env and fill in GEMINI_API_KEY, FRED_API_KEY, NEWSAPI_KEY
# Leave DB_USER and DB_PASSWORD blank on macOS Homebrew Postgres (peer auth)
```

### Step 3 - Create database and schema

```bash
psql -U <your-username> -d postgres -c "DROP DATABASE IF EXISTS marketpulse;"
psql -U <your-username> -d postgres -c "CREATE DATABASE marketpulse;"
psql -U <your-username> -d marketpulse -f schema/schema.sql
```

### Step 4 - Fetch live data (takes 15-30 minutes)

Pulls real data from yfinance (50 tickers, 2-year OHLCV), Yahoo Finance RSS, Google News RSS,
NewsAPI.org, and FRED. Writes 7 CSV files into `data/`.

```bash
venv/bin/python3 data/fetch_real_data.py
```

Data universe: 50 tickers across Technology, Consumer, Financial, Healthcare, Energy, and
Communication sectors. FRED series: FEDFUNDS, CPIAUCSL, UNRATE, GS10, GDP growth, USD/EUR,
WTI crude oil, VIX.

### Step 5 - Load CSVs into PostgreSQL

```bash
psql -U <your-username> -d marketpulse -f data/import_data.sql
```

### Step 6 - Generate vector embeddings

Generates 768-dimensional embeddings for all news articles using `all-mpnet-base-v2` and stores
them in the `news_articles.embedding VECTOR(768)` column. The HNSW index is then used for
approximate nearest-neighbour search.

```bash
PYTHONPATH=. venv/bin/python3 app/embed_news.py
```

### Step 7 - Run the Streamlit frontend

Interactive web UI showing the full RAG pipeline step by step with live 3D visualizations.

```bash
PYTHONPATH=. venv/bin/python3 -m streamlit run app/streamlit_app.py
```

Opens at http://localhost:8501

### Step 8 - Run the CLI

```bash
PYTHONPATH=. venv/bin/python3 app/main.py "Why did NVDA rally this week?" --ticker NVDA
PYTHONPATH=. venv/bin/python3 app/main.py "What is the Fed rate outlook?"
```

### Step 9 - Run test cases

```bash
PYTHONPATH=. venv/bin/python3 app/test_cases.py
```

> Note: there is no `__init__.py` in `app/`. All scripts must be run with `PYTHONPATH=.` from the
> project root so that `from app.db import ...` resolves correctly. Running `python3 -m app.main`
> without `PYTHONPATH=.` will fail with a ModuleNotFoundError.

---

## 4. Schema, Indexing and AI Components

### Schema (7 tables, 3NF)

| Table | Description |
|---|---|
| `sectors` | Industry sector lookup |
| `companies` | 50 companies with ticker, exchange, market cap |
| `stock_prices` | Daily OHLCV + adjusted close per company |
| `news_articles` | Articles with title, content, sentiment score, 768-dim embedding |
| `article_company` | Many-to-many join between articles and companies |
| `analyst_ratings` | Analyst firm upgrades/downgrades with target price |
| `economic_indicators` | FRED macroeconomic time series |

### Indexing

- **B-Tree indexes** on `stock_prices(company_id, trade_date)`, `news_articles(published_at)`,
  `analyst_ratings(company_id, rating_date)` for high-frequency range and lookup queries.
- **HNSW index** on `news_articles.embedding VECTOR(768)` using cosine distance (`vector_cosine_ops`)
  for approximate nearest-neighbour semantic search via pgvector.

### AI Components

- **Embeddings**: `sentence-transformers/all-mpnet-base-v2` runs locally (no API key needed).
  Produces 768-dim dense vectors. Sentiment scoring uses NLTK VADER (also local, no API key).
- **LLM**: Google Gemini via `google-generativeai`. Model fallback order:
  `gemini-2.5-flash` -> `gemini-flash-latest` -> `gemini-2.0-flash` -> `gemini-2.5-pro`.
  If all fail or no key is set, the app returns the raw retrieved context (fallback mode).

---

## 5. RAG Pipeline Flow

```
User query
    |
    v
Generate 768-dim query embedding (all-mpnet-base-v2)
    |
    v
PostgreSQL retrieval
    |- HNSW cosine search on news_articles.embedding  (semantic similarity)
    |- B-Tree lookup on stock_prices                  (recent OHLCV)
    |- B-Tree lookup on analyst_ratings               (recent ratings)
    |- Latest row per series from economic_indicators (macro context)
    |
    v
Assemble context string (company info + prices + ratings + news + macro)
    |
    v
Gemini LLM generates answer with inline source citations
    |
    v
Response displayed in Streamlit UI or printed to CLI
```

---

## 6. Fallback Mode

If `GEMINI_API_KEY` is not set or the API is unavailable, the application automatically enters
fallback mode. All PostgreSQL retrieval and HNSW semantic search still run normally. The raw
structured context is returned directly instead of an LLM-synthesised answer. This guarantees
that the pipeline always produces output regardless of external API availability.

---

## 7. Environment Variables

All variables go in `app/.env` (never commit this file).

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=marketpulse
DB_USER=                  # leave blank on macOS Homebrew (uses OS username via peer auth)
DB_PASSWORD=              # leave blank on macOS Homebrew

GEMINI_API_KEY=           # optional; falls back gracefully if absent
FRED_API_KEY=             # required for fetch_real_data.py macro data
NEWSAPI_KEY=              # optional; RSS feeds still work without it
```

---

## 8. Dependencies

Key packages (full list in `app/requirements.txt`):

| Package | Purpose |
|---|---|
| `psycopg2-binary` | PostgreSQL driver |
| `pgvector` | Python client for pgvector |
| `sentence-transformers` | Local embedding model (all-mpnet-base-v2) |
| `google-generativeai` | Gemini LLM API |
| `yfinance` | Stock price and analyst rating data |
| `feedparser` | Yahoo Finance RSS and Google News RSS |
| `nltk` | VADER sentiment scoring |
| `fredapi` | FRED macroeconomic data |
| `streamlit` | Web frontend |
| `plotly` | 3D interactive charts in the frontend |
| `python-dotenv` | .env file loading |

---

## 9. AI Usage Disclosure

Per the Z2004 AI Tools Policy:
- **Tool**: Claude (Anthropic)
- **Used for**: SQL query optimisation, RAG pipeline integration (embedding logic and LLM prompt
  design), Streamlit frontend design, data fetcher architecture
