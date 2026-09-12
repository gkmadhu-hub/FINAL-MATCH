import os
import re
import atexit
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import yfinance as yf

# Screener Login Credentials
SCREENER_USER = os.getenv("SCREENER_USERNAME", "bsbindurani@gmail.com")
SCREENER_PASS = os.getenv("SCREENER_PASSWORD", "cricket786")

def clean_val(val_str):
    if val_str is None:
        return None
    try:
        clean = str(val_str).replace("%", "").replace(",", "").replace("₹", "").replace("Cr", "").strip()
        return float(clean)
    except Exception:
        return None

# Global Playwright Single-Session Handler
_playwright_instance = None
_browser_instance = None
_context_instance = None
_page_instance = None
_is_logged_in = False

def get_shared_screener_page():
    global _playwright_instance, _browser_instance, _context_instance, _page_instance, _is_logged_in
    if _page_instance is not None and not _page_instance.is_closed():
        return _page_instance

    _playwright_instance = sync_playwright().start()
    _browser_instance = _playwright_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    )
    _context_instance = _browser_instance.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768}
    )
    _page_instance = _context_instance.new_page()

    if not _is_logged_in:
        try:
            _page_instance.goto("https://www.screener.in/login/", timeout=60000)
            _page_instance.fill("input[name='username']", SCREENER_USER)
            _page_instance.fill("input[name='password']", SCREENER_PASS)
            _page_instance.click("button[type='submit']")
            _page_instance.wait_for_timeout(3000)
            _is_logged_in = True
        except Exception as e:
            print(f"Screener Shared Login Error: {e}")

    return _page_instance

def cleanup_shared_session():
    global _playwright_instance, _browser_instance
    try:
        if _browser_instance:
            _browser_instance.close()
        if _playwright_instance:
            _playwright_instance.stop()
    except Exception:
        pass

atexit.register(cleanup_shared_session)

def get_screener_data(symbol):
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

    metrics = {
        "market_cap": None,
        "cap_category": "N/A",
        "sector": "N/A",
        "industry": "N/A",
        "high_52w": None,
        "low_52w": None,
        "pe": None,
        "roce": None,
        "roe": None,
        "debt_to_equity": None,
        "sales_growth_ttm": None,
        "sales_growth_3y": None,
        "profit_growth_ttm": None,
        "profit_growth_3y": None,
        "opm": None,
        "interest_coverage_ttm": None,
        "interest_coverage_fy": None,
        "price_cagr_1y": None,
        "price_cagr_3y": None,
        "promoter_holding": None,
        "pledged_percentage": None,
        "fii_holding": None,
        "dii_holding": None,
        "piotroski": None,
    }

    # 1. Base Sector / Industry from YFinance
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        info = ticker.info or {}
        if info:
            metrics["sector"] = info.get("sector") or "N/A"
            metrics["industry"] = info.get("industry") or "N/A"
    except Exception:
        pass

    # 2. Extract Data using Persistent Shared Session
    data = {}
    try:
        page = get_shared_screener_page()

        # Step A: Try Consolidated URL first
        cons_url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
        page.goto(cons_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        soup = BeautifulSoup(page.content(), "html.parser")
        top_ratios = soup.find("ul", id="top-ratios")

        # Step B: Fallback to Standalone if Consolidated doesn't exist
        if not top_ratios:
            page.goto(f"https://www.screener.in/company/{clean_sym}/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            soup = BeautifulSoup(page.content(), "html.parser")
            top_ratios = soup.find("ul", id="top-ratios")

        # Step C: Parse Custom Top Ratios Box
        if top_ratios:
            for li in top_ratios.find_all("li"):
                name_elem = li.find("span", class_="name")
                val_elem = li.find("span", class_="number") or li.find("span", class_="value")
                if name_elem and val_elem:
                    k = name_elem.text.strip().lower()
                    v = val_elem.text.strip().replace(",", "").replace("%", "")
                    data[k] = v

        # Sector Fallback
        peers_sec = soup.find("section", id="peers")
        if peers_sec:
            sub = peers_sec.find("p", class_="sub")
            if sub and sub.find("a"):
                metrics["sector"] = sub.find("a").text.strip()

    except Exception as e:
        print(f"Error scraping {clean_sym}: {e}")

    def find_key(names, d=data):
        for k in d:
            for n in names:
                if n == k:
                    return clean_val(d[k])
        for k in d:
            for n in names:
                if n in k:
                    return clean_val(d[k])
        return None

    # Map Fields from Custom Box
    if data:
        metrics["market_cap"] = find_key(["market cap"])
        metrics["pe"] = find_key(["stock p/e", "p/e"])
        metrics["roce"] = find_key(["roce"])
        metrics["roe"] = find_key(["roe"])
        metrics["debt_to_equity"] = find_key(["debt to equity"])
        metrics["sales_growth_ttm"] = find_key(["sales growth"])
        metrics["sales_growth_3y"] = find_key(["sales growth 3years", "sales growth 3yr"])
        metrics["profit_growth_ttm"] = find_key(["profit growth"])
        metrics["profit_growth_3y"] = find_key(["profit var 3yrs", "profit var 3years"])
        metrics["opm"] = find_key(["opm"])
        metrics["interest_coverage_ttm"] = find_key(["int coverage", "interest coverage"])
        metrics["interest_coverage_fy"] = metrics["interest_coverage_ttm"]

        pio = find_key(["piotroski score", "piotroski"])
        metrics["piotroski"] = int(pio) if pio is not None else None

        metrics["pledged_percentage"] = find_key(["pledged percentage", "pledged"])
        metrics["promoter_holding"] = find_key(["promoter holding"])
        metrics["fii_holding"] = find_key(["fii holding"])
        metrics["dii_holding"] = find_key(["dii holding"])
        metrics["price_cagr_1y"] = find_key(["return over 1year", "return over 1 year"])
        metrics["price_cagr_3y"] = find_key(["return over 3years", "return over 3 years"])

    # Cap Category
    if metrics["market_cap"] is not None:
        if metrics["market_cap"] >= 20000:
            metrics["cap_category"] = "🟢 LARGE CAP"
        elif metrics["market_cap"] >= 5000:
            metrics["cap_category"] = "🟡 MID CAP"
        else:
            metrics["cap_category"] = "🔴 SMALL CAP"

    return metrics

def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    pg = m["profit_growth_ttm"] if m["profit_growth_ttm"] is not None else m["profit_growth_3y"]
    if pg is not None:
        max_possible_score += 15
        if pg >= 12.0:
            earned_score += 15
            marks["profit_growth"] = True
        else:
            earned_score += 5 if pg >= 5.0 else 0
            marks["profit_growth"] = False
    else:
        marks["profit_growth"] = None

    if m["roce"] is not None:
        max_possible_score += 15
        if m["roce"] >= 15.0:
            earned_score += 15
            marks["roce"] = True
        else:
            earned_score += 6 if m["roce"] >= 10.0 else 0
            marks["roce"] = False
    else:
        marks["roce"] = None

    if m["debt_to_equity"] is not None:
        max_possible_score += 15
        if m["debt_to_equity"] < 1.0:
            earned_score += 15
            marks["debt_to_equity"] = True
        else:
            earned_score += 5 if m["debt_to_equity"] < 1.5 else 0
            marks["debt_to_equity"] = False
    else:
        marks["debt_to_equity"] = None

    if m["roe"] is not None:
        max_possible_score += 12
        if m["roe"] >= 15.0:
            earned_score += 12
            marks["roe"] = True
        else:
            earned_score += 5 if m["roe"] >= 10.0 else 0
            marks["roe"] = False
    else:
        marks["roe"] = None

    sg = m["sales_growth_ttm"] if m["sales_growth_ttm"] is not None else m["sales_growth_3y"]
    if sg is not None:
        max_possible_score += 12
        if sg >= 10.0:
            earned_score += 12
            marks["sales_growth"] = True
        else:
            earned_score += 4 if sg >= 5.0 else 0
            marks["sales_growth"] = False
    else:
        marks["sales_growth"] = None

    if m["opm"] is not None:
        max_possible_score += 12
        if m["opm"] >= 15.0:
            earned_score += 12
            marks["opm"] = True
        else:
            earned_score += 4 if m["opm"] >= 8.0 else 0
            marks["opm"] = False
    else:
        marks["opm"] = None

    if m["pe"] is not None:
        max_possible_score += 10
        if 10.0 <= m["pe"] <= 45.0:
            earned_score += 10
            marks["pe"] = True
        else:
            earned_score += 4 if m["pe"] <= 60.0 else 0
            marks["pe"] = False
    else:
        marks["pe"] = None

    ic = m["interest_coverage_ttm"] if m["interest_coverage_ttm"] is not None else m["interest_coverage_fy"]
    if ic is not None:
        max_possible_score += 9
        if ic >= 3.5:
            earned_score += 9
            marks["interest_coverage"] = True
        else:
            marks["interest_coverage"] = False
    else:
        marks["interest_coverage"] = None

    if max_possible_score >= 20:
        final_score = int(round((earned_score / max_possible_score) * 100))
        if final_score >= 80: quality = "🟢 A+ SUPER STRONG"
        elif final_score >= 65: quality = "🟢 A GOOD QUALITY"
        elif final_score >= 50: quality = "🟡 B AVERAGE"
        else: quality = "🔴 C WEAK"
    else:
        final_score = "N/A"
        quality = "⚪ DATA UNAVAILABLE"

    return final_score, quality, marks

def get_fundamental_analysis(symbol):
    try:
        metrics = get_screener_data(symbol)
        score, quality, marks = calculate_100M_score(metrics)
        return {
            "available": (score != "N/A"),
            "score": score,
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": []
        }
    except Exception as e:
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
        }
