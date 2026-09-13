import sys
import os
import requests
from playwright.sync_api import sync_playwright

os.system("playwright install chromium")

BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
CHAT_ID = "7475999824"
SCREENER_EMAIL = "bsbindurani@gmail.com"
SCREENER_PASS = "cricket786"

def get_fundamental_analysis(symbol):
    symbol = symbol.strip().upper()
    metrics = {}
    marks = {}
    score = 50
    quality = "🟡 MODERATE"

    with sync_playwright() as p:
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

        page.route(
            "**/*", 
            lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
        )

        try:
            page.goto("https://www.screener.in/login/", timeout=35000)
            page.fill('input[name="username"]', SCREENER_EMAIL)
            page.fill('input[name="password"]', SCREENER_PASS)
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)

            # 1. ಮೊದಲು Consolidated ಟ್ರೈ ಮಾಡು
            url = f"https://www.screener.in/company/{symbol}/consolidated/"
            page.goto(url, timeout=35000)
            page.wait_for_timeout(2000)

            data = {}
            items = page.query_selector_all("#top-ratios li")
            
            # ಒಂದುವೇಳೆ Consolidated ಲಿಂಕ್‌ನಲ್ಲಿ ಡೇಟಾ ಸಿಗಲಿಲ್ಲ ಅಂದರೆ Standalone ಗೆ ಹೋಗು
            if not items:
                url_stand = f"https://www.screener.in/company/{symbol}/"
                page.goto(url_stand, timeout=35000)
                page.wait_for_timeout(2000)
                items = page.query_selector_all("#top-ratios li")

            for item in items:
                name_elem = item.query_selector(".name")
                val_elem = item.query_selector(".value")
                if name_elem and val_elem:
                    k = name_elem.inner_text().strip()
                    v = val_elem.inner_text().strip()
                    data[k] = v

            def parse_num(val_str):
                if not val_str:
                    return None
                try:
                    clean = val_str.replace(",", "").replace("₹", "").replace("%", "").strip()
                    return float(clean) # ರೌಂಡ್ ಆಫ್ ಮಾಡದೇ ಎಕ್ಸಾಕ್ಟ್ ಡೆಸಿಮಲ್
                except:
                    return None

            metrics['market_cap'] = parse_num(data.get("Market Cap"))
            metrics['pe'] = parse_num(data.get("Stock P/E"))
            metrics['roce'] = parse_num(data.get("ROCE"))
            metrics['roe'] = parse_num(data.get("ROE"))
            metrics['debt_to_equity'] = parse_num(data.get("Debt to equity"))
            metrics['opm'] = parse_num(data.get("OPM"))
            metrics['piotroski_score'] = parse_num(data.get("Piotroski score"))
            metrics['promoter_holding'] = parse_num(data.get("Promoter holding"))
            metrics['pledged_percentage'] = parse_num(data.get("Pledged percentage"))
            metrics['fii_holding'] = parse_num(data.get("FII holding"))
            metrics['dii_holding'] = parse_num(data.get("DII holding"))
            metrics['sales_growth_ttm'] = parse_num(data.get("Sales growth"))
            metrics['profit_growth_ttm'] = parse_num(data.get("Profit growth"))
            metrics['interest_coverage_ttm'] = parse_num(data.get("Interest Coverage"))

            pe_val = metrics.get('pe')
            marks['pe'] = (10 <= pe_val <= 45) if pe_val is not None else None
            roce_val = metrics.get('roce')
            marks['roce'] = (roce_val > 15) if roce_val is not None else None
            roe_val = metrics.get('roe')
            marks['roe'] = (roe_val > 15) if roe_val is not None else None
            de_val = metrics.get('debt_to_equity')
            marks['debt_to_equity'] = (de_val < 1.0) if de_val is not None else None
            opm_val = metrics.get('opm')
            marks['opm'] = (opm_val > 15) if opm_val is not None else None

            score_pts = 50
            if marks.get('roce'): score_pts += 15
            if marks.get('roe'): score_pts += 15
            if marks.get('debt_to_equity'): score_pts += 10
            if marks.get('pe'): score_pts += 10
            score = min(100, score_pts)
            quality = "🟢 STRONG" if score >= 70 else ("🔴 WEAK" if score < 45 else "🟡 MODERATE")

            return {
                "available": True,
                "score": score,
                "quality": quality,
                "marks": marks,
                "metrics": metrics
            }

        except Exception as e:
            print(f"SCRAPE_ERROR: {str(e)}", file=sys.stderr)
            return {"available": False, "score": "N/A", "quality": "⚪ DATA UNAVAILABLE", "marks": {}, "metrics": {}}
        finally:
            context.close()
            browser.close()
        
