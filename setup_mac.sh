#!/bin/bash
# One-shot setup script for macOS (Homebrew + PostgreSQL 18 + pgvector).
# Run from the Market-Pulse/ project root.

set -e

echo "========================================"
echo " MarketPulse - macOS Setup"
echo "========================================"

# 1. Homebrew check
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Install it first:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

# 2. PostgreSQL 18 + pgvector
echo "Installing PostgreSQL 18 and pgvector..."
brew install postgresql@18
brew install pgvector
brew services start postgresql@18
export PATH="/opt/homebrew/opt/postgresql@18/bin:$PATH"
sleep 3

# 3. Python venv
echo "Creating virtual environment..."
python3 -m venv venv
venv/bin/pip install --upgrade pip
PYTHONPATH=. venv/bin/pip install -r app/requirements.txt

# 4. .env file
if [ ! -f "app/.env" ]; then
    cp app/.env.example app/.env
    echo "NOTE: Edit app/.env and fill in GEMINI_API_KEY, FRED_API_KEY, NEWSAPI_KEY"
fi

# 5. Database + schema
echo "Creating database and loading schema..."
USERNAME=$(whoami)
psql -U "$USERNAME" -d postgres -c "DROP DATABASE IF EXISTS marketpulse;" || true
psql -U "$USERNAME" -d postgres -c "CREATE DATABASE marketpulse;"
psql -U "$USERNAME" -d marketpulse -f schema/schema.sql

# 6. Fetch real data (15-30 min)
echo "Fetching live market data (this takes 15-30 minutes)..."
venv/bin/python3 data/fetch_real_data.py

# 7. Import CSVs
echo "Loading CSVs into PostgreSQL..."
psql -U "$USERNAME" -d marketpulse -f data/import_data.sql

# 8. Generate embeddings
echo "Generating pgvector embeddings..."
PYTHONPATH=. venv/bin/python3 app/embed_news.py

echo "========================================"
echo "Setup complete. Run the app with:"
echo "  PYTHONPATH=. venv/bin/python3 -m streamlit run app/streamlit_app.py"
echo "  PYTHONPATH=. venv/bin/python3 app/main.py \"Why did NVDA rally?\" --ticker NVDA"
echo "========================================"
