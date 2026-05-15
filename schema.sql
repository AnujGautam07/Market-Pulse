-- =============================================================================
-- MarketPulse: RAG Pipeline for Stock Price Movement Analysis
-- Z2004 Database Management Systems — IIT Madras Zanzibar
-- Team: Nidheesh Deepu Nair (ZDA24B013), Anuj Gautam (ZDA24B033),
--       Shreyash Kumar Pandey (ZDA24B004)
-- Track: A — RAG Pipeline (Retrieval-Augmented Generation)
-- Milestone 1 — Schema Design and DDL  (API-audited revision)
-- =============================================================================

-- Enable pgvector for semantic similarity search on news embeddings.
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- NORMALISATION ARGUMENT (3NF)
-- -----------------------------------------------------------------------------
-- All tables satisfy Third Normal Form (3NF):
--   1NF: Every column holds a single atomic value; no repeating groups.
--   2NF: Every non-key attribute depends on the WHOLE primary key.
--        (Relevant for ARTICLE_COMPANY where PK is composite.)
--   3NF: No transitive dependencies among non-key attributes.
--        Where such dependencies existed (company → sector details),
--        they were removed by decomposing into a separate SECTORS table.
--
-- Key functional dependencies:
--   SECTORS             : sector_id → sector_name, industry_name
--   COMPANIES           : company_id → ticker, name, sector_id, exchange,
--                         market_cap_usd  (ticker is a candidate key;
--                         sector attrs live in SECTORS to remove transitive dep)
--   STOCK_PRICES        : price_id → company_id, trade_date, all price cols
--                         (company_id + trade_date = natural candidate key)
--   NEWS_ARTICLES       : article_id → title, content, url, published_at,
--                         source, sentiment_score, embedding  (url = candidate key)
--   ARTICLE_COMPANY     : (article_id, company_id) composite PK; no other attrs
--   ANALYST_RATINGS     : rating_id → company_id, analyst_firm, rating,
--                         target_price_usd, rating_date
--   ECONOMIC_INDICATORS : indicator_id → indicator_name, value, recorded_date,
--                         source, unit  (indicator_name + recorded_date = natural key)
-- =============================================================================


-- =============================================================================
-- TABLE 1: SECTORS
-- API source: yf.Ticker(ticker).info
--   info["sector"]   → sector_name
--   info["industry"] → industry_name
-- Seeded once during company registration.
-- Isolated from COMPANIES to eliminate transitive dependency (3NF).
-- =============================================================================
CREATE TABLE IF NOT EXISTS sectors (
    sector_id     SERIAL        PRIMARY KEY,
    sector_name   VARCHAR(100)  NOT NULL,
    industry_name VARCHAR(150)  NOT NULL,

    CONSTRAINT uq_sector_industry UNIQUE (sector_name, industry_name)
);

COMMENT ON TABLE  sectors IS
  'GICS sector/industry classification. Sourced from yf.Ticker().info["sector"] '
  'and ["industry"]. Isolated from COMPANIES to satisfy 3NF.';
COMMENT ON COLUMN sectors.sector_id    IS 'Surrogate primary key; auto-incremented.';
COMMENT ON COLUMN sectors.sector_name  IS 'Broad GICS category, e.g. Technology, Energy.';
COMMENT ON COLUMN sectors.industry_name IS 'Sub-category, e.g. Semiconductors, Biotech.';


-- =============================================================================
-- TABLE 2: COMPANIES
-- API source: yf.Ticker(ticker).info
--   info["longName"]   → name
--   info["symbol"]     → ticker
--   info["exchange"]   → exchange
--   info["marketCap"]  → market_cap_usd  (NULL when not reported)
-- ticker is UNIQUE — the natural candidate key for all downstream API calls.
-- =============================================================================
CREATE TABLE IF NOT EXISTS companies (
    company_id     SERIAL         PRIMARY KEY,
    ticker         VARCHAR(10)    NOT NULL,
    name           VARCHAR(200)   NOT NULL,
    sector_id      INT            NOT NULL,
    exchange       VARCHAR(20)    NOT NULL,
    market_cap_usd NUMERIC(20, 2),

    CONSTRAINT uq_ticker UNIQUE (ticker),
    CONSTRAINT fk_company_sector
        FOREIGN KEY (sector_id) REFERENCES sectors (sector_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_exchange
        CHECK (exchange IN ('NYSE','NASDAQ','AMEX','OTC','LSE','OTHER')),
    CONSTRAINT chk_market_cap
        CHECK (market_cap_usd IS NULL OR market_cap_usd >= 0)
);

COMMENT ON TABLE  companies IS
  'Publicly traded companies. Seeded via yf.Ticker(ticker).info for each of '
  '~25 tickers. ticker is the natural candidate key used by all price/news APIs.';
COMMENT ON COLUMN companies.ticker IS
  'Exchange ticker symbol (e.g. AAPL). Natural candidate key.';
COMMENT ON COLUMN companies.sector_id IS
  'FK to sectors. Normalised here to eliminate transitive dependency (3NF).';
COMMENT ON COLUMN companies.market_cap_usd IS
  'Point-in-time market cap from yf.info["marketCap"]. '
  'NULL when yfinance does not report it (ETFs, smaller tickers).';


-- =============================================================================
-- TABLE 3: STOCK_PRICES
-- API source (primary):  yf.Ticker(ticker).history(period="2y")
--   DataFrame columns: Open, High, Low, Close, Volume  (index = Date)
--   adjusted_close: yfinance Close with auto_adjust=True is already adjusted.
-- API source (fallback): Alpha Vantage TIME_SERIES_DAILY_ADJUSTED
-- Row count: 25 tickers × ~500 trading days ≈ 12,500 rows (exceeds 1,000 min).
-- (company_id, trade_date) is the natural candidate key → UNIQUE constraint.
-- =============================================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    price_id       SERIAL          PRIMARY KEY,
    company_id     INT             NOT NULL,
    trade_date     DATE            NOT NULL,
    open_price     NUMERIC(12, 4)  NOT NULL,
    high_price     NUMERIC(12, 4)  NOT NULL,
    low_price      NUMERIC(12, 4)  NOT NULL,
    close_price    NUMERIC(12, 4)  NOT NULL,
    volume         BIGINT          NOT NULL,
    adjusted_close NUMERIC(12, 4),

    CONSTRAINT uq_company_date
        UNIQUE (company_id, trade_date),
    CONSTRAINT fk_price_company
        FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_prices_positive
        CHECK (open_price > 0 AND close_price > 0
               AND high_price > 0 AND low_price > 0),
    CONSTRAINT chk_high_gte_low
        CHECK (high_price >= low_price),
    CONSTRAINT chk_volume_nonneg
        CHECK (volume >= 0)
);

COMMENT ON TABLE  stock_prices IS
  'Daily OHLCV price data. Primary source: yf.Ticker().history(period="2y"). '
  'Fallback: Alpha Vantage TIME_SERIES_DAILY_ADJUSTED. '
  '25 tickers × ~500 trading days ≈ 12,500 rows. '
  '(company_id, trade_date) is the natural candidate key.';
COMMENT ON COLUMN stock_prices.adjusted_close IS
  'Split/dividend-adjusted close. yfinance returns this when auto_adjust=True '
  '(default). Used for accurate historical return calculations.';
COMMENT ON COLUMN stock_prices.volume IS
  'Shares traded on trade_date. Used as market activity signal in RAG context.';


-- =============================================================================
-- TABLE 4: NEWS_ARTICLES
-- API sources:
--   NewsAPI.org      : title, description, url, publishedAt, source.name
--                      *** Free tier truncates content to ~200 chars ***
--   GNews API        : title, description, url, publishedAt, source.name
--   Yahoo Finance RSS: feedparser → entry.title, entry.link, entry.summary
--   Google News RSS  : feedparser → same fields  (no API key needed)
--
-- sentiment_score: COMPUTED by Python pipeline (VADER / FinBERT) before INSERT.
-- embedding:       COMPUTED by SentenceTransformer("all-mpnet-base-v2").encode(
--                    title + " " + description)  → 768-dim vector.
--                  Uses title+description (NOT raw content) because NewsAPI
--                  free tier truncates content — sentence-transformers gives
--                  high-quality embeddings from short text.
--
-- url is a natural candidate key → prevents duplicate ingestion across sources.
-- =============================================================================
CREATE TABLE IF NOT EXISTS news_articles (
    article_id      SERIAL          PRIMARY KEY,
    title           TEXT            NOT NULL,
    content         TEXT            NOT NULL,   -- may be truncated to ~200 chars
    url             VARCHAR(2048)   NOT NULL,
    published_at    TIMESTAMPTZ     NOT NULL,
    source          VARCHAR(100)    NOT NULL,
    sentiment_score NUMERIC(4, 3),              -- computed; range -1.000 to 1.000
    embedding       VECTOR(768),                -- computed; 768-dim all-mpnet-base-v2

    CONSTRAINT uq_article_url UNIQUE (url),
    CONSTRAINT chk_sentiment
        CHECK (sentiment_score IS NULL
               OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0))
);

COMMENT ON TABLE  news_articles IS
  'News articles from NewsAPI, GNews, Yahoo Finance RSS, Google News RSS. '
  'embedding (VECTOR 768) enables cosine similarity RAG retrieval via pgvector. '
  'Target: 1,000+ rows across all sources and tickers.';
COMMENT ON COLUMN news_articles.content IS
  'Raw article body. NOTE: NewsAPI free tier truncates to ~200 chars. '
  'Embeddings are generated from (title + description) not from this column.';
COMMENT ON COLUMN news_articles.sentiment_score IS
  'COMPUTED by Python pipeline before INSERT — not from any external API. '
  'Range: -1.0 (negative) to 1.0 (positive). NULL until pipeline runs.';
COMMENT ON COLUMN news_articles.embedding IS
  '768-dim vector from SentenceTransformer("all-mpnet-base-v2"). '
  'COMPUTED on (title + " " + description) to handle free-tier content truncation. '
  'Indexed with HNSW for fast approximate cosine similarity in RAG retrieval.';
COMMENT ON COLUMN news_articles.url IS
  'Canonical source URL. UNIQUE prevents duplicate ingestion when the same '
  'article appears in multiple feeds (e.g. Yahoo RSS + NewsAPI).';


-- =============================================================================
-- TABLE 5: ARTICLE_COMPANY  (junction / associative table)
-- NO external API call required.
-- Populated entirely at INGESTION TIME:
--   When NewsAPI/GNews is queried with q="AAPL Apple", every returned article
--   is immediately tagged with Apple's company_id in a single INSERT.
--   No NLP entity extraction needed — the search query defines the link.
-- Resolves the M:N relationship between NEWS_ARTICLES and COMPANIES.
-- 3NF: composite PK with no other attributes → no partial or transitive deps.
-- =============================================================================
CREATE TABLE IF NOT EXISTS article_company (
    article_id  INT  NOT NULL,
    company_id  INT  NOT NULL,

    PRIMARY KEY (article_id, company_id),

    CONSTRAINT fk_ac_article
        FOREIGN KEY (article_id)  REFERENCES news_articles (article_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ac_company
        FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

COMMENT ON TABLE  article_company IS
  'Junction table for the M:N relationship between NEWS_ARTICLES and COMPANIES. '
  'Populated at ingestion time: every article from a ticker-specific API query '
  '(e.g. NewsAPI q="AAPL") is tagged with that company_id — no NLP needed. '
  'Required for 3NF: avoids multi-valued company columns in NEWS_ARTICLES.';
COMMENT ON COLUMN article_company.article_id IS
  'FK to the news article. Cascade delete when article is removed.';
COMMENT ON COLUMN article_company.company_id IS
  'FK to the company linked via the search query used at fetch time.';


-- =============================================================================
-- TABLE 6: ANALYST_RATINGS
-- API source: yf.Ticker(ticker).recommendations
--   DataFrame columns: Firm → analyst_firm, "To Grade" → rating, index → rating_date
--
-- KNOWN API LIMITATION — target_price_usd:
--   yf.recommendations does NOT provide per-firm target prices.
--   yf.Ticker().analyst_price_targets returns AGGREGATE values only
--   (current, low, high, mean, median) — not per-firm per-date.
--   Therefore target_price_usd is NULL for individual rows.
--   This is by design; the column stays for potential enrichment and
--   is fully documented here and in README.md.
-- =============================================================================
CREATE TABLE IF NOT EXISTS analyst_ratings (
    rating_id        SERIAL         PRIMARY KEY,
    company_id       INT            NOT NULL,
    analyst_firm     VARCHAR(150)   NOT NULL,
    rating           VARCHAR(20)    NOT NULL,
    target_price_usd NUMERIC(12, 2),            -- NULL in most rows; see comment above
    rating_date      DATE           NOT NULL,

    CONSTRAINT uq_rating_per_firm_date
        UNIQUE (company_id, analyst_firm, rating_date),
    CONSTRAINT fk_rating_company
        FOREIGN KEY (company_id) REFERENCES companies (company_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_rating_value
        CHECK (rating IN ('Buy','Sell','Hold','Outperform','Underperform',
                          'Neutral','Overweight','Underweight','Market Perform')),
    CONSTRAINT chk_target_price
        CHECK (target_price_usd IS NULL OR target_price_usd > 0)
);

COMMENT ON TABLE  analyst_ratings IS
  'Analyst ratings from yf.Ticker().recommendations. '
  'Fields: Firm, To Grade, date. ~5–20 rows per ticker (~200 rows total). '
  'Used as supplementary RAG context alongside news and price data.';
COMMENT ON COLUMN analyst_ratings.target_price_usd IS
  'Per-firm 12-month price target. NULL in most rows because '
  'yf.Ticker().recommendations does NOT include per-firm targets. '
  'Aggregate targets (mean/median/high/low) are available from '
  'yf.Ticker().analyst_price_targets but are not per-firm-per-date. '
  'Column retained for potential future enrichment from other data sources.';
COMMENT ON COLUMN analyst_ratings.rating IS
  'Normalised from yfinance "To Grade" field. Constrained to standard '
  'analyst vocabulary for reliable SQL aggregation (e.g. COUNT by rating).';


-- =============================================================================
-- TABLE 7: ECONOMIC_INDICATORS
-- API source: FRED (Federal Reserve Economic Data)
-- Python library: fredapi  (pip install fredapi --break-system-packages)
-- FRED series used:
--   FEDFUNDS         : Federal Funds Rate           (monthly, %)
--   CPIAUCSL         : Consumer Price Index         (monthly, Index)
--   UNRATE           : US Unemployment Rate         (monthly, %)
--   GS10             : 10-Year Treasury Yield       (monthly, %)
--   A191RL1Q225SBEA  : Real GDP Growth Rate         (quarterly, %)
-- Estimated rows: 5 series × 36 months = ~180 rows minimum.
-- No FK link to other tables; used as standalone RAG context.
-- (indicator_name, recorded_date) forms the natural candidate key.
-- =============================================================================
CREATE TABLE IF NOT EXISTS economic_indicators (
    indicator_id   SERIAL         PRIMARY KEY,
    indicator_name VARCHAR(200)   NOT NULL,
    value          NUMERIC(16, 6) NOT NULL,
    recorded_date  DATE           NOT NULL,
    source         VARCHAR(50)    NOT NULL DEFAULT 'FRED',
    unit           VARCHAR(50)    NOT NULL,

    CONSTRAINT uq_indicator_date
        UNIQUE (indicator_name, recorded_date),
    CONSTRAINT chk_indicator_source
        CHECK (source IN ('FRED','BLS','BEA','OTHER'))
);

COMMENT ON TABLE  economic_indicators IS
  'Macroeconomic time-series from FRED via fredapi Python library. '
  'Provides market-wide context in RAG pipeline responses '
  '(e.g. "rate hike correlates with this equity decline"). '
  'Standalone entity — no FK relationship to COMPANIES.';
COMMENT ON COLUMN economic_indicators.indicator_name IS
  'Human-readable FRED series description. Combined with recorded_date '
  'as the natural candidate key (enforced by UNIQUE constraint).';
COMMENT ON COLUMN economic_indicators.unit IS
  'Unit from FRED metadata via fred.get_series_info(series_id).units, '
  'e.g. Percent, Index 1982-84=100, Billions of Chained 2012 Dollars.';


-- =============================================================================
-- INDEXES
-- B-Tree indexes on high-frequency lookup columns (for EXPLAIN ANALYZE evidence).
-- pgvector HNSW index for approximate nearest-neighbour embedding search.
-- All created AFTER table definitions per DDL best practice.
-- =============================================================================

-- B-Tree: speeds up date-range price queries ("AAPL prices last 30 days")
CREATE INDEX IF NOT EXISTS idx_stock_prices_date
    ON stock_prices (trade_date DESC);

-- B-Tree: speeds up per-company price lookups (most common join in RAG pipeline)
CREATE INDEX IF NOT EXISTS idx_stock_prices_company
    ON stock_prices (company_id);

-- B-Tree: speeds up recent news retrieval by publication time
CREATE INDEX IF NOT EXISTS idx_news_published_at
    ON news_articles (published_at DESC);

-- B-Tree: speeds up article-company lookups for a given company
CREATE INDEX IF NOT EXISTS idx_article_company_company
    ON article_company (company_id);

-- B-Tree: speeds up analyst rating lookups per company
CREATE INDEX IF NOT EXISTS idx_analyst_ratings_company
    ON analyst_ratings (company_id, rating_date DESC);

-- HNSW: approximate nearest-neighbour cosine similarity for RAG embedding search.
-- m=16, ef_construction=64 are recommended defaults for 10k-100k vectors.
-- EXPLAIN ANALYZE on RAG queries will show this index in the execution plan.
CREATE INDEX IF NOT EXISTS idx_news_embedding_hnsw
    ON news_articles
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- END OF SCHEMA
-- Run:    psql -d marketpulse -f schema.sql
-- Verify: psql -d marketpulse -c "\dt"
-- =============================================================================