import pandas as pd
import requests
import json
import time
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FUNDAMENTALS = BASE_DIR / "data" / "fundamentals" / "tasi_fundamentals.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def get_company_id(ticker):
    """Search Argaam for the ticker and extract the companyid."""
    search_url = f"https://www.argaam.com/en/search?q={ticker}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        # Argaam search results contain links like /company/companyoverview/marketid/3/companyid/1234/
        match = re.search(r'companyid/(\d+)', resp.text)
        if match:
            return match.group(1)
    except:
        pass
    return None

def fetch_argaam_data(ticker):
    print(f"Fetching {ticker}...", end=" ")
    
    # Step 1: Get company ID
    company_id = get_company_id(ticker)
    if not company_id:
        print("❌ Company ID not found")
        return None
    
    # Step 2: Fetch the JSON data
    url = f"https://www.argaam.com/en/company/companyoverview/marketid/3/companyid/{company_id}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"❌ HTTP {resp.status_code}")
            return None
        
        soup = BeautifulSoup(resp.text, "html.parser")
        # Look for the embedded JSON or specific text patterns
        # Argaam embeds the data in a script tag with JSON
        for script in soup.find_all("script"):
            if "recurringEps" in script.text:
                # Extract the JSON object
                match = re.search(r'(\{.*"recurringEps".*\})', script.text)
                if match:
                    data = json.loads(match.group(1))
                    return {
                        "eps": data.get("recurringEps"),
                        "book_value_per_share": data.get("bookValue"),
                        "roe": data.get("returnOnAverageEquity"),
                        "pe_ratio": data.get("recurringPE"),
                        "price": data.get("lastPrice"),
                    }
        
        print("⚠️ Data pattern not found")
        return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def update_all():
    print("--- TASI Fundamentals (Argaam JSON) ---")
    df = pd.read_csv(FUNDAMENTALS)
    for col in ["price", "eps", "book_value_per_share", "roe", "roic", "debt_to_equity", "interest_coverage"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
        else:
            df[col] = 0.0

    symbols = df["symbol"].dropna().unique()
    print(f"Updating {len(symbols)} stocks via Argaam...\n")

    success = 0
    for i, sym in enumerate(symbols, 1):
        sym = str(sym).strip()
        idx = df[df["symbol"] == sym].index
        if len(idx) == 0: continue
        
        data = fetch_argaam_data(sym)
        
        if data:
            updated = False
            for col in ["price", "eps", "book_value_per_share", "roe"]:
                if col in data and data[col] is not None:
                    df.loc[idx, col] = float(data[col])
                    updated = True
            if updated:
                print(f"✅ EPS={data.get('eps', '?')}, BV={data.get('book_value_per_share', '?')}")
                success += 1
            else:
                print("⚠️ No useful data")
        else:
            print("⚠️ Skipped")
        
        if i % 20 == 0:
            df.to_csv(FUNDAMENTALS, index=False)
            
        time.sleep(2.0)  # Polite delay

    df.to_csv(FUNDAMENTALS, index=False)
    print(f"\n--- Done: {success}/{len(symbols)} updated ---")

if __name__ == "__main__":
    update_all()
