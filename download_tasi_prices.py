import pandas as pd
import yfinance as yf
from pathlib import Path
import time
import os

BASE_DIR = Path(__file__).resolve().parent
FUNDAMENTALS = BASE_DIR / "data" / "fundamentals" / "tasi_fundamentals.csv"
PRICES_DIR = BASE_DIR / "data" / "prices"
PRICES_DIR.mkdir(parents=True, exist_ok=True)

def download_tasi_history():
    print("--- TASI Price History Downloader ---")
    if not FUNDAMENTALS.exists():
        print(f"❌ Error: {FUNDAMENTALS} not found. Create the fundamentals CSV first.")
        return

    df = pd.read_csv(FUNDAMENTALS)
    if "symbol" not in df.columns:
        print("❌ Error: 'symbol' column missing.")
        return

    # TASI tickers on Yahoo Finance need the .SR suffix
    symbols = df["symbol"].dropna().astype(str).str.strip().unique()
    print(f"Downloading price history for {len(symbols)} TASI stocks...\n")

    success, failed = 0, 0
    
    for sym in symbols:
        yahoo_ticker = f"{sym}.SR"
        print(f"Fetching {yahoo_ticker}...", end=" ")
        
        try:
            # Download 1 year of daily data
            ticker = yf.Ticker(yahoo_ticker)
            hist = ticker.history(period="1y", interval="1d")
            
            if hist.empty:
                print("⚠️ No data found.")
                failed += 1
                continue
            
            # Clean up the dataframe
            hist = hist.reset_index()
            hist.columns = [str(c).replace(" ", "_") for c in hist.columns]
            hist["Symbol"] = sym
            hist["Source"] = "Yahoo Finance (TASI)"
            
            # Save to the exact path the liquidity filter expects
            clean_path = PRICES_DIR / f"{sym}_prices.csv"
            hist.to_csv(clean_path, index=False)
            
            print(f"✅ Saved {len(hist)} rows.")
            success += 1
            
        except Exception as e:
            print(f"❌ Error: {e}")
            failed += 1
            
        time.sleep(0.5) # Polite delay to avoid Yahoo rate-limiting

    print(f"\n--- Done: {success} succeeded, {failed} failed ---")
    print(f"📁 Data saved to: {PRICES_DIR}")

if __name__ == "__main__":
    download_tasi_history()
