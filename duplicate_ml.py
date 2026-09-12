import time
import requests
from duplicate_fundamental import get_screener_ratios_multiple

TELEGRAM_BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
TELEGRAM_CHAT_ID = "7475999824"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    resp = requests.post(url, json=payload)
    return resp.status_code == 200

def run_test():
    tickers = ["ASIANPAINT", "JINDALSTEL", "GMRAIRPORT"]
    print("Fetching live Screener data for stocks:", tickers)
    all_data = get_screener_ratios_multiple(tickers)

    for ticker in tickers:
        data = all_data.get(ticker, {})
        if not data:
            continue

        msg = f"""━━━━━━━━━━━━━━━━━━━━
🔍 {ticker} 🟡 MID CAP • {data.get('sector', 'N/A')}
━━━━━━━━━━━━━━━━━━━━

• TV 📈   |   Fundamental 🏛️

• Price: ₹{data.get('current_price', 'N/A')} | Vol: High
_______________________________

▼ 🇮🇳 FUNDAMENTAL HEALTH
_______________________________

• Piotroski F-Score: {data.get('piotroski', 'N/A')}

• Market Cap: ₹{data.get('market_cap', 'N/A')} Cr

• P/E: {data.get('pe', 'N/A')} [Target: 10 to 45]

• ROCE: {data.get('roce', 'N/A')}% [Target: > 15%]

• ROE: {data.get('roe', 'N/A')}% [Target: > 15%]

• Debt/Equity: {data.get('debt_equity', 'N/A')} [Target: < 1.0]

• Sales Growth (TTM / 3Y): {data.get('sales_growth', 'N/A')}% / {data.get('sales_growth_3yr', 'N/A')}% [Target: > 10%]

• Profit Growth (TTM / 3Y): {data.get('profit_growth', 'N/A')}% / {data.get('profit_var_3yr', 'N/A')}% [Target: > 12%]

• OPM: {data.get('opm', 'N/A')}% [Target: > 15%]

• Interest Coverage (TTM / FY): {data.get('int_coverage', 'N/A')} / {data.get('int_coverage', 'N/A')} [Target: > 3.5]


▼ 🇮🇳 MOMENTUM & SHAREHOLDING
_______________________________

• Price CAGR (1Y / 3Y): {data.get('cagr_1y', 'N/A')}% / {data.get('cagr_3y', 'N/A')}%

• Promoter Holding: {data.get('promoter', 'N/A')}%

• Pledged percentage: {data.get('pledged', 'N/A')}% [Target: < 5.0%]

• FII Holding: {data.get('fii', 'N/A')}%

• DII Holding: {data.get('dii', 'N/A')}%
"""

        print(f"Sending {ticker} message to Telegram...")
        success = send_telegram_message(msg)
        if success:
            print(f"Telegram alert for {ticker} sent successfully!")
        else:
            print(f"Failed to send Telegram alert for {ticker}.")
        time.sleep(1)

if __name__ == "__main__":
    run_test()
        
