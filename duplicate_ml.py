import time
import requests
from duplicate_fundamental import get_screener_ratios_multiple

TELEGRAM_BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
TELEGRAM_CHAT_ID = "7475999824"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        print("Telegram API Error:", resp.text)
    return resp.status_code == 200

def run_test():
    tickers = ["ASIANPAINT", "JINDALSTEL", "GMRAIRPORT"]
    print("Fetching live Screener Consolidated data for:", tickers)
    all_data = get_screener_ratios_multiple(tickers)

    for ticker in tickers:
        data = all_data.get(ticker, {})
        if not data:
            continue

        tv_link = f"https://in.tradingview.com/chart/?symbol=NSE:{ticker}"
        screener_link = f"https://www.screener.in/company/{ticker}/consolidated/"

        msg = f"""━━━━━━━━━━━━━━━━━━━━
🔍 <b>{ticker}</b> 🟡 MID CAP • {data.get('sector', 'N/A')}
━━━━━━━━━━━━━━━━━━━━

• <a href="{tv_link}">TV 📈</a>   |   <a href="{screener_link}">Fundamental 🏛️</a>

• Price: ₹{data.get('current_price', '—')} | Vol: High
_______________________________

▼ 🇮🇳 FUNDAMENTAL HEALTH
_______________________________

• Piotroski F-Score: {data.get('piotroski', '—')}

• Market Cap: ₹{data.get('market_cap', '—')} Cr

• P/E: {data.get('pe', '—')} [Target: 10 to 45]

• ROCE: {data.get('roce', '—')}% [Target: &gt; 15%]

• ROE: {data.get('roe', '—')}% [Target: &gt; 15%]

• Debt/Equity: {data.get('debt_equity', '—')} [Target: &lt; 1.0]

• Sales Growth (TTM / 3Y): {data.get('sales_growth', '—')}% / {data.get('sales_growth_3yr', '—')}% [Target: &gt; 10%]

• Profit Growth (TTM / 3Y): {data.get('profit_growth', '—')}% / {data.get('profit_var_3yr', '—')}% [Target: &gt; 12%]

• OPM: {data.get('opm', '—')}% [Target: &gt; 15%]

• Interest Coverage (TTM / FY): {data.get('int_coverage', '—')} / {data.get('int_coverage', '—')} [Target: &gt; 3.5]


▼ 🇮🇳 MOMENTUM & SHAREHOLDING
_______________________________

• Price CAGR (1Y / 3Y): {data.get('cagr_1y', '—')}% / {data.get('cagr_3y', '—')}%

• Promoter Holding: {data.get('promoter', '—')}%

• Pledged percentage: {data.get('pledged', '—')}% [Target: &lt; 5.0%]

• FII Holding: {data.get('fii', '—')}%

• DII Holding: {data.get('dii', '—')}%
"""

        print(f"Sending {ticker} card to Telegram...")
        success = send_telegram_message(msg)
        if success:
            print(f"Telegram alert for {ticker} sent successfully!")
        else:
            print(f"Failed to send Telegram alert for {ticker}.")
        time.sleep(1)

if __name__ == "__main__":
    run_test()

