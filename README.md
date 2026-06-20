# Market-Pulse
AI-powered fintech platform that analyzes stock market movements using financial news, real-time market data, and RAG-based semantic search.

Link - https://github.com/AnujGautam07/Market-Pulse.git

---
## Final Submission Requirements

Z2004 Database Management Systems · IIT Madras Zanzibar · Track A (RAG Pipeline)
Team: Nidheesh Deepu Nair (ZDA24B013) · Anuj Gautam (ZDA24B033) · Shreyash Kumar Pandey (ZDA24B004)

MarketPulse is a finance-domain RAG pipeline that explains why stock prices move by linking structured market data (prices, ratings, macro indicators) with news articles.

### 1. Repository Structure
```
marketpulse/
├── schema/
│   ├── schema.sql              # DDL (7 tables, 3NF) with pgvector extension
│   └── ER-diagram.pdf          # Entity-Relationship diagram
├── data/
│   ├── data.csv                # combined long-format dataset
│   ├── generate_data.py        # dataset simulator (deterministic, seeded)
│   ├── import_data.sql         # loads every CSV into the schema
│   └── *.csv                   # other CSV data files
├── queries/
│   ├── queries.sql             # 14 labelled queries demonstrating SQL features
│   ├── performance.sql         # Query optimization and EXPLAIN ANALYZE notes
│   └── verify.sql              # Optional integrity / row-count checks
├── app/
│   ├── db.py                   # PostgreSQL connection & querying functions
│   ├── rag.py                  # Embedding logic & LLM connection
│   ├── main.py                 # CLI entry point to ask questions
│   ├── embed_news.py           # Script to populate pgvector embeddings
│   ├── test_cases.py           # Runs the 3 core test cases
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Template for DB and API keys
├── report/
│   ├── MarketPulse_Milestone3_Report.pdf
│   └── 3NF,justification_notes.pdf
├── demo/                       # 5-minute screen-recorded demo video
└── README.md                   # Setup and run instructions
```

---
### 2. Prerequisites
* **PostgreSQL 14+** (tested on 16) with `psql` in `PATH`.
* **pgvector extension 0.6.0** (needed for `VECTOR(768)`).
* **Python 3.10+**.

---
### 3. Setup and Run Instructions (End-to-End)

**Step 1: Create Virtual Environment & Install Dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r app/requirements.txt
```

**Step 2: Database Setup**
```bash
createdb marketpulse
psql -d marketpulse -f schema/schema.sql
python3 data/generate_data.py
psql -d marketpulse -f data/import_data.sql
```

**Step 3: Setup Environment Variables**
Copy the `.env.example` to `.env` and fill in your Gemini API key (optional, fallback mode will trigger if omitted) and PostgreSQL credentials.
```bash
cp app/.env.example app/.env
```
*Note: Make sure to never commit `.env` to Git!*

**Step 4: Populate Embeddings**
```bash
python3 -m app.embed_news
```
*This uses `sentence-transformers` (`all-mpnet-base-v2`) to generate 768-dimensional vectors for all news articles in the database so that `pgvector` HNSW indexes can perform fast semantic searches.*

**Step 5: Run the App / Test Cases**
To run the 3 core test cases:
```bash
python3 -m app.test_cases
```

To run a custom query:
```bash
python3 -m app.main "Why did AAPL drop recently?" --ticker AAPL
```

---
### 4. Schema, Indexing & AI Components

* **Schema**: 3NF normalized schema with 7 tables (`companies`, `sectors`, `stock_prices`, `news_articles`, `article_company`, `analyst_ratings`, `economic_indicators`).
* **Indexing**: B-Tree indexes heavily used for high-frequency lookup columns (`trade_date`, `company_id`). The `news_articles` table utilizes a **pgvector HNSW index** for approximate nearest-neighbour cosine similarity searches.
* **AI Components**:
  * **Embeddings**: Uses `sentence-transformers` (`all-mpnet-base-v2`) locally to embed news text.
  * **LLM**: Integrates with the Gemini 1.5 Flash API (`google-generativeai`) to synthesize answers from the DB-retrieved context.

---
### 5. Fallback Plan (Network/API Down)
If the LLM API is down, unavailable, or the `GEMINI_API_KEY` is not provided, the application automatically enters **Fallback Mode**. In this mode, the application will still perform the `pgvector` semantic search and standard SQL queries, returning the raw structured context directly to the user. This guarantees that sample inputs (queries) will always yield expected outputs (relevant data records).

---
### 6. AI Usage Disclosure
Per the Z2004 AI Tools Policy:
* **Tool**: Claude (Anthropic), ChatGPT (OpenAI), and Gemini (Google).
* **Used for**: Brainstorming the dataset simulator structure, geometric Brownian motion drafting, SQL query suggestions, and developing the RAG pipeline integration code (embedding logic and LLM prompt design).
* **What we changed/verified**: We set all parameters, enforced schema compliance, verified SQL query logic manually via EXPLAIN ANALYZE, and tested the fallback mechanisms ourselves to ensure system robustness.
