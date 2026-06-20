import argparse
from app.db import find_company, get_similar_news, get_recent_prices, get_analyst_ratings, get_recent_economic_indicators
from app.rag import generate_embedding, generate_answer

def main():
    parser = argparse.ArgumentParser(description="MarketPulse RAG CLI")
    parser.add_argument("query", type=str, help="The question to ask about the market.")
    parser.add_argument("--ticker", type=str, help="Optional ticker to focus the search on (e.g. AAPL).", default=None)
    args = parser.parse_args()

    query = args.query
    ticker = args.ticker

    print(f"Analyzing query: '{query}'...")
    
    company_id = None
    company_info = None

    # Identify company context if provided or implied
    if ticker:
        company_info = find_company(ticker)
    else:
        # A simple heuristic: check if any uppercase word is a known ticker
        words = query.replace("?", "").replace(",", "").split()
        for word in words:
            if word.isupper() and len(word) <= 5:
                res = find_company(word)
                if res:
                    company_info = res
                    break

    if company_info:
        company_id = company_info['company_id']
        print(f"Detected company focus: {company_info['name']} ({company_info['ticker']})")

    # 1. Generate Query Embedding
    print("Generating embedding for semantic search...")
    query_embedding = generate_embedding(query)

    # 2. Retrieve Context from Database
    print("Retrieving relevant data from PostgreSQL...")
    
    news = get_similar_news(query_embedding, limit=3, company_id=company_id)
    macro = get_recent_economic_indicators()
    
    prices = []
    ratings = []
    if company_id:
        prices = get_recent_prices(company_id, limit=5)
        ratings = get_analyst_ratings(company_id, limit=3)

    # Build Context String
    context = ""
    if company_info:
        context += f"Company: {company_info['name']} ({company_info['ticker']})\n"
    
    if prices:
        context += "\nRecent Stock Prices (Close):\n"
        for p in prices:
            context += f"- {p['trade_date']}: ${p['close_price']} (Vol: {p['volume']})\n"
    
    if ratings:
        context += "\nRecent Analyst Ratings:\n"
        for r in ratings:
            context += f"- {r['rating_date']} | {r['analyst_firm']}: {r['rating']} (Target: ${r['target_price_usd'] or 'N/A'})\n"
            
    if news:
        context += "\nRelevant News Articles:\n"
        for n in news:
            context += f"- [{n['published_at'].date()}] {n['title']} (Sentiment: {n['sentiment_score']})\n  {n['content']}\n"
            
    context += "\nRecent Macroeconomic Indicators:\n"
    for m in macro:
        context += f"- {m['indicator_name']}: {m['value']} {m['unit']} ({m['recorded_date']})\n"

    # 3. Generate Answer
    print("\nGenerating AI response...\n")
    print("="*60)
    answer = generate_answer(query, context)
    print(answer)
    print("="*60)

if __name__ == "__main__":
    main()
