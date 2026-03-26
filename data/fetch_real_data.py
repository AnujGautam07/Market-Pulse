#!/usr/bin/env python3
"""
MarketPulse — Real Data Fetcher
Z2004 DBMS Project | IIT Madras Zanzibar

Fetches live data from all documented project sources:
  - yfinance                 : stock prices (2yr OHLCV), company info, analyst ratings
  - Yahoo Finance RSS        : financial news  (no key needed)
  - Google News RSS          : financial news  (no key needed)
  - FRED via fredapi         : macroeconomic indicators  (free key: fred.stlouisfed.org)
  - NewsAPI.org              : broader news corpus  (free key: newsapi.org)
  - NLTK VADER               : offline sentiment scoring  (no key needed)

Keys to add to app/.env before running:
    FRED_API_KEY=<key>         free at  fred.stlouisfed.org/docs/api/api_key.html
    NEWSAPI_KEY=<key>          free at  newsapi.org/register  (100 req/day free tier)

Usage (run from project root):
    pip install -r app/requirements.txt
    python3 data/fetch_real_data.py
    psql -U <user> -d marketpulse -f schema/schema.sql
    psql -U <user> -d marketpulse -f data/import_data.sql
"""

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as url_quote

# ---------------------------------------------------------------------------
# Dependency check — give a clear install hint for each missing package
# ---------------------------------------------------------------------------
def _import_or_exit(module, install_name=None):
    import importlib
    try:
        return importlib.import_module(module)
    except ImportError:
        pkg = install_name or module
        print(f"[ERROR] Missing package '{pkg}'. Run:  pip install {pkg}")
        sys.exit(1)

yf         = _import_or_exit("yfinance")
feedparser = _import_or_exit("feedparser")
nltk       = _import_or_exit("nltk")

try:
    from fredapi import Fred as _FredCls
    _FRED_LIB = True
except ImportError:
    _FRED_LIB = False

# Download VADER lexicon once if not already present
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    print("[INFO] Downloading NLTK VADER lexicon (one-time setup)...")
    nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# ---------------------------------------------------------------------------
# Load app/.env into os.environ  (DB creds + API keys)
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).parent.parent / "app" / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetch")

# ---------------------------------------------------------------------------
# Output directory (same folder as this script: data/)
# ---------------------------------------------------------------------------
OUT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# 50-ticker universe — covers 6 GICS sectors for a large, diverse corpus
# ---------------------------------------------------------------------------
TICKERS = [
    # Technology (15)
    "AAPL", "MSFT", "NVDA", "AMD", "INTC",
    "GOOGL", "META", "NFLX", "ORCL", "CRM",
    "ADBE", "QCOM", "CSCO", "IBM", "NOW",
    # Consumer Cyclical (10)
    "AMZN", "TSLA", "EBAY", "HD", "NKE",
    "MCD", "SBUX", "F", "GM", "TGT",
    # Financial Services (8)
    "JPM", "BAC", "WFC", "V", "MA",
    "GS", "MS", "AXP",
    # Healthcare (7)
    "PFE", "JNJ", "MRK", "ABBV", "UNH", "LLY", "AMGN",
    # Energy (5)
    "XOM", "CVX", "COP", "SLB", "PSX",
    # Communication / Other (5)
    "DIS", "T", "VZ", "CMCSA", "SONY",
]

# ---------------------------------------------------------------------------
# yfinance exchange code → schema CHECK constraint values
# ---------------------------------------------------------------------------
EXCHANGE_MAP = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NAS": "NASDAQ",
    "NYQ": "NYSE",   "NYS": "NYSE",
    "ASE": "AMEX",
    "PNK": "OTC",    "OBB": "OTC",    "OTC": "OTC",
    "LSE": "LSE",
}

# ---------------------------------------------------------------------------
# yfinance "To Grade" strings → schema CHECK constraint vocabulary
# ---------------------------------------------------------------------------
RATING_MAP = {
    "strong buy":          "Buy",
    "buy":                 "Buy",
    "add":                 "Buy",
    "accumulate":          "Buy",
    "positive":            "Buy",
    "outperform":          "Outperform",
    "market outperform":   "Outperform",
    "sector outperform":   "Outperform",
    "overperform":         "Outperform",
    "outperformer":        "Outperform",
    "overweight":          "Overweight",
    "hold":                "Hold",
    "long-term buy":       "Hold",
    "neutral":             "Neutral",
    "equal-weight":        "Neutral",
    "equal weight":        "Neutral",
    "in-line":             "Neutral",
    "peer perform":        "Neutral",
    "mixed":               "Neutral",
    "market perform":      "Market Perform",
    "sector perform":      "Market Perform",
    "perform":             "Market Perform",
    "underweight":         "Underweight",
    "underperform":        "Underperform",
    "sector underperform": "Underperform",
    "sell":                "Sell",
    "strong sell":         "Sell",
    "reduce":              "Sell",
    "negative":            "Sell",
}

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "").strip()

# FRED series to fetch: series_id → (human label, unit)
FRED_SERIES = {
    "FEDFUNDS":          ("Federal Funds Effective Rate",                    "Percent"),
    "CPIAUCSL":          ("Consumer Price Index for All Urban Consumers",    "Index 1982-84=100"),
    "UNRATE":            ("Unemployment Rate",                               "Percent"),
    "GS10":              ("10-Year Treasury Constant Maturity Rate",         "Percent"),
    "A191RL1Q225SBEA":   ("Real Gross Domestic Product Growth Rate",         "Percent"),
    "DEXUSEU":           ("US Dollar / Euro Foreign Exchange Rate",          "USD per EUR"),
    "DCOILWTICO":        ("Crude Oil Prices: West Texas Intermediate (WTI)", "Dollars per Barrel"),
    "VIXCLS":            ("CBOE Volatility Index (VIX)",                    "Index"),
}

VADER = SentimentIntensityAnalyzer()

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

def clean_text(raw):
    """Strip HTML tags and collapse whitespace."""
    text = _HTML_TAG.sub(" ", raw or "")
    return _WHITESPACE.sub(" ", text).strip()


def vader_score(title, body=""):
    """VADER compound sentiment, clamped to [-1, 1], rounded to 3 dp."""
    raw = VADER.polarity_scores(f"{title} {body}")["compound"]
    return round(max(-1.0, min(1.0, raw)), 3)


def norm_exchange(raw):
    return EXCHANGE_MAP.get(str(raw or "").upper(), "OTHER")


def norm_rating(raw):
    """Return normalised rating string or None if unrecognised."""
    return RATING_MAP.get(str(raw or "").lower().strip())


def write_csv(filename, fieldnames, rows):
    path = OUT_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"  wrote {filename:<42}  {len(rows):>6} rows")


# ===========================================================================
# 1. COMPANY INFO + SECTORS  (yfinance Ticker.info)
# ===========================================================================
def fetch_companies():
    """Return (sector_rows, company_rows, ticker_to_company_id)."""
    sectors_seen = {}   # (sector_name, industry_name) -> sector_id
    sector_rows  = []
    company_rows = []
    ticker_to_id = {}
    cid = 0

    log.info(f"[1/5] Fetching company info for {len(TICKERS)} tickers via yfinance...")

    for tkr in TICKERS:
        try:
            info = yf.Ticker(tkr).info

            # Sector / industry — default to "Other" when yfinance omits them
            sector   = clean_text(info.get("sector")   or "Other")[:100]
            industry = clean_text(info.get("industry") or "Other")[:150]
            key = (sector, industry)
            if key not in sectors_seen:
                sectors_seen[key] = len(sectors_seen) + 1
                sector_rows.append({
                    "sector_id":     sectors_seen[key],
                    "sector_name":   sector,
                    "industry_name": industry,
                })

            name  = clean_text(info.get("longName") or info.get("shortName") or tkr)[:200]
            exch  = norm_exchange(info.get("exchange"))
            cap   = info.get("marketCap")

            cid += 1
            ticker_to_id[tkr] = cid
            company_rows.append({
                "company_id":     cid,
                "ticker":         tkr,
                "name":           name,
                "sector_id":      sectors_seen[key],
                "exchange":       exch,
                "market_cap_usd": round(float(cap), 2) if cap else "",
            })
            log.info(f"    {tkr:<6}  {name[:40]:<40}  {exch}  cap={'${:,.0f}'.format(cap) if cap else 'N/A'}")

        except Exception as exc:
            log.warning(f"    {tkr}: {exc} — skipped")

        time.sleep(0.5)     # be polite to yfinance

    log.info(f"  → {len(company_rows)} companies, {len(sector_rows)} sectors")
    return sector_rows, company_rows, ticker_to_id


# ===========================================================================
# 2. STOCK PRICES  (yfinance Ticker.history, 2-year daily OHLCV)
# ===========================================================================
def fetch_prices(ticker_to_id):
    """Return price_rows list."""
    price_rows = []
    log.info(f"[2/5] Fetching 2-year daily price history for {len(ticker_to_id)} tickers...")

    for tkr, cid in ticker_to_id.items():
        try:
            df = yf.Ticker(tkr).history(period="2y", auto_adjust=True)
            if df is None or df.empty:
                log.warning(f"    {tkr}: empty history")
                continue

            for dt_idx, row in df.iterrows():
                # dt_idx is a pandas Timestamp
                trade_date = dt_idx.date().isoformat()
                o = float(row["Open"])
                h = float(row["High"])
                l = float(row["Low"])
                c = float(row["Close"])
                v = int(row["Volume"])

                # Skip rows with non-positive prices (data quality guard)
                if o <= 0 or h <= 0 or l <= 0 or c <= 0 or h < l:
                    continue

                price_rows.append({
                    "company_id":    cid,
                    "trade_date":    trade_date,
                    "open_price":    round(o, 4),
                    "high_price":    round(h, 4),
                    "low_price":     round(l, 4),
                    "close_price":   round(c, 4),
                    "volume":        v,
                    "adjusted_close": round(c, 4),  # auto_adjust=True means Close is already adjusted
                })

            log.info(f"    {tkr:<6}  {len(df)} trading days")

        except Exception as exc:
            log.warning(f"    {tkr}: {exc}")

        time.sleep(0.3)

    log.info(f"  → {len(price_rows)} price rows")
    return price_rows


# ===========================================================================
# 3. ANALYST RATINGS  (yfinance Ticker.upgrades_downgrades)
# Note: Ticker.recommendations was deprecated in yfinance 0.2.x.
#       upgrades_downgrades has columns: GradeDate (index), Firm, ToGrade,
#       FromGrade, Action — and covers several years of history.
# ===========================================================================
def fetch_ratings(ticker_to_id):
    """Return rating_rows list."""
    rating_rows = []
    seen        = set()     # (company_id, firm, date) dedup key
    rid         = 0

    log.info(f"[3/5] Fetching analyst upgrades/downgrades for {len(ticker_to_id)} tickers...")

    for tkr, cid in ticker_to_id.items():
        try:
            ticker_obj = yf.Ticker(tkr)

            # Primary: upgrades_downgrades (current yfinance API)
            df = ticker_obj.upgrades_downgrades
            if df is None or df.empty:
                # Fallback: legacy recommendations attribute
                df = ticker_obj.recommendations
            if df is None or df.empty:
                log.info(f"    {tkr}: no rating data")
                continue

            count_before = len(rating_rows)
            for dt_idx, row in df.iterrows():
                # Column name varies between yfinance versions
                raw = str(
                    row.get("ToGrade") or row.get("To Grade") or
                    row.get("toGrade") or ""
                )
                normalised = norm_rating(raw)
                if not normalised:
                    continue    # unmapped grade — skip rather than violate CHECK

                if hasattr(dt_idx, "date"):
                    rdate = dt_idx.date().isoformat()
                elif hasattr(dt_idx, "strftime"):
                    rdate = dt_idx.strftime("%Y-%m-%d")
                else:
                    rdate = str(dt_idx)[:10]

                firm = clean_text(str(row.get("Firm") or row.get("firm") or "Unknown"))[:150]
                key  = (cid, firm, rdate)
                if key in seen:
                    continue
                seen.add(key)
                rid += 1
                rating_rows.append({
                    "rating_id":        rid,
                    "company_id":       cid,
                    "analyst_firm":     firm,
                    "rating":           normalised,
                    "target_price_usd": "",   # yfinance does not supply per-firm targets
                    "rating_date":      rdate,
                })

            added = len(rating_rows) - count_before
            log.info(f"    {tkr:<6}  {added} ratings")

        except Exception as exc:
            log.warning(f"    {tkr}: {exc}")

        time.sleep(0.3)

    log.info(f"  → {len(rating_rows)} rating rows")
    return rating_rows


# ===========================================================================
# 4. NEWS ARTICLES
#    Sources (in priority order):
#      a) Yahoo Finance RSS   — per-ticker feed, no key, always available
#      b) Google News RSS     — broad coverage, no key, always available
#      c) NewsAPI.org         — 100 req/day free tier; set NEWSAPI_KEY in .env
# ===========================================================================
QUERY_VARIANTS = [
    "{ticker}",
    "{ticker} stock earnings",
    "{ticker} analyst forecast",
    "{name} stock",
]

FEEDPARSER_AGENT = "Mozilla/5.0 (compatible; MarketPulse-RAG/1.0)"


def _rss_entries(feed_url):
    try:
        parsed = feedparser.parse(feed_url, agent=FEEDPARSER_AGENT)
        return parsed.entries or [], ("yahoo" in feed_url.lower())
    except Exception as exc:
        log.debug(f"    RSS error {feed_url[:70]}: {exc}")
        return [], False


def _newsapi_articles(query, api_key, page_size=100):
    """Fetch from NewsAPI.org /v2/everything. Returns list of article dicts."""
    if not api_key:
        return []
    try:
        import urllib.request
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={url_quote(query)}&language=en&sortBy=publishedAt"
            f"&pageSize={page_size}&apiKey={api_key}"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("articles", [])
    except Exception as exc:
        log.debug(f"    NewsAPI error ({query}): {exc}")
        return []


def fetch_news(ticker_to_id, company_rows):
    """Return (article_rows, ac_rows)."""
    article_rows = []
    ac_rows      = []
    url_to_aid   = {}   # url -> article_id  (enables cross-company linking)
    ac_seen      = set()
    aid          = 0

    name_map = {r["company_id"]: r["name"] for r in company_rows}
    newsapi_calls = 0   # track free-tier usage (100/day)

    log.info("[4/5] Fetching news (Yahoo Finance RSS + Google News RSS + NewsAPI)...")

    for tkr, cid in ticker_to_id.items():
        name  = name_map.get(cid, tkr)
        added = 0

        for variant in QUERY_VARIANTS:
            q   = variant.format(ticker=tkr, name=name)
            q_e = url_quote(q)

            # --- RSS sources (no key) ---
            rss_feeds = [
                (f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={tkr}&region=US&lang=en-US",
                 "Yahoo Finance RSS"),
                (f"https://news.google.com/rss/search?q={q_e}&hl=en-US&gl=US&ceid=US:en",
                 "Google News RSS"),
            ]

            for feed_url, source_label in rss_feeds:
                entries, _ = _rss_entries(feed_url)
                for entry in entries:
                    url = clean_text(str(getattr(entry, "link", "") or ""))[:2048]
                    if not url:
                        continue
                    title   = clean_text(getattr(entry, "title",       "") or "")
                    summary = clean_text(getattr(entry, "summary",     "") or
                                         getattr(entry, "description", "") or "")
                    content = summary or title
                    if not title or not content:
                        continue

                    pub = getattr(entry, "published_parsed", None)
                    if pub:
                        try:
                            published_at = datetime(*pub[:6], tzinfo=timezone.utc).isoformat()
                        except Exception:
                            published_at = datetime.now(timezone.utc).isoformat()
                    else:
                        published_at = datetime.now(timezone.utc).isoformat()

                    if url in url_to_aid:
                        ac_key = (url_to_aid[url], cid)
                        if ac_key not in ac_seen:
                            ac_seen.add(ac_key)
                            ac_rows.append({"article_id": url_to_aid[url], "company_id": cid})
                            added += 1
                    else:
                        aid += 1
                        url_to_aid[url] = aid
                        article_rows.append({
                            "article_id":      aid,
                            "title":           title[:1000],
                            "content":         content[:4000],
                            "url":             url,
                            "published_at":    published_at,
                            "source":          source_label,
                            "sentiment_score": vader_score(title, content),
                            "embedding":       "",
                        })
                        ac_seen.add((aid, cid))
                        ac_rows.append({"article_id": aid, "company_id": cid})
                        added += 1

                time.sleep(0.15)

            # --- NewsAPI.org (optional, requires key) ---
            if NEWSAPI_KEY and newsapi_calls < 95:   # leave headroom in 100/day limit
                for art in _newsapi_articles(q, NEWSAPI_KEY, page_size=20):
                    newsapi_calls += 1
                    url  = clean_text(str(art.get("url") or ""))[:2048]
                    if not url:
                        continue
                    title   = clean_text(art.get("title")       or "")
                    content = clean_text(art.get("description") or art.get("content") or title)
                    if not title or not content:
                        continue
                    pub_str = art.get("publishedAt") or ""
                    try:
                        published_at = datetime.fromisoformat(
                            pub_str.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        published_at = datetime.now(timezone.utc).isoformat()

                    if url in url_to_aid:
                        ac_key = (url_to_aid[url], cid)
                        if ac_key not in ac_seen:
                            ac_seen.add(ac_key)
                            ac_rows.append({"article_id": url_to_aid[url], "company_id": cid})
                            added += 1
                    else:
                        aid += 1
                        url_to_aid[url] = aid
                        article_rows.append({
                            "article_id":      aid,
                            "title":           title[:1000],
                            "content":         content[:4000],
                            "url":             url,
                            "published_at":    published_at,
                            "source":          "NewsAPI.org",
                            "sentiment_score": vader_score(title, content),
                            "embedding":       "",
                        })
                        ac_seen.add((aid, cid))
                        ac_rows.append({"article_id": aid, "company_id": cid})
                        added += 1
                time.sleep(0.1)

        log.info(f"    {tkr:<6}  {added} article-company links")

    log.info(f"  → {len(article_rows)} unique articles, {len(ac_rows)} article-company links")
    if NEWSAPI_KEY:
        log.info(f"     NewsAPI calls used: {newsapi_calls}/100")
    return article_rows, ac_rows


# ===========================================================================
# 5. ECONOMIC INDICATORS  (FRED via fredapi)
# ===========================================================================
def fetch_fred():
    """Return indicator_rows list. Requires FRED_API_KEY in app/.env."""
    if not _FRED_LIB:
        log.warning("[5/5] fredapi not installed — skipping FRED. "
                    "Install with: pip install fredapi")
        return []

    fred_key = os.environ.get("FRED_API_KEY", "").strip()
    if not fred_key:
        log.warning("[5/5] FRED_API_KEY not set in app/.env — skipping FRED indicators. "
                    "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html")
        return []

    try:
        fred = _FredCls(api_key=fred_key)
    except Exception as exc:
        log.warning(f"[5/5] FRED init failed: {exc}")
        return []

    rows  = []
    ind_id = 0
    log.info(f"[5/5] Fetching {len(FRED_SERIES)} FRED series (2022-01-01 → present)...")

    for series_id, (label, unit) in FRED_SERIES.items():
        try:
            series = fred.get_series(series_id, observation_start="2022-01-01")
            series = series.dropna()
            for dt, val in series.items():
                rdate = str(dt)[:10]
                ind_id += 1
                rows.append({
                    "indicator_id":   ind_id,
                    "indicator_name": label,
                    "value":          round(float(val), 6),
                    "recorded_date":  rdate,
                    "source":         "FRED",
                    "unit":           unit,
                })
            log.info(f"    {series_id:<22}  {len(series)} observations")
        except Exception as exc:
            log.warning(f"    {series_id}: {exc}")
        time.sleep(0.2)

    log.info(f"  → {len(rows)} indicator rows")
    return rows


# ===========================================================================
# Main
# ===========================================================================
def main():
    t0 = time.time()
    log.info("=" * 60)
    log.info("MarketPulse Real Data Fetcher")
    log.info(f"Tickers: {len(TICKERS)}  |  Output: {OUT_DIR}")
    log.info("=" * 60)

    sector_rows, company_rows, ticker_to_id = fetch_companies()

    if not company_rows:
        log.error("No companies fetched — check your network connection and try again.")
        sys.exit(1)

    price_rows     = fetch_prices(ticker_to_id)
    rating_rows    = fetch_ratings(ticker_to_id)
    article_rows, ac_rows = fetch_news(ticker_to_id, company_rows)
    indicator_rows = fetch_fred()

    # ------------------------------------------------------------------
    # Write CSVs  — same filenames and column order as generate_data.py
    # import_data.sql requires this exact format.
    # ------------------------------------------------------------------
    log.info("Writing CSVs...")
    write_csv("sectors.csv",
              ["sector_id", "sector_name", "industry_name"],
              sector_rows)

    write_csv("companies.csv",
              ["company_id", "ticker", "name", "sector_id", "exchange", "market_cap_usd"],
              company_rows)

    write_csv("stock_prices.csv",
              ["company_id", "trade_date", "open_price", "high_price",
               "low_price", "close_price", "volume", "adjusted_close"],
              price_rows)

    write_csv("news_articles.csv",
              ["article_id", "title", "content", "url", "published_at",
               "source", "sentiment_score", "embedding"],
              article_rows)

    write_csv("article_company.csv",
              ["article_id", "company_id"],
              ac_rows)

    write_csv("analyst_ratings.csv",
              ["rating_id", "company_id", "analyst_firm", "rating",
               "target_price_usd", "rating_date"],
              rating_rows)

    write_csv("economic_indicators.csv",
              ["indicator_id", "indicator_name", "value",
               "recorded_date", "source", "unit"],
              indicator_rows)

    # Combined data.csv  (satisfies M2 "data.csv or data.json" deliverable)
    combined = []
    for tname, rlist in [
        ("sectors",             sector_rows),
        ("companies",           company_rows),
        ("stock_prices",        price_rows),
        ("news_articles",       article_rows),
        ("article_company",     ac_rows),
        ("analyst_ratings",     rating_rows),
        ("economic_indicators", indicator_rows),
    ]:
        for r in rlist:
            combined.append({
                "table_name":  tname,
                "record_json": json.dumps(r, separators=(",", ":"), ensure_ascii=False),
            })
    write_csv("data.csv", ["table_name", "record_json"], combined)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = sum(map(len, [sector_rows, company_rows, price_rows,
                          article_rows, ac_rows, rating_rows, indicator_rows]))
    elapsed = time.time() - t0

    log.info("")
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    log.info(f"  sectors              : {len(sector_rows):>6}")
    log.info(f"  companies            : {len(company_rows):>6}  (of {len(TICKERS)} requested)")
    log.info(f"  stock_prices         : {len(price_rows):>6}")
    log.info(f"  news_articles        : {len(article_rows):>6}")
    log.info(f"  article_company      : {len(ac_rows):>6}")
    log.info(f"  analyst_ratings      : {len(rating_rows):>6}")
    log.info(f"  economic_indicators  : {len(indicator_rows):>6}")
    log.info(f"  TOTAL ROWS           : {total:>6}")
    log.info(f"  Elapsed              : {elapsed:.0f}s")
    log.info("")
    log.info("Next step — load into PostgreSQL:")
    log.info("  psql -U <user> -d marketpulse -f schema/schema.sql")
    log.info("  psql -U <user> -d marketpulse -f data/import_data.sql")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
