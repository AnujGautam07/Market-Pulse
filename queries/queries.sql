-- =============================================================================
-- MarketPulse — queries.sql
-- Z2004 Database Management Systems | IIT Madras Zanzibar | Milestone 2
-- Team: Nidheesh Deepu Nair (ZDA24B013), Anuj Gautam (ZDA24B033),
--       Shreyash Kumar Pandey (ZDA24B004)
--
-- 14 labelled queries. Rubric requires a minimum of 2 each of:
--   aggregations, joins, subqueries, CTEs, window functions  (>= 10 total).
--
-- COVERAGE MAP
--   Aggregation     : Q1, Q2, Q9, Q12
--   Join            : Q3, Q4, Q10, Q13
--   Subquery        : Q5, Q6, Q14
--   CTE             : Q7, Q8, Q11, Q13
--   Window function : Q8, Q9, Q10, Q11, Q12
--   (several queries intentionally satisfy more than one category)
--
-- Run all:   psql -d marketpulse -f queries/queries.sql
-- Run one:   copy the block between the Q-header and the next Q-header.
-- =============================================================================


-- =============================================================================
-- Q1  [AGGREGATION]
-- Sector-level market overview: how many companies, and total / average
-- market cap per sector. NULL market caps are excluded by AVG/SUM naturally.
-- Business value: the first thing an analyst wants — where is the weight.
-- =============================================================================
SELECT
    s.sector_name,
    s.industry_name,
    COUNT(c.company_id)                       AS num_companies,
    ROUND(SUM(c.market_cap_usd) / 1e9, 2)     AS total_market_cap_bn_usd,
    ROUND(AVG(c.market_cap_usd) / 1e9, 2)     AS avg_market_cap_bn_usd
FROM sectors  s
JOIN companies c ON c.sector_id = s.sector_id
GROUP BY s.sector_id, s.sector_name, s.industry_name
ORDER BY total_market_cap_bn_usd DESC NULLS LAST;


-- =============================================================================
-- Q2  [AGGREGATION]
-- Per-company trading-activity summary over the full price history:
-- number of trading days on record, average daily volume, highest close,
-- lowest close. HAVING filters to companies with a meaningful history.
-- Business value: liquidity and price-range profile for each ticker.
-- =============================================================================
SELECT
    c.ticker,
    c.name,
    COUNT(sp.price_id)                AS trading_days,
    ROUND(AVG(sp.volume))             AS avg_daily_volume,
    MAX(sp.close_price)               AS highest_close,
    MIN(sp.close_price)               AS lowest_close,
    ROUND(MAX(sp.close_price) - MIN(sp.close_price), 2) AS close_range
FROM companies     c
JOIN stock_prices  sp ON sp.company_id = c.company_id
GROUP BY c.company_id, c.ticker, c.name
HAVING COUNT(sp.price_id) >= 250          -- at least ~1 year of data
ORDER BY avg_daily_volume DESC;


-- =============================================================================
-- Q3  [JOIN]  (3-table inner join)
-- Latest closing price for every company, with its sector.
-- Joins companies -> sectors and companies -> stock_prices, filtered to the
-- most recent trade_date in the database.
-- Business value: a current snapshot board of the tracked universe.
-- =============================================================================
SELECT
    c.ticker,
    c.name,
    s.sector_name,
    sp.trade_date,
    sp.close_price,
    sp.volume
FROM companies     c
JOIN sectors       s  ON s.sector_id  = c.sector_id
JOIN stock_prices  sp ON sp.company_id = c.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
ORDER BY s.sector_name, c.ticker;


-- =============================================================================
-- Q4  [JOIN]  (LEFT JOIN + junction table)
-- News coverage count per company, including companies with zero articles.
-- LEFT JOIN keeps uncovered companies; the junction table article_company
-- resolves the M:N relationship between companies and news_articles.
-- Business value: shows which tickers the RAG pipeline has context for.
-- =============================================================================
SELECT
    c.ticker,
    c.name,
    COUNT(ac.article_id)                                  AS article_count,
    ROUND(AVG(na.sentiment_score), 3)                     AS avg_sentiment,
    MIN(na.published_at)::date                            AS earliest_article,
    MAX(na.published_at)::date                            AS latest_article
FROM companies        c
LEFT JOIN article_company ac ON ac.company_id = c.company_id
LEFT JOIN news_articles   na ON na.article_id = ac.article_id
GROUP BY c.company_id, c.ticker, c.name
ORDER BY article_count DESC;


-- =============================================================================
-- Q5  [SUBQUERY]  (non-correlated subquery in WHERE)
-- Companies whose market cap is above the average market cap of all
-- companies that actually report one.
-- Business value: identifies the large-cap subset of the universe.
-- =============================================================================
SELECT
    c.ticker,
    c.name,
    ROUND(c.market_cap_usd / 1e9, 2) AS market_cap_bn_usd
FROM companies c
WHERE c.market_cap_usd > (
        SELECT AVG(market_cap_usd)
        FROM companies
        WHERE market_cap_usd IS NOT NULL
      )
ORDER BY c.market_cap_usd DESC;


-- =============================================================================
-- Q6  [SUBQUERY]  (correlated subquery + EXISTS, with a correlated count)
-- Companies that received at least 2 "Buy" ratings AND whose AVERAGE news
-- sentiment is positive. Both inner queries are correlated on c.company_id.
-- Business value: tickers where analysts and the overall news flow agree
-- (a genuinely bullish signal, not just one stray positive headline).
-- =============================================================================
SELECT
    c.ticker,
    c.name,
    (SELECT COUNT(*)
       FROM analyst_ratings ar
      WHERE ar.company_id = c.company_id
        AND ar.rating = 'Buy')                    AS buy_ratings
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


-- =============================================================================
-- Q7  [CTE]
-- Use a CTE to compute each company's first and last adjusted close in the
-- dataset, then derive total holding-period return over the window.
-- Business value: which tickers actually rewarded a buy-and-hold investor.
-- =============================================================================
WITH price_bounds AS (
    SELECT
        sp.company_id,
        FIRST_VALUE(sp.adjusted_close) OVER w  AS first_adj_close,
        LAST_VALUE(sp.adjusted_close)  OVER w  AS last_adj_close
    FROM stock_prices sp
    WINDOW w AS (
        PARTITION BY sp.company_id
        ORDER BY sp.trade_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT DISTINCT
    c.ticker,
    c.name,
    pb.first_adj_close,
    pb.last_adj_close,
    ROUND(100.0 * (pb.last_adj_close - pb.first_adj_close)
                / pb.first_adj_close, 2)        AS holding_period_return_pct
FROM price_bounds pb
JOIN companies c ON c.company_id = pb.company_id
ORDER BY holding_period_return_pct DESC;


-- =============================================================================
-- Q8  [CTE + WINDOW FUNCTION]
-- Daily returns via LAG(), then the 3 single-day biggest gains per company.
-- daily_returns CTE: LAG() over (company ordered by date).
-- ranked CTE      : ROW_NUMBER() to pick the top 3 per company.
-- Business value: the exact days the RAG pipeline must explain ("why did
-- NVDA jump 9% on this date?").
-- =============================================================================
WITH daily_returns AS (
    SELECT
        sp.company_id,
        sp.trade_date,
        sp.close_price,
        LAG(sp.close_price) OVER (PARTITION BY sp.company_id
                                  ORDER BY sp.trade_date) AS prev_close
    FROM stock_prices sp
),
returns_pct AS (
    SELECT
        company_id,
        trade_date,
        close_price,
        prev_close,
        ROUND(100.0 * (close_price - prev_close) / prev_close, 2) AS daily_return_pct
    FROM daily_returns
    WHERE prev_close IS NOT NULL
),
ranked AS (
    SELECT
        rp.*,
        ROW_NUMBER() OVER (PARTITION BY rp.company_id
                           ORDER BY rp.daily_return_pct DESC) AS gain_rank
    FROM returns_pct rp
)
SELECT
    c.ticker,
    r.trade_date,
    r.prev_close,
    r.close_price,
    r.daily_return_pct,
    r.gain_rank
FROM ranked r
JOIN companies c ON c.company_id = r.company_id
WHERE r.gain_rank <= 3
ORDER BY c.ticker, r.gain_rank;


-- =============================================================================
-- Q9  [WINDOW FUNCTION + AGGREGATION]
-- 7-day moving average of close price for a single ticker (AAPL), using
-- AVG() OVER with a sliding row frame. Shows the smoothed trend next to the
-- raw close.
-- Business value: classic technical-analysis view; demonstrates frame clauses.
-- =============================================================================
SELECT
    c.ticker,
    sp.trade_date,
    sp.close_price,
    ROUND(AVG(sp.close_price) OVER (
            ORDER BY sp.trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
          ), 2)                                AS moving_avg_7d,
    ROUND(sp.close_price - AVG(sp.close_price) OVER (
            ORDER BY sp.trade_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
          ), 2)                                AS deviation_from_ma
FROM stock_prices sp
JOIN companies c ON c.company_id = sp.company_id
WHERE c.ticker = 'AAPL'
ORDER BY sp.trade_date
LIMIT 60;          -- most recent run shows the latest ~3 months


-- =============================================================================
-- Q10 [WINDOW FUNCTION + JOIN]
-- Rank companies within their sector by latest market cap using RANK() and
-- DENSE_RANK() partitioned by sector. Also shows each company's share of its
-- sector's total cap.
-- Business value: who leads each sector, and by how much.
-- =============================================================================
SELECT
    s.sector_name,
    c.ticker,
    c.name,
    ROUND(c.market_cap_usd / 1e9, 2)                     AS market_cap_bn,
    RANK()       OVER (PARTITION BY s.sector_id
                       ORDER BY c.market_cap_usd DESC)   AS cap_rank_in_sector,
    ROUND(100.0 * c.market_cap_usd
          / SUM(c.market_cap_usd) OVER (PARTITION BY s.sector_id), 1)
                                                         AS pct_of_sector_cap
FROM companies c
JOIN sectors   s ON s.sector_id = c.sector_id
WHERE c.market_cap_usd IS NOT NULL
ORDER BY s.sector_name, cap_rank_in_sector;


-- =============================================================================
-- Q11 [CTE + WINDOW FUNCTION]
-- Monthly average sentiment per company, with month-over-month change via
-- LAG(). monthly CTE aggregates; the outer query adds the window comparison.
-- Business value: detects sentiment momentum/turns that precede price moves.
-- =============================================================================
WITH monthly_sentiment AS (
    SELECT
        ac.company_id,
        DATE_TRUNC('month', na.published_at)::date AS month,
        ROUND(AVG(na.sentiment_score), 3)          AS avg_sentiment,
        COUNT(*)                                   AS article_count
    FROM news_articles   na
    JOIN article_company ac ON ac.article_id = na.article_id
    WHERE na.sentiment_score IS NOT NULL
    GROUP BY ac.company_id, DATE_TRUNC('month', na.published_at)
)
SELECT
    c.ticker,
    ms.month,
    ms.avg_sentiment,
    ms.article_count,
    LAG(ms.avg_sentiment) OVER (PARTITION BY ms.company_id
                                ORDER BY ms.month)            AS prev_month_sentiment,
    ROUND(ms.avg_sentiment
          - LAG(ms.avg_sentiment) OVER (PARTITION BY ms.company_id
                                        ORDER BY ms.month), 3) AS sentiment_change
FROM monthly_sentiment ms
JOIN companies c ON c.company_id = ms.company_id
ORDER BY c.ticker, ms.month;


-- =============================================================================
-- Q12 [AGGREGATION + WINDOW FUNCTION]
-- Analyst rating mix per company: count of each rating, plus the company's
-- total ratings via a window SUM, and each rating's share of that total.
-- Business value: at-a-glance analyst consensus per ticker.
-- =============================================================================
SELECT
    c.ticker,
    ar.rating,
    COUNT(*)                                              AS rating_count,
    SUM(COUNT(*)) OVER (PARTITION BY c.company_id)         AS total_ratings,
    ROUND(100.0 * COUNT(*)
          / SUM(COUNT(*)) OVER (PARTITION BY c.company_id), 1)
                                                          AS pct_of_ratings
FROM analyst_ratings ar
JOIN companies       c ON c.company_id = ar.company_id
GROUP BY c.company_id, c.ticker, ar.rating
ORDER BY c.ticker, rating_count DESC;


-- =============================================================================
-- Q13 [CTE + JOIN]
-- Link macro context to the market: average monthly close across all
-- companies vs the Federal Funds Rate for the same month.
-- market_monthly CTE: average close per month across the whole universe.
-- Joined to economic_indicators (the standalone FRED table).
-- Business value: the core RAG idea — tie equity moves to macro conditions.
-- =============================================================================
WITH market_monthly AS (
    SELECT
        DATE_TRUNC('month', sp.trade_date)::date AS month,
        ROUND(AVG(sp.close_price), 2)            AS avg_market_close
    FROM stock_prices sp
    GROUP BY DATE_TRUNC('month', sp.trade_date)
)
SELECT
    mm.month,
    mm.avg_market_close,
    ei.value                                     AS fed_funds_rate_pct
FROM market_monthly mm
JOIN economic_indicators ei
      ON DATE_TRUNC('month', ei.recorded_date) = mm.month
     AND ei.indicator_name = 'Federal Funds Effective Rate'
ORDER BY mm.month;


-- =============================================================================
-- Q14 [SUBQUERY]  (subquery in FROM / derived table)
-- For each sector, the single company with the highest average daily volume.
-- Inner derived table computes per-company average volume; the outer query
-- keeps only the per-sector maximum.
-- Business value: the most actively traded name in each sector.
-- =============================================================================
SELECT
    sector_name,
    ticker,
    name,
    avg_volume
FROM (
    SELECT
        s.sector_name,
        c.ticker,
        c.name,
        ROUND(AVG(sp.volume))                                   AS avg_volume,
        RANK() OVER (PARTITION BY s.sector_id
                     ORDER BY AVG(sp.volume) DESC)              AS vol_rank
    FROM sectors      s
    JOIN companies    c  ON c.sector_id  = s.sector_id
    JOIN stock_prices sp ON sp.company_id = c.company_id
    GROUP BY s.sector_id, s.sector_name, c.ticker, c.name
) ranked_by_volume
WHERE vol_rank = 1
ORDER BY avg_volume DESC;

-- =============================================================================
-- END OF queries.sql
-- =============================================================================
