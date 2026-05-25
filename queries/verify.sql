-- =============================================================================
-- MarketPulse — verify.sql
-- Z2004 Database Management Systems | IIT Madras Zanzibar
-- Team: Nidheesh Deepu Nair (ZDA24B013), Anuj Gautam (ZDA24B033),
--       Shreyash Kumar Pandey (ZDA24B004)
--
-- Integrity and row-count verification script.
-- Run after import_data.sql to confirm the dataset was loaded correctly.
--
-- Usage:  psql -d marketpulse -f queries/verify.sql
-- =============================================================================

\echo '========================================'
\echo 'MarketPulse — Integrity Verification'
\echo '========================================'

-- ---------------------------------------------------------------------------
-- 1. Row counts — confirm all tables are populated
-- ---------------------------------------------------------------------------
\echo ''
\echo '== Row counts =='
SELECT
    table_name,
    row_count
FROM (
    VALUES
        ('sectors',             (SELECT COUNT(*) FROM sectors)),
        ('companies',           (SELECT COUNT(*) FROM companies)),
        ('stock_prices',        (SELECT COUNT(*) FROM stock_prices)),
        ('news_articles',       (SELECT COUNT(*) FROM news_articles)),
        ('article_company',     (SELECT COUNT(*) FROM article_company)),
        ('analyst_ratings',     (SELECT COUNT(*) FROM analyst_ratings)),
        ('economic_indicators', (SELECT COUNT(*) FROM economic_indicators))
) AS t(table_name, row_count)
ORDER BY table_name;

-- ---------------------------------------------------------------------------
-- 2. Minimum-row check — Track A requires >= 1,000 meaningful rows
-- ---------------------------------------------------------------------------
\echo ''
\echo '== Track A minimum row check (>= 1000 total meaningful rows) =='
SELECT
    CASE
        WHEN (SELECT COUNT(*) FROM news_articles) +
             (SELECT COUNT(*) FROM stock_prices) >= 1000
        THEN 'PASS — minimum row count met'
        ELSE 'FAIL — fewer than 1000 rows across news + prices'
    END AS row_count_check;

-- ---------------------------------------------------------------------------
-- 3. Embedding coverage — all news articles must have embeddings
--    (populated by: python3 -m app.embed_news)
-- ---------------------------------------------------------------------------
\echo ''
\echo '== Embedding coverage =='
SELECT
    COUNT(*)                                        AS total_articles,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL)   AS with_embedding,
    COUNT(*) FILTER (WHERE embedding IS NULL)       AS missing_embedding,
    CASE
        WHEN COUNT(*) FILTER (WHERE embedding IS NULL) = 0
        THEN 'PASS — all articles embedded'
        ELSE 'WARN — run: PYTHONPATH=. venv/bin/python3 app/embed_news.py'
    END AS embedding_check
FROM news_articles;

-- ---------------------------------------------------------------------------
-- 4. Referential integrity — dangling FKs should return 0 rows each
-- ---------------------------------------------------------------------------
\echo ''
\echo '== Referential integrity checks (all should return 0 rows) =='

-- companies.sector_id → sectors
SELECT 'companies.sector_id orphan' AS check_name, COUNT(*) AS orphan_count
FROM companies c
WHERE NOT EXISTS (SELECT 1 FROM sectors s WHERE s.sector_id = c.sector_id)
UNION ALL
-- stock_prices.company_id → companies
SELECT 'stock_prices.company_id orphan', COUNT(*)
FROM stock_prices sp
WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.company_id = sp.company_id)
UNION ALL
-- article_company.article_id → news_articles
SELECT 'article_company.article_id orphan', COUNT(*)
FROM article_company ac
WHERE NOT EXISTS (SELECT 1 FROM news_articles n WHERE n.article_id = ac.article_id)
UNION ALL
-- article_company.company_id → companies
SELECT 'article_company.company_id orphan', COUNT(*)
FROM article_company ac
WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.company_id = ac.company_id)
UNION ALL
-- analyst_ratings.company_id → companies
SELECT 'analyst_ratings.company_id orphan', COUNT(*)
FROM analyst_ratings ar
WHERE NOT EXISTS (SELECT 1 FROM companies c WHERE c.company_id = ar.company_id);

-- ---------------------------------------------------------------------------
-- 5. Constraint checks — values must respect CHECK constraints
-- ---------------------------------------------------------------------------
\echo ''
\echo '== CHECK constraint violations (all should return 0) =='

SELECT 'stock_prices: negative/zero price'  AS check_name,
       COUNT(*) AS violations
FROM stock_prices
WHERE open_price <= 0 OR close_price <= 0 OR high_price <= 0 OR low_price <= 0
UNION ALL
SELECT 'stock_prices: high < low',
       COUNT(*)
FROM stock_prices
WHERE high_price < low_price
UNION ALL
SELECT 'news_articles: sentiment out of [-1,1]',
       COUNT(*)
FROM news_articles
WHERE sentiment_score IS NOT NULL
  AND (sentiment_score < -1.0 OR sentiment_score > 1.0)
UNION ALL
SELECT 'analyst_ratings: unrecognised rating',
       COUNT(*)
FROM analyst_ratings
WHERE rating NOT IN (
    'Buy','Sell','Hold','Outperform','Underperform',
    'Neutral','Overweight','Underweight','Market Perform'
)
UNION ALL
SELECT 'companies: invalid exchange code',
       COUNT(*)
FROM companies
WHERE exchange NOT IN ('NYSE','NASDAQ','AMEX','OTC','LSE','OTHER');

-- ---------------------------------------------------------------------------
-- 6. Pgvector extension and HNSW index
-- ---------------------------------------------------------------------------
\echo ''
\echo '== pgvector extension and HNSW index =='
SELECT
    (SELECT extname FROM pg_extension WHERE extname = 'vector') AS pgvector_installed,
    (SELECT indexname FROM pg_indexes
     WHERE tablename = 'news_articles'
       AND indexname  = 'idx_news_embedding_hnsw')               AS hnsw_index_present;

-- ---------------------------------------------------------------------------
-- 7. Index presence — all B-Tree indexes from schema.sql
-- ---------------------------------------------------------------------------
\echo ''
\echo '== B-Tree indexes =='
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
      'idx_stock_prices_date',
      'idx_stock_prices_company',
      'idx_news_published_at',
      'idx_article_company_company',
      'idx_analyst_ratings_company'
  )
ORDER BY tablename, indexname;

-- ---------------------------------------------------------------------------
-- 8. Date range sanity — prices span at least 1 year
-- ---------------------------------------------------------------------------
\echo ''
\echo '== Price date range =='
SELECT
    MIN(trade_date)                          AS earliest_date,
    MAX(trade_date)                          AS latest_date,
    MAX(trade_date) - MIN(trade_date)        AS span_days,
    COUNT(DISTINCT company_id)               AS companies_covered
FROM stock_prices;

\echo ''
\echo '== Verification complete =='
