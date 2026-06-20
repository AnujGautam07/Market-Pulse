import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'marketpulse'),
        user=os.getenv('DB_USER', ''),
        password=os.getenv('DB_PASSWORD', '')
    )

def find_company(query_text):
    """Finds a company by ticker or name approximation."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Try exact ticker match first
            cur.execute("SELECT company_id, ticker, name FROM companies WHERE ticker = %s", (query_text.upper(),))
            res = cur.fetchone()
            if res:
                return res
            
            # Try ILIKE name match
            cur.execute("SELECT company_id, ticker, name FROM companies WHERE name ILIKE %s", (f"%{query_text}%",))
            res = cur.fetchone()
            if res:
                return res
    finally:
        conn.close()
    return None

def get_similar_news(embedding_vector, limit=5, company_id=None):
    """Retrieves news articles similar to the query embedding."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Convert embedding list to pgvector string format
            embedding_str = "[" + ",".join(map(str, embedding_vector)) + "]"
            
            if company_id:
                # If company is known, prioritize news about this company or highly similar general news
                query = """
                    SELECT n.title, n.content, n.published_at, n.source, n.sentiment_score,
                           (n.embedding <#> %s) as distance
                    FROM news_articles n
                    JOIN article_company ac ON n.article_id = ac.article_id
                    WHERE ac.company_id = %s AND n.embedding IS NOT NULL
                    ORDER BY n.embedding <#> %s
                    LIMIT %s;
                """
                cur.execute(query, (embedding_str, company_id, embedding_str, limit))
            else:
                query = """
                    SELECT title, content, published_at, source, sentiment_score,
                           (embedding <#> %s) as distance
                    FROM news_articles
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <#> %s
                    LIMIT %s;
                """
                cur.execute(query, (embedding_str, embedding_str, limit))
            return cur.fetchall()
    finally:
        conn.close()

def get_recent_prices(company_id, limit=5):
    """Fetches the most recent stock prices for a company."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT trade_date, open_price, close_price, volume, adjusted_close
                FROM stock_prices
                WHERE company_id = %s
                ORDER BY trade_date DESC
                LIMIT %s;
            """
            cur.execute(query, (company_id, limit))
            return cur.fetchall()
    finally:
        conn.close()

def get_analyst_ratings(company_id, limit=3):
    """Fetches recent analyst ratings for a company."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT analyst_firm, rating, target_price_usd, rating_date
                FROM analyst_ratings
                WHERE company_id = %s
                ORDER BY rating_date DESC
                LIMIT %s;
            """
            cur.execute(query, (company_id, limit))
            return cur.fetchall()
    finally:
        conn.close()

def get_recent_economic_indicators():
    """Fetches the most recent macroeconomic data."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT indicator_name, value, unit, recorded_date
                FROM (
                    SELECT indicator_name, value, unit, recorded_date,
                           ROW_NUMBER() OVER(PARTITION BY indicator_name ORDER BY recorded_date DESC) as rn
                    FROM economic_indicators
                ) sub
                WHERE rn = 1;
            """
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()
