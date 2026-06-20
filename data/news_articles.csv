-- =============================================================================
-- MarketPulse — Data Import Script
-- Z2004 DBMS Project | Milestone 2
--
-- Loads the simulator-generated CSVs into the schema created by schema.sql.
-- Uses psql \copy (client-side) so it works on a clean machine with no
-- server-side superuser file permissions.
--
-- RUN FROM THE PROJECT ROOT:
--   psql -d marketpulse -f schema/schema.sql
--   psql -d marketpulse -f data/import_data.sql
--
-- Load order respects foreign keys:
--   sectors -> companies -> stock_prices
--                        -> analyst_ratings
--           news_articles -> article_company
--           economic_indicators (standalone)
-- =============================================================================

\echo '== Importing MarketPulse dataset =='

-- Clean slate so the import is re-runnable (children first).
TRUNCATE article_company, analyst_ratings, stock_prices,
         news_articles, economic_indicators, companies, sectors
         RESTART IDENTITY CASCADE;

-- 1. SECTORS ------------------------------------------------------------------
\copy sectors (sector_id, sector_name, industry_name) FROM 'data/sectors.csv' WITH (FORMAT csv, HEADER true)

-- 2. COMPANIES ----------------------------------------------------------------
-- market_cap_usd is left empty in the CSV for tickers yfinance does not report;
-- FORCE_NULL makes psql load those empty fields as SQL NULL instead of erroring.
\copy companies (company_id, ticker, name, sector_id, exchange, market_cap_usd) FROM 'data/companies.csv' WITH (FORMAT csv, HEADER true, FORCE_NULL (market_cap_usd))

-- 3. STOCK_PRICES -------------------------------------------------------------
-- price_id is SERIAL and omitted from the CSV → assigned automatically.
\copy stock_prices (company_id, trade_date, open_price, high_price, low_price, close_price, volume, adjusted_close) FROM 'data/stock_prices.csv' WITH (FORMAT csv, HEADER true)

-- 4. NEWS_ARTICLES ------------------------------------------------------------
-- embedding is empty in the CSV (computed later by the RAG pipeline) → NULL.
\copy news_articles (article_id, title, content, url, published_at, source, sentiment_score, embedding) FROM 'data/news_articles.csv' WITH (FORMAT csv, HEADER true, FORCE_NULL (sentiment_score, embedding))

-- 5. ARTICLE_COMPANY (junction) ----------------------------------------------
\copy article_company (article_id, company_id) FROM 'data/article_company.csv' WITH (FORMAT csv, HEADER true)

-- 6. ANALYST_RATINGS ----------------------------------------------------------
-- target_price_usd is mostly empty (documented yfinance limitation) → NULL.
\copy analyst_ratings (rating_id, company_id, analyst_firm, rating, target_price_usd, rating_date) FROM 'data/analyst_ratings.csv' WITH (FORMAT csv, HEADER true, FORCE_NULL (target_price_usd))

-- 7. ECONOMIC_INDICATORS ------------------------------------------------------
\copy economic_indicators (indicator_id, indicator_name, value, recorded_date, source, unit) FROM 'data/economic_indicators.csv' WITH (FORMAT csv, HEADER true)

-- -----------------------------------------------------------------------------
-- Re-sync SERIAL sequences: rows were inserted with explicit IDs, so the
-- sequences must be advanced past the max value or future INSERTs collide.
-- -----------------------------------------------------------------------------
SELECT setval('sectors_sector_id_seq',
              (SELECT MAX(sector_id)  FROM sectors));
SELECT setval('companies_company_id_seq',
              (SELECT MAX(company_id) FROM companies));
SELECT setval('stock_prices_price_id_seq',
              (SELECT MAX(price_id)   FROM stock_prices));
SELECT setval('news_articles_article_id_seq',
              (SELECT MAX(article_id) FROM news_articles));
SELECT setval('analyst_ratings_rating_id_seq',
              (SELECT MAX(rating_id)  FROM analyst_ratings));
SELECT setval('economic_indicators_indicator_id_seq',
              (SELECT MAX(indicator_id) FROM economic_indicators));

-- -----------------------------------------------------------------------------
-- Row-count summary so the TA sees the load succeeded.
-- -----------------------------------------------------------------------------
\echo ''
\echo '== Row counts after import =='
SELECT 'sectors'             AS table_name, COUNT(*) AS rows FROM sectors
UNION ALL SELECT 'companies',            COUNT(*) FROM companies
UNION ALL SELECT 'stock_prices',         COUNT(*) FROM stock_prices
UNION ALL SELECT 'news_articles',        COUNT(*) FROM news_articles
UNION ALL SELECT 'article_company',      COUNT(*) FROM article_company
UNION ALL SELECT 'analyst_ratings',      COUNT(*) FROM analyst_ratings
UNION ALL SELECT 'economic_indicators',  COUNT(*) FROM economic_indicators
ORDER BY table_name;

\echo ''
\echo '== Import complete =='
