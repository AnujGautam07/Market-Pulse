"""MarketPulse RAG pipeline test suite.

Runs end-to-end and component-level checks against the live database and Gemini
API. Each test prints a pass/fail line; a final summary lists failures and exits
non-zero if any test failed so CI can pick it up.

Usage (run from the Market-Pulse/ project root):
    PYTHONPATH=. venv/bin/python3 app/test_cases.py            # run everything
    PYTHONPATH=. venv/bin/python3 app/test_cases.py --quick    # skip slow E2E tests
"""

import argparse
import os
import re
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from app.db import (
    find_company,
    get_analyst_ratings,
    get_recent_economic_indicators,
    get_recent_prices,
    get_similar_news,
    get_db_connection,
)
from app.rag import (
    GENERATION_MODEL_CANDIDATES,
    embedding_model,
    generate_answer,
    generate_embedding,
    generation_model,
)


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


class TestRunner:
    def __init__(self):
        self.results = []

    def run(self, name, fn):
        print(f"\n{BOLD}>> {name}{RESET}")
        start = time.time()
        try:
            fn()
            elapsed = time.time() - start
            print(f"{GREEN}   PASS{RESET} ({elapsed:.2f}s)")
            self.results.append((name, True, None))
        except AssertionError as e:
            elapsed = time.time() - start
            print(f"{RED}   FAIL{RESET} ({elapsed:.2f}s): {e}")
            self.results.append((name, False, str(e)))
        except Exception as e:
            elapsed = time.time() - start
            print(f"{RED}   ERROR{RESET} ({elapsed:.2f}s): {type(e).__name__}: {e}")
            self.results.append((name, False, f"{type(e).__name__}: {e}"))

    def summary(self):
        total = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = total - passed
        print(f"\n{BOLD}{'=' * 70}{RESET}")
        print(f"{BOLD}SUMMARY:{RESET} {passed}/{total} passed, {failed} failed")
        if failed:
            print(f"\n{RED}Failed tests:{RESET}")
            for name, ok, err in self.results:
                if not ok:
                    print(f"  - {name}: {err}")
        print(f"{BOLD}{'=' * 70}{RESET}")
        return failed == 0


# --- Component tests --------------------------------------------------------


def test_db_connection():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1, "DB did not return expected value"
    finally:
        conn.close()


def test_pgvector_extension():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            assert cur.fetchone() is not None, "pgvector extension not installed"
    finally:
        conn.close()


def test_expected_tables_exist():
    expected = {
        "companies",
        "stock_prices",
        "news_articles",
        "article_company",
        "analyst_ratings",
        "economic_indicators",
        "sectors",
    }
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
            present = {row[0] for row in cur.fetchall()}
            missing = expected - present
            assert not missing, f"Missing tables: {missing}"
    finally:
        conn.close()


def test_tables_have_data():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for table in ["companies", "stock_prices", "news_articles", "analyst_ratings", "economic_indicators"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                assert count > 0, f"Table {table} is empty"
    finally:
        conn.close()


def test_news_embeddings_populated():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news_articles WHERE embedding IS NOT NULL")
            count = cur.fetchone()[0]
            assert count > 0, "No news articles have embeddings populated"
    finally:
        conn.close()


def test_embedding_model_loaded():
    assert embedding_model is not None, "Embedding model failed to load"


def test_generate_embedding_shape():
    vec = generate_embedding("Apple stock is rising due to strong iPhone sales")
    assert isinstance(vec, list), f"Expected list, got {type(vec)}"
    assert len(vec) == 768, f"Expected 768-dim embedding, got {len(vec)}"
    assert all(isinstance(x, float) for x in vec[:5]), "Embedding values should be floats"
    # Not all zeros (would mean fallback path)
    assert any(x != 0.0 for x in vec), "Embedding is all zeros — model not actually loaded"


def test_embedding_semantics():
    """Semantically similar sentences should produce closer embeddings than unrelated ones."""
    import numpy as np

    a = np.array(generate_embedding("Apple released a new iPhone"))
    b = np.array(generate_embedding("Apple unveils new smartphone"))
    c = np.array(generate_embedding("The Federal Reserve raised interest rates"))

    def cos(u, v):
        return float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))

    sim_ab = cos(a, b)
    sim_ac = cos(a, c)
    assert sim_ab > sim_ac, (
        f"Semantic ordering failed: cos(iPhone, smartphone)={sim_ab:.3f} "
        f"should be > cos(iPhone, Fed)={sim_ac:.3f}"
    )


def test_find_company_by_ticker():
    res = find_company("AAPL")
    assert res is not None, "find_company('AAPL') returned None"
    assert res["ticker"] == "AAPL", f"Expected ticker AAPL, got {res['ticker']}"
    assert "Apple" in res["name"], f"Expected Apple in name, got {res['name']}"


def test_find_company_unknown_returns_none():
    res = find_company("ZZZZZ_NOT_A_TICKER")
    assert res is None, f"Expected None for unknown ticker, got {res}"


def test_get_recent_prices():
    company = find_company("AAPL")
    prices = get_recent_prices(company["company_id"], limit=5)
    assert len(prices) > 0, "No prices returned for AAPL"
    assert len(prices) <= 5, f"Limit not respected: got {len(prices)} rows"
    # Sorted DESC by date
    dates = [p["trade_date"] for p in prices]
    assert dates == sorted(dates, reverse=True), "Prices not sorted DESC by trade_date"


def test_get_analyst_ratings():
    company = find_company("NVDA")
    ratings = get_analyst_ratings(company["company_id"], limit=3)
    assert len(ratings) > 0, "No ratings returned for NVDA"
    for r in ratings:
        assert r["analyst_firm"], "analyst_firm missing"
        assert r["rating"], "rating missing"


def test_get_recent_economic_indicators():
    macro = get_recent_economic_indicators()
    assert len(macro) > 0, "No macro indicators returned"
    names = {m["indicator_name"] for m in macro}
    # Should have one row per indicator (deduped by ROW_NUMBER)
    assert len(names) == len(macro), "Duplicate indicator_name rows in macro result"


def test_semantic_search_returns_relevant_news():
    vec = generate_embedding("Apple regulatory probe and lawsuit concerns")
    apple = find_company("AAPL")
    news = get_similar_news(vec, limit=3, company_id=apple["company_id"])
    assert len(news) > 0, "Semantic search returned no news for Apple"
    titles_lower = " ".join(n["title"].lower() for n in news)
    # Apple-filtered results should reference Apple/AAPL
    assert "aapl" in titles_lower or "apple" in titles_lower, (
        f"Apple-filtered search did not return Apple news. Titles: {[n['title'] for n in news]}"
    )


def test_semantic_search_distance_ordering():
    """Returned news should be ordered by ascending distance (most similar first)."""
    vec = generate_embedding("Stock market crash and economic downturn")
    news = get_similar_news(vec, limit=5, company_id=None)
    assert len(news) > 0, "Semantic search returned no news"
    distances = [n["distance"] for n in news]
    assert distances == sorted(distances), f"Distances not sorted ascending: {distances}"


# --- LLM tests --------------------------------------------------------------


def test_llm_configured():
    assert generation_model is not None, (
        "Generation model not configured — GEMINI_API_KEY missing or invalid"
    )
    assert GENERATION_MODEL_CANDIDATES, "No model candidates configured"


def test_llm_generates_grounded_answer():
    """LLM should produce a non-fallback answer when given valid context."""
    context = (
        "Company: Apple Inc. (AAPL)\n"
        "Recent Stock Prices (Close):\n"
        "- 2026-05-08: $268.50 (Vol: 10934103)\n"
        "- 2026-05-07: $268.17 (Vol: 4862477)\n"
    )
    answer = generate_answer("What was AAPL's closing price on 2026-05-08?", context)
    assert "FALLBACK MODE ACTIVE" not in answer, f"LLM fell into fallback: {answer[:200]}"
    assert "268" in answer, f"LLM did not cite the supplied price. Got: {answer[:300]}"


def test_llm_fallback_when_model_unavailable():
    """If we force a bad context the fallback formatter should still be well-formed."""
    from app.rag import _fallback_answer

    out = _fallback_answer("q", "ctx data here", "simulated failure")
    assert "FALLBACK MODE ACTIVE" in out
    assert "simulated failure" in out
    assert "ctx data here" in out


# --- End-to-end CLI tests ---------------------------------------------------


def _run_cli(query, ticker=None, timeout=120):
    # Resolve project root (one level above this file's directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_script  = os.path.join(project_root, "app", "main.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root   # ensures `from app.xxx import` resolves
    cmd = [sys.executable, main_script, query]
    if ticker:
        cmd += ["--ticker", ticker]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return result


def test_e2e_company_query():
    result = _run_cli(
        "What caused AAPL stock price to move recently? Summarize the news sentiment.",
        "AAPL",
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
    out = result.stdout
    assert "Apple Inc." in out, "Company detection (Apple) missing from output"
    assert "FALLBACK MODE ACTIVE" not in out, (
        f"E2E query fell into fallback mode:\n{out[-800:]}"
    )
    # Sanity: the answer body sits between the two ===== separators
    bars = [m.start() for m in re.finditer(r"={10,}", out)]
    assert len(bars) >= 2, "Answer separator banners missing from CLI output"
    answer = out[bars[0]:bars[1]]
    assert len(answer) > 100, f"Answer suspiciously short: {answer!r}"


def test_e2e_analyst_query():
    result = _run_cli(
        "What are the most recent analyst ratings for NVDA and what is their target price?",
        "NVDA",
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
    out = result.stdout
    assert "NVIDIA" in out, "Company detection (NVIDIA) missing from output"
    assert "FALLBACK MODE ACTIVE" not in out, (
        f"E2E analyst query fell into fallback:\n{out[-800:]}"
    )


def test_e2e_macro_query():
    result = _run_cli(
        "How might the current Federal Funds Rate and CPI affect the Technology sector?"
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
    out = result.stdout
    assert "FALLBACK MODE ACTIVE" not in out, (
        f"E2E macro query fell into fallback:\n{out[-800:]}"
    )
    # Macro context should make it into the prompt; answer should mention at
    # least one of the key indicators.
    lower = out.lower()
    assert any(k in lower for k in ["federal", "cpi", "rate", "inflation"]), (
        "Macro answer did not reference any expected indicator"
    )


# --- Main -------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip slow end-to-end CLI tests",
    )
    args = parser.parse_args()

    print(f"{BOLD}MARKETPULSE - RAG PIPELINE TEST SUITE{RESET}\n")

    runner = TestRunner()

    # Database layer
    print(f"\n{YELLOW}--- DATABASE LAYER ---{RESET}")
    runner.run("DB connection", test_db_connection)
    runner.run("pgvector extension installed", test_pgvector_extension)
    runner.run("Expected tables exist", test_expected_tables_exist)
    runner.run("Tables have data", test_tables_have_data)
    runner.run("News embeddings populated", test_news_embeddings_populated)

    # Embedding + retrieval
    print(f"\n{YELLOW}--- EMBEDDING & RETRIEVAL ---{RESET}")
    runner.run("Embedding model loaded", test_embedding_model_loaded)
    runner.run("Embedding shape (768-dim)", test_generate_embedding_shape)
    runner.run("Embedding captures semantic similarity", test_embedding_semantics)
    runner.run("find_company by ticker", test_find_company_by_ticker)
    runner.run("find_company unknown returns None", test_find_company_unknown_returns_none)
    runner.run("get_recent_prices", test_get_recent_prices)
    runner.run("get_analyst_ratings", test_get_analyst_ratings)
    runner.run("get_recent_economic_indicators", test_get_recent_economic_indicators)
    runner.run("Semantic news search relevance", test_semantic_search_returns_relevant_news)
    runner.run("Semantic news search distance ordering", test_semantic_search_distance_ordering)

    # LLM layer
    print(f"\n{YELLOW}--- LLM LAYER ---{RESET}")
    runner.run("LLM configured", test_llm_configured)
    runner.run("LLM generates grounded answer", test_llm_generates_grounded_answer)
    runner.run("LLM fallback formatter", test_llm_fallback_when_model_unavailable)

    # End-to-end CLI
    if not args.quick:
        print(f"\n{YELLOW}--- END-TO-END CLI (slow) ---{RESET}")
        runner.run("E2E company query (AAPL)", test_e2e_company_query)
        runner.run("E2E analyst query (NVDA)", test_e2e_analyst_query)
        runner.run("E2E macro query", test_e2e_macro_query)
    else:
        print(f"\n{YELLOW}--- Skipping end-to-end CLI tests (--quick) ---{RESET}")

    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
