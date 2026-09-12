import requests
from duplicate_fundamental import get_screener_ratios

# Telegram Bot Credentials
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
    ticker = "ASIANPAINT"
    data = get_screener_ratios(ticker)
    
    # Format message with clean line-by-line spacing
    msg = f"""━━━━━━━━━━━━━━━━━━━━
🔍 {ticker} 🟡 MID CAP • {data['sector']}
━━━━━━━━━━━━━━━━━━━━

• TV 📈   |   Fundamental 🏛️

• Price: ₹{data['current_price']} | Vol: High
_______________________________

▼ 🇮🇳 FUNDAMENTAL HEALTH: 92/100 (🟢 A+ SUPER STRONG)
_______________________________

• Piotroski F-Score: {data['piotroski']}

• Market Cap: ₹{data['market_cap']} Cr

• P/E: {data['pe']} [Target: 10 to 45]

• ROCE: {data['roce']}% [Target: > 15%]

• ROE: {data['roe']}% [Target: > 15%]

• Debt/Equity: {data['debt_equity']} [Target: < 1.0]

• Sales Growth (TTM / 3Y): {data['sales_growth']}% / {data['sales_growth_3yr']}% [Target: > 10%]

• Profit Growth (TTM / 3Y): {data['profit_growth']}% / {data['profit_var_3yr']}% [Target: > 12%]

• OPM: {data['opm']}% [Target: > 15%]

• Interest Coverage (TTM / FY): {data['int_coverage']} / {data['int_coverage']} [Target: > 3.5]


▼ 🇮🇳 MOMENTUM & SHAREHOLDING
_______________________________

• Price CAGR (1Y / 3Y): {data['cagr_1y']}% / {data['cagr_3y']}%

• Promoter Holding: {data['promoter']}%

• Pledged percentage: {data['pledged']}% [Target: < 5.0%]

• FII Holding: {data['fii']}%

• DII Holding: {data['dii']}%
"""

    print("Sending message to Telegram...")
    success = send_telegram_message(msg)
    if success:
        print("Telegram alert sent successfully!")
    else:
        print("Failed to send Telegram alert.")

if __name__ == "__main__":
    run_test()

