import subprocess
import time

def run_test_case(query, ticker=None):
    print(f"\n>> RUNNING TEST CASE: '{query}'")
    cmd = ["python", "-m", "app.main", query]
    if ticker:
        cmd.extend(["--ticker", ticker])
    
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    end = time.time()
    
    print(result.stdout)
    if result.stderr:
        print("ERRORS:", result.stderr)
    print(f"Time taken: {end - start:.2f} seconds")
    print("-" * 80)

if __name__ == "__main__":
    print("MARKETPULSE - FINAL SUBMISSION TEST CASES\n")
    
    # Test Case 1: Specific Company Event Analysis
    run_test_case("What caused AAPL stock price to move recently? Summarize the news sentiment.", "AAPL")
    
    # Test Case 2: Analyst Rating Impact
    run_test_case("What are the most recent analyst ratings for NVDA and what is their target price?", "NVDA")
    
    # Test Case 3: Macroeconomic Context
    run_test_case("How might the current Federal Funds Rate and CPI affect the Technology sector?")
