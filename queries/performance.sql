-- =============================================================================
-- MarketPulse — performance.sql
-- Z2004 Database Management Systems | IIT Madras Zanzibar | Milestone 3
-- Team: Nidheesh Deepu Nair (ZDA24B013), Anuj Gautam (ZDA24B033),
--       Shreyash Kumar Pandey (ZDA24B004)
--
-- This file demonstrates performance optimization through indexing and
-- contains a stored procedure and trigger for data management.
--
-- Run:  psql -d marketpulse -f performance.sql
-- Pre-requisites: schema.sql executed, data imported via import_data.sql
-- =============================================================================


-- =============================================================================
-- SECTION 1: TEST ENVIRONMENT
-- =============================================================================
-- PostgreSQL 16 with pgvector 0.6.0
-- Dataset: 7 tables, 16,063 total rows
--   stock_prices:        12,600 rows (25 tickers × ~504 trading days)
--   news_articles:        1,500 rows
--   article_company:      1,500 rows (junction table)
--   analyst_ratings:        324 rows
--   economic_indicators:    104 rows
--   companies:               25 rows
--   sectors:                 10 rows


-- =============================================================================
-- SECTION 2: DROP CUSTOM INDEXES (BASELINE)
-- Only PK and UNIQUE constraint indexes remain after this step.
-- =============================================================================
\echo '== Dropping custom indexes to establish baseline =='

DROP INDEX IF EXISTS idx_stock_prices_date;
DROP INDEX IF EXISTS idx_stock_prices_company;
DROP INDEX IF EXISTS idx_news_published_at;
DROP INDEX IF EXISTS idx_article_company_company;
DROP INDEX IF EXISTS idx_analyst_ratings_company;
DROP INDEX IF EXISTS idx_news_embedding_hnsw;

\echo '== Baseline established: only PK/UNIQUE indexes remain =='
ANALYZE;


-- =============================================================================
-- SECTION 3: BASELINE EXPLAIN ANALYZE (BEFORE INDEXES)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- SLOW QUERY 1: Date-range price lookup for a specific month
-- WHY IT MATTERS: The RAG pipeline answers questions like "What happened to
-- stocks in October 2025?" This requires filtering stock_prices by trade_date.
-- Without a date index, PostgreSQL must sequentially scan all 12,600 rows
-- even when only ~575 match the filter (4.6% selectivity).
-- ─────────────────────────────────────────────────────────────────────────────
\echo ''
\echo '== BEFORE: Slow Query 1 — Date-range stock price lookup =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    sp.trade_date,
    sp.close_price,
    sp.volume
FROM stock_prices sp
JOIN companies c ON c.company_id = sp.company_id
WHERE sp.trade_date BETWEEN '2025-10-01' AND '2025-10-31'
ORDER BY sp.volume DESC
LIMIT 20;


-- ─────────────────────────────────────────────────────────────────────────────
-- SLOW QUERY 2: Correlated subquery — bullish companies
-- WHY IT MATTERS: Identifies companies where both analyst ratings AND news
-- sentiment agree (a bullish signal). SubPlan 3 runs a correlated subquery
-- that joins article_company and news_articles for EACH of the 25 companies.
-- Without an index on article_company.company_id, each iteration performs a
-- sequential scan of all 1,500 junction rows.
-- ─────────────────────────────────────────────────────────────────────────────
\echo ''
\echo '== BEFORE: Slow Query 2 — Correlated subquery (bullish signal) =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    c.name,
    (SELECT COUNT(*)
       FROM analyst_ratings ar
      WHERE ar.company_id = c.company_id
        AND ar.rating = 'Buy') AS buy_ratings
FROM companies c
WHERE (
        SELECT COUNT(*)
        FROM analyst_ratings ar
        WHERE ar.company_id = c.company_id
          AND ar.rating = 'Buy'
      ) >= 2
  AND (
        SELECT AVG(na.sentiment_score)
        FROM article_company ac
        JOIN news_articles na ON na.article_id = ac.article_id
        WHERE ac.company_id = c.company_id
      ) > 0
ORDER BY buy_ratings DESC, c.ticker;


-- ─────────────────────────────────────────────────────────────────────────────
-- SLOW QUERY 3: Date-range RAG pipeline query (prices + news in a window)
-- WHY IT MATTERS: This is the core RAG retrieval pattern — for a given month,
-- find all stock price movements alongside published news articles to
-- explain "why did prices move?" Without idx_news_published_at, the planner
-- sequentially scans all 1,500 news articles to filter by published_at.
-- ─────────────────────────────────────────────────────────────────────────────
\echo ''
\echo '== BEFORE: Slow Query 3 — RAG pipeline date-range retrieval =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    sp.trade_date,
    sp.close_price,
    sp.volume,
    na.title,
    na.sentiment_score
FROM stock_prices sp
JOIN companies c ON c.company_id = sp.company_id
JOIN article_company ac ON ac.company_id = c.company_id
JOIN news_articles na ON na.article_id = ac.article_id
WHERE sp.trade_date BETWEEN '2024-06-01' AND '2024-06-30'
  AND na.published_at >= '2024-06-01'
  AND na.published_at < '2024-07-01'
ORDER BY sp.trade_date, c.ticker;


-- =============================================================================
-- SECTION 4: INDEX CREATION WITH JUSTIFICATION
-- =============================================================================
\echo ''
\echo '== Creating optimized indexes =='

-- INDEX 1: B-Tree on stock_prices.trade_date (descending)
-- JUSTIFICATION: The most frequent query pattern in the RAG pipeline is
-- "retrieve prices for a specific date range." With 12,600 rows and typical
-- month-long filters selecting ~575 rows (4.6%), a B-Tree index on trade_date
-- enables Bitmap Index Scan instead of Sequential Scan. Descending order
-- optimises the common case of querying recent data first.
CREATE INDEX idx_stock_prices_date
    ON stock_prices (trade_date DESC);

-- INDEX 2: B-Tree on stock_prices.company_id
-- JUSTIFICATION: Per-company price lookups are the second most common join
-- pattern. While the UNIQUE constraint on (company_id, trade_date) provides
-- a composite index, a standalone company_id index allows the planner to
-- use it when only the company filter is needed without a date condition.
CREATE INDEX idx_stock_prices_company
    ON stock_prices (company_id);

-- INDEX 3: B-Tree on news_articles.published_at (descending)
-- JUSTIFICATION: The RAG retrieval pipeline filters news by publication date
-- to match them with price movements in the same time window. Without this
-- index, date-range filters on published_at cause a Sequential Scan of all
-- 1,500 articles. The index converts this to a Bitmap Index Scan.
CREATE INDEX idx_news_published_at
    ON news_articles (published_at DESC);

-- INDEX 4: B-Tree on article_company.company_id
-- JUSTIFICATION: The junction table is queried via correlated subqueries
-- and joins that filter by company_id. The composite PK (article_id,
-- company_id) has article_id as the leading column, so lookups by
-- company_id alone cannot use it. This index eliminates repeated
-- Sequential Scans in correlated subqueries (SubPlan 3 of Query 2).
CREATE INDEX idx_article_company_company
    ON article_company (company_id);

-- INDEX 5: B-Tree on analyst_ratings (company_id, rating_date DESC)
-- JUSTIFICATION: Analyst rating queries typically ask "what are the latest
-- ratings for company X?" The composite index on (company_id, rating_date)
-- supports both equality lookups on company_id and date-ordered retrieval.
CREATE INDEX idx_analyst_ratings_company
    ON analyst_ratings (company_id, rating_date DESC);

-- INDEX 6: HNSW on news_articles.embedding (pgvector cosine similarity)
-- JUSTIFICATION: The RAG pipeline's core operation is approximate nearest-
-- neighbour search — given a user question embedded as a 768-dim vector,
-- find the most semantically similar news articles. Without this HNSW index,
-- cosine similarity search requires a brute-force scan of all 1,500 vectors.
-- Parameters: m=16 (connections per layer), ef_construction=64 (build-time
-- search width), chosen for the 1k–100k vector range per pgvector docs.
CREATE INDEX idx_news_embedding_hnsw
    ON news_articles
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Update planner statistics after index creation
ANALYZE;
\echo '== All indexes created and statistics updated =='


-- =============================================================================
-- SECTION 5: OPTIMIZED EXPLAIN ANALYZE (AFTER INDEXES)
-- =============================================================================

\echo ''
\echo '== AFTER: Slow Query 1 — Date-range stock price lookup =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    sp.trade_date,
    sp.close_price,
    sp.volume
FROM stock_prices sp
JOIN companies c ON c.company_id = sp.company_id
WHERE sp.trade_date BETWEEN '2025-10-01' AND '2025-10-31'
ORDER BY sp.volume DESC
LIMIT 20;


\echo ''
\echo '== AFTER: Slow Query 2 — Correlated subquery (bullish signal) =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    c.name,
    (SELECT COUNT(*)
       FROM analyst_ratings ar
      WHERE ar.company_id = c.company_id
        AND ar.rating = 'Buy') AS buy_ratings
FROM companies c
WHERE (
        SELECT COUNT(*)
        FROM analyst_ratings ar
        WHERE ar.company_id = c.company_id
          AND ar.rating = 'Buy'
      ) >= 2
  AND (
        SELECT AVG(na.sentiment_score)
        FROM article_company ac
        JOIN news_articles na ON na.article_id = ac.article_id
        WHERE ac.company_id = c.company_id
      ) > 0
ORDER BY buy_ratings DESC, c.ticker;


\echo ''
\echo '== AFTER: Slow Query 3 — RAG pipeline date-range retrieval =='
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    c.ticker,
    sp.trade_date,
    sp.close_price,
    sp.volume,
    na.title,
    na.sentiment_score
FROM stock_prices sp
JOIN companies c ON c.company_id = sp.company_id
JOIN article_company ac ON ac.company_id = c.company_id
JOIN news_articles na ON na.article_id = ac.article_id
WHERE sp.trade_date BETWEEN '2024-06-01' AND '2024-06-30'
  AND na.published_at >= '2024-06-01'
  AND na.published_at < '2024-07-01'
ORDER BY sp.trade_date, c.ticker;


-- =============================================================================
-- SECTION 6: STORED PROCEDURE — refresh_sentiment_summary
-- =============================================================================
-- PURPOSE: Aggregates per-company sentiment statistics from the news_articles
-- and article_company tables into a materialised summary table. This avoids
-- re-computing expensive joins and averages each time the RAG pipeline or
-- a dashboard query needs sentiment context.
--
-- WHAT IT DOES:
--   1. Creates (if not exists) a summary table: company_sentiment_summary.
--   2. Truncates and repopulates it with one row per company containing:
--      total article count, average sentiment, most recent article date,
--      and counts of positive / negative / neutral articles.
--   3. Returns a result set so the caller can verify the refresh.
--
-- HOW TO RUN:
--   SELECT * FROM refresh_sentiment_summary();
-- =============================================================================

\echo ''
\echo '== Creating stored procedure: refresh_sentiment_summary =='

-- Summary table to hold pre-computed sentiment aggregates
CREATE TABLE IF NOT EXISTS company_sentiment_summary (
    company_id      INT PRIMARY KEY REFERENCES companies(company_id),
    ticker          VARCHAR(10)  NOT NULL,
    total_articles  INT          NOT NULL DEFAULT 0,
    avg_sentiment   NUMERIC(5,3),
    latest_article  TIMESTAMPTZ,
    positive_count  INT          NOT NULL DEFAULT 0,
    negative_count  INT          NOT NULL DEFAULT 0,
    neutral_count   INT          NOT NULL DEFAULT 0,
    refreshed_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- The stored procedure
CREATE OR REPLACE FUNCTION refresh_sentiment_summary()
RETURNS SETOF company_sentiment_summary
LANGUAGE plpgsql
AS $$
BEGIN
    -- Clear stale data
    TRUNCATE company_sentiment_summary;

    -- Repopulate with fresh aggregates
    INSERT INTO company_sentiment_summary
        (company_id, ticker, total_articles, avg_sentiment,
         latest_article, positive_count, negative_count, neutral_count,
         refreshed_at)
    SELECT
        c.company_id,
        c.ticker,
        COUNT(na.article_id)                                    AS total_articles,
        ROUND(AVG(na.sentiment_score), 3)                       AS avg_sentiment,
        MAX(na.published_at)                                    AS latest_article,
        COUNT(*) FILTER (WHERE na.sentiment_score >  0.05)      AS positive_count,
        COUNT(*) FILTER (WHERE na.sentiment_score < -0.05)      AS negative_count,
        COUNT(*) FILTER (WHERE na.sentiment_score BETWEEN -0.05
                                                   AND    0.05) AS neutral_count,
        NOW()
    FROM companies c
    LEFT JOIN article_company ac ON ac.company_id = c.company_id
    LEFT JOIN news_articles   na ON na.article_id = ac.article_id
    GROUP BY c.company_id, c.ticker;

    RAISE NOTICE 'Sentiment summary refreshed for % companies.',
                 (SELECT COUNT(*) FROM company_sentiment_summary);

    RETURN QUERY SELECT * FROM company_sentiment_summary
                 ORDER BY avg_sentiment DESC NULLS LAST;
END;
$$;

COMMENT ON FUNCTION refresh_sentiment_summary() IS
    'Truncates and repopulates company_sentiment_summary with per-company '
    'sentiment aggregates from news_articles + article_company. '
    'Run after bulk article ingestion to keep the dashboard current.';

-- Execute it to verify
\echo '== Running refresh_sentiment_summary() =='
SELECT * FROM refresh_sentiment_summary();


-- =============================================================================
-- SECTION 7: TRIGGER — auto-flag high-volatility trading days
-- =============================================================================
-- PURPOSE: Automatically flags trading days where a stock's intra-day price
-- range exceeds 5% of its opening price. These are the exact days the RAG
-- pipeline needs to explain ("why did NVDA swing 7% on this date?").
--
-- WHAT IT DOES:
--   1. Creates a volatility_alerts table to store flagged events.
--   2. A BEFORE INSERT trigger on stock_prices checks each new row's
--      intra-day range: (high_price - low_price) / open_price.
--   3. If the range exceeds 5%, it inserts an alert row with the
--      computed volatility percentage.
--
-- HOW TO TEST:
--   INSERT INTO stock_prices (company_id, trade_date, open_price,
--       high_price, low_price, close_price, volume, adjusted_close)
--   VALUES (1, '2026-01-15', 100.00, 110.00, 95.00, 108.00, 5000000, 108.00);
--   SELECT * FROM volatility_alerts ORDER BY flagged_at DESC LIMIT 5;
-- =============================================================================

\echo ''
\echo '== Creating trigger: flag_high_volatility =='

CREATE TABLE IF NOT EXISTS volatility_alerts (
    alert_id        SERIAL       PRIMARY KEY,
    company_id      INT          NOT NULL REFERENCES companies(company_id),
    trade_date      DATE         NOT NULL,
    open_price      NUMERIC(12,4),
    high_price      NUMERIC(12,4),
    low_price       NUMERIC(12,4),
    close_price     NUMERIC(12,4),
    intraday_range_pct NUMERIC(6,2),
    flagged_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION fn_flag_high_volatility()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_range_pct NUMERIC(6,2);
BEGIN
    -- Calculate intra-day range as a percentage of the open
    v_range_pct := ROUND(
        100.0 * (NEW.high_price - NEW.low_price) / NEW.open_price, 2
    );

    -- Flag if the swing exceeds 5%
    IF v_range_pct > 5.0 THEN
        INSERT INTO volatility_alerts
            (company_id, trade_date, open_price, high_price,
             low_price, close_price, intraday_range_pct)
        VALUES
            (NEW.company_id, NEW.trade_date, NEW.open_price,
             NEW.high_price, NEW.low_price, NEW.close_price,
             v_range_pct);
    END IF;

    RETURN NEW;  -- allow the INSERT to proceed
END;
$$;

-- Attach the trigger to stock_prices
DROP TRIGGER IF EXISTS trg_high_volatility ON stock_prices;
CREATE TRIGGER trg_high_volatility
    BEFORE INSERT ON stock_prices
    FOR EACH ROW
    EXECUTE FUNCTION fn_flag_high_volatility();

-- Test the trigger with a high-volatility row
\echo '== Testing trigger with a volatile trading day =='
INSERT INTO stock_prices
    (company_id, trade_date, open_price, high_price, low_price,
     close_price, volume, adjusted_close)
VALUES
    (1, '2026-01-15', 100.0000, 110.0000, 95.0000,
     108.0000, 5000000, 108.0000)
ON CONFLICT (company_id, trade_date) DO NOTHING;

SELECT * FROM volatility_alerts ORDER BY flagged_at DESC LIMIT 5;


-- =============================================================================
-- END OF performance.sql
-- =============================================================================
\echo ''
\echo '== Milestone 3 performance.sql complete =='
