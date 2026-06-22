import os
import time
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()

# Initialize the embedding model globally
try:
    print("Loading embedding model (all-mpnet-base-v2)...")
    embedding_model = SentenceTransformer('all-mpnet-base-v2')
except Exception as e:
    print(f"Warning: Could not load sentence-transformers: {e}")
    embedding_model = None

# Configure Gemini
# Model preference order: try the most current widely-available models first.
# `gemini-1.5-*` was retired from v1beta in early 2026 — use 2.5/2.0 family instead.
GENERATION_MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]

api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)
    generation_model = genai.GenerativeModel(GENERATION_MODEL_CANDIDATES[0])
else:
    generation_model = None
    print("Warning: GEMINI_API_KEY is not set. The app will run in fallback mode (returning raw context).")

def generate_embedding(text):
    """Generates a 768-dimensional embedding for the input text."""
    if not embedding_model:
        return [0.0] * 768
    return embedding_model.encode(text).tolist()

def generate_answer(query, context):
    """Uses the LLM to generate an answer based on the provided context. Includes a fallback."""
    if not generation_model:
        return _fallback_answer(query, context, "LLM is not configured (missing API key).")
    
    prompt = f"""You are a senior financial analyst for the MarketPulse intelligence platform.

Answer the user's question using ONLY the data provided in the context below.
Be detailed, explanatory and educational. Explain the WHY behind every number you cite.

FORMAT YOUR RESPONSE USING EXACTLY THESE MARKDOWN SECTIONS:

## Summary
A 2 to 3 sentence executive overview that directly answers the question.

## Key Findings
1. First key finding with a specific data point cited inline as (Source: [1]) or (Prices, date) or (FRED: indicator).
2. Second key finding with inline citation.
3. Further findings as the data warrants.

## Market Analysis
Detailed discussion of price trends, volumes, and patterns. Reference specific dates and dollar values from the context.

## Analyst Perspective
What the analyst ratings reveal about market sentiment and institutional view. If no analyst data is available, state that.

## Macroeconomic Context
How the FRED indicators (interest rates, inflation, GDP, VIX, oil, etc.) relate to the question and the company.

## Sources
List every article and data source referenced:
[1] Article title - source name - date
[2] Article title - source name - date
(Also include: Stock price data from yfinance, Analyst ratings from yfinance upgrades/downgrades, Macro data from FRED.)

RULES:
- Cite inline using the format: (Source: [1]) for articles, (Prices, date) for price data, (FRED: indicator name) for macro.
- Do not use em dashes. Use commas or colons instead.
- Do not use emojis.
- Do not leave any section blank. If data is missing, write "No data available for this section."
- Be specific: quote actual numbers, dates, company names, and analyst firm names from the context.

Context:
{context}

Question: {query}
"""
    last_error = None
    for model_name in GENERATION_MODEL_CANDIDATES:
        for attempt in range(3):
            try:
                llm = genai.GenerativeModel(model_name)
                response = llm.generate_content(prompt)
                return response.text
            except Exception as e:
                last_error = e
                msg = str(e).lower()
                if "404" in msg or "not found" in msg or "not supported" in msg:
                    break  # model unavailable — try next candidate
                if "429" in msg or "quota" in msg or "resource exhausted" in msg or "rate" in msg:
                    if attempt < 2:
                        wait = 20 * (2 ** attempt)  # 20s, 40s
                        time.sleep(wait)
                        continue  # retry same model after back-off
                    break  # exhausted retries — try next model candidate
                return _fallback_answer(query, context, f"LLM API request failed: {e}")
    return _fallback_answer(query, context, f"LLM API request failed: {last_error}")

def _fallback_answer(query, context, reason):
    """Fallback method when the LLM is unavailable."""
    fallback_msg = (
        f"--- FALLBACK MODE ACTIVE ---\n"
        f"Reason: {reason}\n"
        f"Below is the raw retrieved context for your query:\n"
        f"-----------------------------\n\n"
        f"{context}"
    )
    return fallback_msg
