import pandas as pd
import yfinance as yf
from pathlib import Path
import time
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
FUNDAMENTALS = BASE_DIR / "data" / "fundamentals" / "tasi_fundamentals.csv"
PRICES_DIR = BASE_DIR / "data" / "prices"
REPORTS_DIR = BASE_DIR / "outputs"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# === LIQUIDITY THRESHOLDS ===
MIN_AVG_VOLUME = 50000
MIN_DAYS_TRADED = 15
MIN_AVG_VALUE_SAR = 100000

SECTOR_FAIR_PE = {
    "banks": 9.0, "petrochemicals": 12.0, "telecom": 14.0, "utilities": 12.0,
    "cement": 11.0, "retail": 15.0, "healthcare": 18.0, "industrials": 13.0,
    "energy": 10.0, "realestate": 12.0, "insurance": 9.0, "generic": 12.0,
}

SECTOR_MAP = {
    "2222": "energy", "2010": "petrochemicals", "1120": "banks", "1180": "banks",
    "2350": "cement", "7010": "telecom", "2280": "consumer", "4001": "retail",
    "4013": "healthcare", "4300": "realestate",
}

MIN_PE = 5.0
MAX_PE = 30.0
MIN_MOS = 15.0
MIN_QUALITY_SCORE = 50
MIN_ROE = 0.10
MAX_DEBT_TO_EQUITY = 1.5

def to_float(val):
    try:
        if val is None or pd.isna(val): return None
        return float(val)
    except: return None

def fetch_fundamentals_from_yahoo(symbol):
    """Fetch fundamentals using the old data_provider logic."""
    yahoo_ticker = f"{symbol}.SR"
    try:
        ticker = yf.Ticker(yahoo_ticker)
        info = ticker.info
        
        # Use the same keys as the old data_provider.py
        return {
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "eps": info.get("trailingEps"),
            "book_value": info.get("bookValue"),
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "sector": info.get("sector"),
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def check_liquidity(symbol):
    """Read the price history CSV and calculate volume metrics."""
    file_path = PRICES_DIR / f"{symbol}_prices.csv"
    if not file_path.exists():
        return False, "NO_PRICE_HISTORY"
    
    try:
        df = pd.read_csv(file_path)
        if df.empty or "Volume" not in df.columns:
            return False, "NO_VOLUME_DATA"
        
        recent = df.tail(50).copy()
        recent["Volume"] = pd.to_numeric(recent["Volume"], errors="coerce").fillna(0)
        recent["Close"] = pd.to_numeric(recent["Close"], errors="coerce").fillna(0)
        
        days_traded = int((recent["Volume"] > 0).sum())
        avg_volume = recent["Volume"].mean()
        avg_value = (recent["Volume"] * recent["Close"]).mean()
        
        if days_traded < MIN_DAYS_TRADED:
            return False, f"LOW_ACTIVITY ({days_traded} days)"
        if avg_volume < MIN_AVG_VOLUME:
            return False, f"LOW_VOLUME ({avg_volume:.0f})"
        if avg_value < MIN_AVG_VALUE_SAR:
            return False, f"LOW_VALUE ({avg_value:.0f} SAR)"
        
        return True, "PASS"
    except:
        return False, "PARSE_ERROR"

def compute_quality_score(row):
    rules = [
        ("roe", lambda x: 20 if x >= 0.20 else 14 if x >= 0.15 else 8 if x >= 0.10 else 0, 20),
        ("roic", lambda x: 20 if x >= 0.15 else 14 if x >= 0.10 else 7 if x >= 0.05 else 0, 20),
        ("debt_to_equity", lambda x: 15 if x <= 0.25 else 10 if x <= 0.5 else 5 if x <= 1 else 0, 15),
        ("fcf_per_share", lambda x: 15 if x > 0 else 0, 15),
        ("eps_growth_5y", lambda x: 15 if x >= 0.10 else 10 if x >= 0.05 else 5 if x > 0 else 0, 15),
        ("interest_coverage", lambda x: 15 if x >= 8 else 10 if x >= 4 else 5 if x >= 2 else 0, 15),
    ]
    points, possible = 0.0, 0.0
    for key, fn, weight in rules:
        val = to_float(row.get(key))
        if val is None: continue
        points += fn(val)
        possible += weight
    return round(100 * points / possible, 1) if possible else None

def main():
    print(f"--- TASI Buffett Agent vTASI-2.0 ---")
    print(f"LIQUIDITY FILTERS:")
    print(f"  Min Days Traded: {MIN_DAYS_TRADED}")
    print(f"  Min Avg Volume: {MIN_AVG_VOLUME:,} shares")
    print(f"  Min Avg Value: {MIN_AVG_VALUE_SAR:,} SAR\n")

    df = pd.read_csv(FUNDAMENTALS)
    rows = []
    
    for _, r in df.iterrows():
        row = r.to_dict()
        symbol = str(row.get("symbol", "")).strip()
        
        # Fetch real fundamentals from Yahoo
        yahoo_data = None  # Use CSV data directly
        if yahoo_data:
            if yahoo_data.get("price"): row["price"] = yahoo_data["price"]
            if yahoo_data.get("eps"): row["eps"] = yahoo_data["eps"]
            if yahoo_data.get("book_value"): row["book_value_per_share"] = yahoo_data["book_value"]
            if yahoo_data.get("roe"): row["roe"] = yahoo_data["roe"]
            if yahoo_data.get("debt_to_equity"): 
                de = yahoo_data["debt_to_equity"]
                row["debt_to_equity"] = de / 100.0 if de else 0.0
            if yahoo_data.get("sector"): row["sector"] = yahoo_data["sector"]
        
        # Calculate Liquidity
        is_liquid, reason = check_liquidity(symbol)
        row["liquidity_status"] = reason
        
        # Quality & Valuation
        q_score = compute_quality_score(row)
        row["quality_score"] = q_score
        
        price = to_float(row.get("price"))
        eps = to_float(row.get("eps"))
        row["pe"] = round(price / eps, 2) if price and eps and eps > 0 else None
        
        sector = row.get("sector", "generic").lower()
        fair_pe = SECTOR_FAIR_PE.get(sector, 12.0)
        
        fair_value = eps * fair_pe if eps and eps > 0 else None
        mos = ((fair_value - price) / fair_value * 100) if fair_value and price else None
        
        row["mos"] = round(mos, 2) if mos else None
        row["valuation_status"] = "PROVISIONAL" if fair_value else "NOT_VALUED"

        reasons = []
        if not is_liquid: reasons.append(reason)
        if not row["pe"] or row["pe"] < MIN_PE or row["pe"] > MAX_PE: reasons.append("PE_FAIL")
        if not mos or mos < MIN_MOS: reasons.append("MOS_BELOW_15")
        if not q_score or q_score < MIN_QUALITY_SCORE: reasons.append("QUALITY_BELOW_50")
        
        row["rejection_reasons"] = "|".join(reasons)
        row["is_candidate"] = len(reasons) == 0
        rows.append(row)
        time.sleep(1.0) # Polite delay

    all_df = pd.DataFrame(rows)
    candidates = all_df[all_df["is_candidate"] == True].copy()
    rejected = all_df[all_df["is_candidate"] == False].copy()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = REPORTS_DIR / f"tasi_scan_{timestamp}.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        candidates.to_excel(writer, sheet_name="Filtered", index=False)
        all_df.to_excel(writer, sheet_name="All_Data", index=False)
        rejected.to_excel(writer, sheet_name="Rejected", index=False)

    print(f"\n🏆 RESULT: {len(candidates)} TRADEABLE candidates out of {len(all_df)} stocks")
    if len(candidates) > 0:
        print("\n=== TRADEABLE TASI BUY LIST ===")
        for _, c in candidates.iterrows():
            sym_str = str(c['symbol']).strip()
            name_str = str(c.get('company_name', 'Unknown')).strip()
            print(f"  {sym_str:6s} | MOS={c['mos']:5.1f}% | Quality={c['quality_score']:5.1f} | {name_str[:30]}")
    else:
        print("\n❌ NO TRADEABLE STOCKS FOUND.")
    
    print(f"\n📁 Report: {output_path}")

if __name__ == "__main__":
    from datetime import datetime
    main()

