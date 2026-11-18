import pandas as pd
import glob
import os
from pathlib import Path
import webbrowser
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS = BASE_DIR / "outputs"

def generate_report():
    files = glob.glob(str(OUTPUTS / "tasi_scan_*.xlsx"))
    if not files:
        print("No report found.")
        return
    
    latest = max(files, key=os.path.getctime)
    df = pd.read_excel(latest, sheet_name="Filtered")
    
    html = f"""
    <html><head><style>
        body {{ font-family: 'Segoe UI'; background: #0f172a; color: white; padding: 40px; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; }}
        th {{ background: #0f172a; color: #94a3b8; padding: 15px; text-align: left; }}
        td {{ padding: 12px; border-top: 1px solid #334155; }}
        .badge {{ padding: 5px 10px; border-radius: 6px; background: #059669; font-weight: bold; }}
        a {{ color: #3b82f6; text-decoration: none; }}
    </style></head><body>
    <h1>🇸🇦 TASI Buffett Agent: Daily Buy List</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <table>
        <tr><th>Symbol</th><th>Company</th><th>Price (SAR)</th><th>Margin of Safety</th><th>Quality</th></tr>
    """
    for _, row in df.iterrows():
        sym = str(row['symbol']).strip()
        url = f"https://stockanalysis.com/quote/tadawul/{sym}/statistics/"
        html += f"<tr><td><a href='{url}' target='_blank'>{sym}</a></td><td>{row.get('company_name','')}</td><td>{row['price']}</td><td><span class='badge'>{row['mos']}%</span></td><td>{row['quality_score']}</td></tr>"
    
    html += "</table></body></html>"
    
    out = OUTPUTS / "tasi_daily_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"HTML Report: {out.name}")
    webbrowser.open(f"file://{out.absolute()}")

if __name__ == "__main__":
    generate_report()
