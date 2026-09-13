import sys
import os
import requests
from playwright.sync_api import sync_playwright

# Streamlit Cloud ಗಾಗಿ Playwright Chromium ಲೈಬ್ರರಿ ಇನ್‌ಸ್ಟಾಲ್ ಖಚಿತಪಡಿಸಲು
os.system("playwright install chromium")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
CHAT_ID = "7475999824"
SCREENER_EMAIL = "bsbindurani@gmail.com"
SCREENER_PASS = "cricket786"

def send_telegram_message(message):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(tg_url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram Send Error: {e}", file=sys.stderr)

def scrape_screener(symbol):
    symbol = symbol.strip().upper()
    
    with sync_playwright() as p:
        # ಕನಿಷ್ಠ RAM ಬಳಸುವ ಲಾಂಚ್ ಫ್ಲ್ಯಾಗ್‌ಗಳು
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process"
            ]
        )
        context = browser.new_context()
        page = context.new_page()

        # Screener ಇಮೇಜ್ & ಫಾಂಟ್‌ಗಳನ್ನು ಬ್ಲಾಕ್ ಮಾಡಿ 80% RAM ಉಳಿಸುವ ಫಿಲ್ಟರ್
        page.route(
            "**/*", 
            lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
        )

        try:
            # 1. ಲಾಗಿನ್ ಪ್ರಕ್ರಿಯೆ
            page.goto("https://www.screener.in/login/", timeout=35000)
            page.fill('input[name="username"]', SCREENER_EMAIL)
            page.fill('input[name="password"]', SCREENER_PASS)
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)

            # 2. ಕಂಪನಿ ಕನ್ಸೋಲಿಡೇಟೆಡ್ ಪೇಜ್‌ಗೆ ಭೇಟಿ
            url = f"https://www.screener.in/company/{symbol}/consolidated/"
            page.goto(url, timeout=35000)
            page.wait_for_timeout(2000)

            # 3. ಎಲ್ಲಾ ಟಾಪ್ ರೇಷಿಯೋಗಳನ್ನು ಎಕ್ಸ್‌ಟ್ರಾಕ್ಟ್ ಮಾಡುವುದು
            data = {}
            items = page.query_selector_all("#top-ratios li")
            for item in items:
                name_elem = item.query_selector(".name")
                val_elem = item.query_selector(".value")
                if name_elem and val_elem:
                    k = name_elem.inner_text().strip()
                    v = val_elem.inner_text().strip()
                    data[k] = v

            # ಕಂಪನಿ ಹೆಸರು & ಇಂಡಸ್ಟ್ರಿ
            h1 = page.query_selector("h1")
            company_name = h1.inner_text().strip() if h1 else symbol
            
            # ರೇಷಿಯೋ ಮ್ಯಾಪಿಂಗ್
            price = data.get("Current Price", "N/A")
            high_low = data.get("High / Low", "N/A")
            mcap = data.get("Market Cap", "N/A")
            pe = data.get("Stock P/E", "N/A")
            roce = data.get("ROCE", "N/A")
            roe = data.get("ROE", "N/A")
            debt_equity = data.get("Debt to equity", "0.0")
            opm = data.get("OPM", "N/A")
            piotroski = data.get("Piotroski score", "N/A")
            promoter = data.get("Promoter holding", "N/A")
            dii = data.get("DII holding", "N/A")
            fii = data.get("FII holding", "N/A")
            int_cov = data.get("Interest Coverage", "N/A")

            # 4. ಪೂರ್ಣ ಟೆಲಿಗ್ರಾಂ ಕಾರ್ಡ್ ರಚನೆ
            card = (
                f"🇮🇳 🇮🇳 *GK INSTANT STOCK ANALYSIS* 🇮🇳 🇮🇳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⭐ *{company_name}* ({symbol})\n\n"
                f"• *Price:* ₹{price} | *52W H/L:* ₹{high_low}\n"
                f"• *Market Cap:* ₹{mcap} Cr\n"
                f"_______________________________\n\n"
                f"🇮🇳 *FUNDAMENTAL HEALTH* 🇮🇳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Piotroski F-Score: *{piotroski}*\n"
                f"• P/E: *{pe}*\n"
                f"• ROCE: *{roce}%*\n"
                f"• ROE: *{roe}%*\n"
                f"• Debt/Equity: *{debt_equity}*\n"
                f"• OPM: *{opm}%*\n"
                f"• Interest Coverage: *{int_cov}*\n"
                f"_______________________________\n\n"
                f"🇮🇳 *SHAREHOLDING PATTERN* 🇮🇳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• Promoter Holding: *{promoter}%*\n"
                f"• FII Holding: *{fii}%*\n"
                f"• DII Holding: *{dii}%*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *DATA SOURCE:* Real Screener.in Account"
            )

            # ಟೆಲಿಗ್ರಾಂಗೆ ಕಾರ್ಡ್ ಕಳುಹಿಸಿ
            send_telegram_message(card)
            print("SUCCESS")

        except Exception as e:
            print(f"SCRAPE_ERROR: {str(e)}", file=sys.stderr)
            sys.exit(1)
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        stock_arg = sys.argv[1].strip()
        scrape_screener(stock_arg)
                    
