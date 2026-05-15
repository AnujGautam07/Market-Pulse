# Market-Pulse
AI-powered fintech platform that analyzes stock market movements using financial news, real-time market data, and RAG-based semantic search.

Link - https://github.com/AnujGautam07/Market-Pulse.git


MarketPulse — Milestone 2: Dataset and Queries

Z2004 Database Management Systems · IIT Madras Zanzibar · Track A (RAG Pipeline)
Team: Nidheesh Deepu Nair (ZDA24B013) · Anuj Gautam (ZDA24B033) · Shreyash Kumar Pandey (ZDA24B004)
MarketPulse is a finance-domain RAG pipeline that explains why stock prices move by
linking structured market data (prices, ratings, macro indicators) with news articles.
This milestone delivers the dataset that fills the Milestone 1 schema, the SQL query
suite, and the instructions to reproduce both from scratch.
---
1. Repository contents (Milestone 2)
```
marketpulse/
├── schema/
│   └── schema.sql              # Milestone 1 DDL (7 tables, 3NF) — included so M2 runs standalone
├── data/
│   ├── data.csv                # combined long-format dataset (table_name, record_json)
│   ├── sectors.csv             # per-table CSVs consumed by import_data.sql
│   ├── companies.csv
│   ├── stock_prices.csv
│   ├── news_articles.csv
│   ├── article_company.csv
│   ├── analyst_ratings.csv
│   ├── economic_indicators.csv
│   └── import_data.sql         # loads every CSV into the schema (psql \copy)
├── queries/
│   └── queries.sql             # 14 labelled queries (see Section 5)
├── scripts/
│   ├── generate_data.py        # dataset simulator (deterministic, seeded)
│   └── verify.sql              # optional integrity / row-count checks
└── README.md                   # this file
```
---
2. Prerequisites
Requirement	Version used	Notes
PostgreSQL	14 or newer (tested on 16)	`psql` client must be on `PATH`
pgvector extension	0.6.0	Needed by `schema.sql` for the `VECTOR(768)` embedding column
Python	3.10+ (tested on 3.12)	Only the standard library is used — no pip install needed
Install pgvector (Debian/Ubuntu): `sudo apt-get install postgresql-16-pgvector`
(or build from https://github.com/pgvector/pgvector).
---
3. How to reproduce from scratch
All commands are run from the project root (`marketpulse/`).
Step 1 — Create the database
```bash
createdb marketpulse
```
Step 2 — Create the schema (7 tables, constraints, indexes, pgvector extension)
```bash
psql -d marketpulse -f schema/schema.sql
```
Step 3 — Generate the dataset (writes all CSVs into `data/`)
```bash
python3 scripts/generate_data.py
```
The simulator is deterministic (fixed RNG seed `20260515`), so this reproduces the
exact dataset every time. The CSVs are already committed, so this step is optional if
you just want to load the provided data.
Step 4 — Import the data
```bash
psql -d marketpulse -f data/import_data.sql
```
Step 5 — Run the queries
```bash
psql -d marketpulse -f queries/queries.sql
```
Optional — Verify integrity and row counts
```bash
psql -d marketpulse -f scripts/verify.sql
```
> If your PostgreSQL needs a username/password, prepend the connection flags, e.g.
> `psql -U postgres -h localhost -d marketpulse -f schema/schema.sql`.
---
4. Dataset description
4.1 Source and generation method
The Z2004 data policy permits a documented simulator that mimics realistic
constraints. The production MarketPulse pipeline will pull live data from yfinance,
NewsAPI/GNews/RSS feeds, and FRED (as documented in the Milestone 1 schema comments).
For Milestone 2 we use `scripts/generate_data.py`, a simulator that reproduces the
shape and constraints of that real data:
Stock prices follow Geometric Brownian Motion with per-sector drift and
volatility, so every ticker has a plausible, continuous price path (not random noise).
Daily volume is log-normal and spikes on large-return days.
News sentiment is correlated with the next trading day's return of the company
the article mentions — reproducing the causal "news → price" relationship the RAG
pipeline is built to surface.
Analyst ratings are sampled only from the rating vocabulary allowed by the schema
`CHECK` constraint; `target_price_usd` is left NULL in ~80% of rows, exactly as the
schema documents for the real yfinance limitation.
Economic indicators reproduce five real FRED series (Federal Funds Rate, CPI,
Unemployment Rate, 10-Year Treasury Yield, Real GDP Growth) at realistic levels.
Referential integrity holds by construction — all foreign keys are generated from
in-memory parent IDs.
The generator is seeded, so the dataset is fully reproducible.
4.2 Row counts
Table	Rows	Notes
`sectors`	10	GICS-style sector / industry pairs
`companies`	25	Real tickers (AAPL, NVDA, JPM, …); 2 have NULL `market_cap_usd` by design
`stock_prices`	12,600	25 tickers × 504 trading days (~2 years)
`news_articles`	1,500	Exceeds the Track A minimum of 1,000
`article_company`	1,500	Junction table resolving the article ↔ company M:N relationship
`analyst_ratings`	324	~10–15 ratings per company
`economic_indicators`	104	5 FRED series, monthly/quarterly, ~2 years
Total	16,063	
Trading-day window: 2024-06-04 to 2026-05-08.
4.3 Data dictionary
`sectors`
Column	Type	Meaning / allowed range
`sector_id`	SERIAL PK	Surrogate key
`sector_name`	VARCHAR(100)	Broad GICS category, e.g. "Technology", "Energy"
`industry_name`	VARCHAR(150)	Sub-category, e.g. "Semiconductors"
`companies`
Column	Type	Meaning / allowed range
`company_id`	SERIAL PK	Surrogate key
`ticker`	VARCHAR(10), UNIQUE	Exchange symbol, e.g. "AAPL" (natural candidate key)
`name`	VARCHAR(200)	Company legal name
`sector_id`	INT FK → sectors	Each company belongs to exactly one sector
`exchange`	VARCHAR(20)	One of: NYSE, NASDAQ, AMEX, OTC, LSE, OTHER
`market_cap_usd`	NUMERIC(20,2)	Market capitalisation in USD; NULL allowed (not always reported), must be ≥ 0
`stock_prices`
Column	Type	Meaning / allowed range
`price_id`	SERIAL PK	Surrogate key
`company_id`	INT FK → companies	Owning company
`trade_date`	DATE	Trading day; `(company_id, trade_date)` is UNIQUE
`open_price`	NUMERIC(12,4)	Opening price, USD, > 0
`high_price`	NUMERIC(12,4)	Intraday high, USD, > 0, ≥ `low_price`
`low_price`	NUMERIC(12,4)	Intraday low, USD, > 0
`close_price`	NUMERIC(12,4)	Closing price, USD, > 0
`volume`	BIGINT	Shares traded, ≥ 0
`adjusted_close`	NUMERIC(12,4)	Split/dividend-adjusted close, USD
`news_articles`
Column	Type	Meaning / allowed range
`article_id`	SERIAL PK	Surrogate key
`title`	TEXT	Headline
`content`	TEXT	Article body (short, mimics free-tier API truncation)
`url`	VARCHAR(2048), UNIQUE	Canonical URL; prevents duplicate ingestion
`published_at`	TIMESTAMPTZ	Publication timestamp (UTC)
`source`	VARCHAR(100)	One of: NewsAPI.org, GNews, Yahoo Finance RSS, Google News RSS
`sentiment_score`	NUMERIC(4,3)	Computed sentiment, range −1.000 … 1.000; NULL allowed
`embedding`	VECTOR(768)	768-dim semantic vector; NULL in this dataset — computed later by the RAG pipeline
`article_company` (junction)
Column	Type	Meaning
`article_id`	INT FK → news_articles	Part of composite PK
`company_id`	INT FK → companies	Part of composite PK
`analyst_ratings`
Column	Type	Meaning / allowed range
`rating_id`	SERIAL PK	Surrogate key
`company_id`	INT FK → companies	Rated company
`analyst_firm`	VARCHAR(150)	Issuing firm, e.g. "Morgan Stanley"
`rating`	VARCHAR(20)	One of: Buy, Sell, Hold, Outperform, Underperform, Neutral, Overweight, Underweight, Market Perform
`target_price_usd`	NUMERIC(12,2)	12-month price target, USD, > 0; NULL in most rows (documented yfinance limitation)
`rating_date`	DATE	Date of rating; `(company_id, analyst_firm, rating_date)` is UNIQUE
`economic_indicators`
Column	Type	Meaning / allowed range
`indicator_id`	SERIAL PK	Surrogate key
`indicator_name`	VARCHAR(200)	FRED series description, e.g. "Federal Funds Effective Rate"
`value`	NUMERIC(16,6)	Indicator value
`recorded_date`	DATE	Observation date; `(indicator_name, recorded_date)` is UNIQUE
`source`	VARCHAR(50)	One of: FRED, BLS, BEA, OTHER (default FRED)
`unit`	VARCHAR(50)	Unit of measure, e.g. "Percent", "Index 1982-84=100"
4.4 Import notes
`import_data.sql` uses client-side `\copy`, so it works on a clean machine with no
server-side superuser file permissions.
Empty CSV fields for `market_cap_usd`, `sentiment_score`, `embedding`, and
`target_price_usd` are loaded as SQL NULL via the `FORCE_NULL` option.
After loading rows with explicit IDs, the script re-syncs every `SERIAL` sequence with
`setval(...)` so future `INSERT`s do not collide.
The script begins with `TRUNCATE ... RESTART IDENTITY CASCADE`, so it is re-runnable.
---
5. Query suite (`queries/queries.sql`)
14 labelled queries. The rubric requires a minimum of 2 each of aggregations, joins,
subqueries, CTEs, and window functions (≥ 10 total). Coverage map:
Category	Queries
Aggregation	Q1, Q2, Q9, Q12
Join	Q3, Q4, Q10, Q13
Subquery	Q5, Q6, Q14
CTE	Q7, Q8, Q11, Q13
Window function	Q8, Q9, Q10, Q11, Q12

#	Category	What it answers
Q1	Aggregation	Sector-level market overview: company count, total & average market cap per sector
Q2	Aggregation	Per-company trading-activity summary (trading days, avg volume, price range) with `HAVING`
Q3	Join (3-table)	Latest closing price for every company, with its sector
Q4	Join (LEFT + junction)	News coverage count & average sentiment per company, including uncovered companies
Q5	Subquery (non-correlated)	Companies with market cap above the all-company average
Q6	Subquery (correlated)	Companies with ≥ 2 "Buy" ratings and positive average news sentiment
Q7	CTE	Holding-period return per company from first to last adjusted close
Q8	CTE + Window	Top 3 single-day gains per company (`LAG`, `ROW_NUMBER`)
Q9	Aggregation + Window	7-day moving average of AAPL's close price (sliding frame)
Q10	Join + Window	Companies ranked within their sector by market cap (`RANK`, `SUM OVER`)
Q11	CTE + Window	Monthly average sentiment per company with month-over-month change (`LAG`)
Q12	Aggregation + Window	Analyst rating mix per company with each rating's share of the total
Q13	CTE + Join	Monthly average market close vs the Federal Funds Rate (macro ↔ market link)
Q14	Subquery (derived table)	The most actively traded company in each sector
Every query is commented with its category, the SQL features it uses, and its business
value. All 14 run on a freshly built database with the provided scripts.
---
6. AI Usage Disclosure
Per the Z2004 AI Tools Policy:
Tool: Claude (Anthropic) and ChatGPT (OpenAI).
Used for: brainstorming the structure of the dataset simulator; drafting the
Geometric Brownian Motion price model; suggesting SQL query ideas that exercise the
required feature categories; debugging `\copy` / `FORCE_NULL` import issues; drafting
this README.
What we changed / verified ourselves: we set every business parameter (tickers,
sectors, drift/volatility values, row counts, date range); we aligned all column names
and constraints to our Milestone 1 `schema.sql`; we ran every query against the live
database and checked the results for correctness and meaning; we wrote and ran
`verify.sql` to confirm referential integrity. We are responsible for the correctness
and understanding of everything submitted.
---
7. Known limitations
`embedding` is NULL throughout this dataset — embeddings are generated by the Python
RAG pipeline (Milestone 3 / Final), not at data-load time. The `VECTOR(768)` column and
its HNSW index already exist in the schema and are ready to be populated.
`target_price_usd` is NULL in ~80% of `analyst_ratings` rows. This mirrors the real
yfinance limitation documented in the Milestone 1 schema, not a data-quality gap.
The dataset is simulator-generated. It reproduces the constraints, distributions, and
relationships of the real sources but is not live market data; the production pipeline
swaps in the real APIs documented in `schema/schema.sql`.
