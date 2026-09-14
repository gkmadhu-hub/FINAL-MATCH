import sys
import os
import requests
from playwright.sync_api import sync_playwright

os.system("playwright install chromium")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            # Screener Login (ಕಸ್ಟಮ್ ರೇಶಿಯೋ ಟೇಬಲ್ ಲೋಡ್ ಆಗಲು ಲಾಗಿನ್ ಕಡ್ಡಾಯ)
            page.goto("https://www.screener.in/login/", timeout=35000)
            page.fill('input[name="username"]', SCREENER_EMAIL)
            page.fill('input[name="password"]', SCREENER_PASS)
            page.click('button[type="submit"]')
            page.wait_for_timeout(2500)

            # 1. ಮೊದಲು Consolidated, ಲಭ್ಯವಿಲ್ಲದಿದ್ದರೆ Standalone
            target_url = f"https://www.screener.in/company/{symbol}/consolidated/"
            page.goto(target_url, timeout=35000)
            page.wait_for_timeout(2000)

            items = page.query_selector_all("#top-ratios li")
            if not items:
                target_url = f"https://www.screener.in/company/{symbol}/"
                page.goto(target_url, timeout=35000)
                page.wait_for_timeout(2000)
                items = page.query_selector_all("#top-ratios li")

            if not items:
                return {
                    "available": False, "score": "N/A", "quality": "⚪ DATA UNAVAILABLE",
                    "marks": {}, "metrics": {}, "screener_url": target_url
                }

            # Top Ratios ನಿಂದ ಎಲ್ಲಾ ಹೆಸರು ಮತ್ತು ಮೌಲ್ಯಗಳನ್ನು ಮ್ಯಾಪ್ ಮಾಡುವುದು
            data = {}
            for item in items:
                name_elem = item.query_selector(".name")
                val_elem = item.query_selector(".value")
                if name_elem and val_elem:
                    k = name_elem.inner_text().strip().lower()
                    v = val_elem.inner_text().strip()
                    data[k] = v

            # Peers ವಿಭಾಗದಿಂದ Sector & Industry
            peers_section = page.query_selector("#peers")
            sector_val, ind_val = "N/A", "N/A"
            if peers_section:
                links = peers_section.query_selector_all("a")
                p_texts = [a.inner_text().strip() for a in links if a.inner_text().strip()]
                if len(p_texts) >= 2:
                    sector_val = p_texts[0]
                    ind_val = p_texts[1]
            metrics['sector'] = sector_val
            metrics['industry'] = ind_val

            # ಡೆಸಿಮಲ್ ಮೌಲ್ಯಗಳನ್ನು ಕರಾರುವಕ್ಕಾಗಿ ಪಾರ್ಸ್ ಮಾಡುವ ಫಂಕ್ಷನ್
            def parse_num(val_str):
                if not val_str:
                    return None
                try:
                    clean = (val_str.replace(",", "")
                                    .replace("₹", "")
                                    .replace("%", "")
                                    .replace("Cr.", "")
                                    .replace("Cr", "")
                                    .strip())
                    return float(clean)
                except:
                    return None

            # ಟಾಪ್ ರೇಶಿಯೋ ಕಾರ್ಡ್‌ನಲ್ಲಿರುವ ಎಕ್ಸಾಕ್ಟ್ ಕೀ ಮ್ಯಾಪಿಂಗ್
            metrics['market_cap'] = parse_num(data.get("market cap"))
            metrics['pe'] = parse_num(data.get("stock p/e") or data.get("p/e"))
            metrics['roce'] = parse_num(data.get("roce"))
            metrics['roe'] = parse_num(data.get("roe"))
            metrics['debt_to_equity'] = parse_num(data.get("debt to equity"))
            metrics['opm'] = parse_num(data.get("opm"))
            metrics['piotroski_score'] = parse_num(data.get("piotroski score"))
            metrics['promoter_holding'] = parse_num(data.get("promoter holding"))
            metrics['pledged_percentage'] = parse_num(data.get("pledged percentage"))
            metrics['fii_holding'] = parse_num(data.get("fii holding"))
            metrics['dii_holding'] = parse_num(data.get("dii holding"))
            
            # Growth & Coverage ರೇಶಿಯೋಗಳು
            metrics['sales_growth_ttm'] = parse_num(data.get("sales growth"))
            metrics['sales_growth_3y'] = parse_num(data.get("sales growth 3years") or data.get("sales growth 3 years"))
            metrics['profit_growth_ttm'] = parse_num(data.get("profit growth"))
            metrics['profit_growth_3y'] = parse_num(data.get("profit var 3yrs") or data.get("profit growth 3years"))
            metrics['interest_coverage_ttm'] = parse_num(data.get("int coverage") or data.get("interest coverage"))
            
            # Price CAGR (Return over 1Y / 3Y)
            metrics['price_cagr_1y'] = parse_num(data.get("return over 1year") or data.get("return over 1 year"))
            metrics['price_cagr_3y'] = parse_num(data.get("return over 3years") or data.get("return over 3 years"))

            # Market Cap ಕೆಟಗರಿ ವಿಂಗಡಣೆ
            mcap_val = metrics.get('market_cap') or 0.0
            if mcap_val >= 20000:
                metrics['cap_category'] = "🟢 LARGE CAP"
            elif mcap_val >= 5000:
                metrics['cap_category'] = "🟡 MID CAP"
            elif mcap_val > 0:
                metrics['cap_category'] = "🟠 SMALL CAP"
            else:
                metrics['cap_category'] = "N/A"

            # ಮಾರ್ಕ್ಸ್ & ಸ್ಕೋರ್ ಲೆಕ್ಕಾಚಾರ
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
            ic_val = metrics.get('interest_coverage_ttm')
            marks['interest_coverage'] = (ic_val > 3.5) if ic_val is not None else None
            sales_val = metrics.get('sales_growth_ttm')
            marks['sales_growth'] = (sales_val > 10) if sales_val is not None else None
            profit_val = metrics.get('profit_growth_ttm')
            marks['profit_growth'] = (profit_val > 12) if profit_val is not None else None

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
                "metrics": metrics,
                "screener_url": target_url
            }

        except Exception as e:
            print(f"SCRAPE_ERROR: {str(e)}", file=sys.stderr)
            return {
                "available": False, "score": "N/A", "quality": "⚪ DATA UNAVAILABLE",
                "marks": {}, "metrics": {}, "screener_url": f"https://www.screener.in/company/{symbol}/consolidated/"
            }
        finally:
            context.close()
            browser.close()
