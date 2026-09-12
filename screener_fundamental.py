import os
import re
import atexit
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import yfinance as yf

# ============================================================
# 🇮🇳 GK FUNDAMENTAL ENGINE — PERSISTENT PLAYWRIGHT SESSION
# ============================================================

SCREENER_EMAIL = os.getenv("SCREENER_USERNAME", "bsbindurani@gmail.com")
SCREENER_PASS = os.getenv("SCREENER_PASSWORD", "cricket786")

# Global Playwright Single-Session Handler
_playwright_instance = None
_browser_instance = None
_context_instance = None
_page_instance = None
_is_logged_in = False

def clean_val(val_str):
    if val_str is None:
        return None
    try:
        clean = str(val_str).replace("%", "").replace(",", "").replace("₹", "").replace("Cr", "").strip()
        return float(clean)
    except Exception:
        return None

def _clean(v, digits=2):
    if v is None:
        return None
    try:
        return round(float(v), digits)
    except Exception:
        return None

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
            _page_instance.fill("input[name='username']", SCREENER_EMAIL)
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

def _score(m):
    rules = {
        "profit_growth_ttm": (15, lambda x: x > 12),
        "roce": (15, lambda x: x > 15),
        "debt_to_equity": (15, lambda x: x < 1),
        "roe": (12, lambda x: x > 15),
        "sales_growth_ttm": (12, lambda x: x > 10),
        "opm": (12, lambda x: x > 15),
        "pe": (10, lambda x: 10 <= x <= 45),
        "interest_coverage_ttm": (9, lambda x: x > 3.5),
    }
    marks, total = {}, 0
    for key, (weight, rule) in rules.items():
        value = m.get(key)
        marks[key] = bool(rule(value)) if value is not None else None
        if marks[key]:
            total += weight

    marks["sales_growth"] = marks.get("sales_growth_ttm")
    marks["profit_growth"] = marks.get("profit_growth_ttm")
    marks["interest_coverage"] = marks.get("interest_coverage_ttm")

    if total >= 85:
        q = "🟢 A+ EXCELLENT"
    elif total >= 70:
        q = "🟢 A GOOD QUALITY"
    elif total >= 50:
        q = "🟡 B AVERAGE"
    else:
        q = "🔴 C WEAK"
    return total, q, marks

def get_fundamental_analysis(symbol):
    clean_sym = str(symbol).upper().replace(".NS", "").replace(".BO", "").strip()

    metrics = {
        "market_cap": None,
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
        "promoter_pledge": None,
        "pledged_percentage": None,
        "fii_holding": None,
        "dii_holding": None,
        "piotroski_score": None,
        "sector": "N/A",
        "industry": "N/A",
        "cap_category": "SMALL CAP",
    }

    # 1. Base Sector / Industry from YFinance
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        info = ticker.info or {}
        if info:
            metrics["sector"] = info.get("sector") or "N/A"
            metrics["industry"] = info.get("industry") or metrics["sector"]
    except Exception:
        pass

    # 2. Extract Data using Persistent Shared Screener Session
    data = {}
    try:
        page = get_shared_screener_page()

        # Step A: Consolidated URL first
        cons_url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
        page.goto(cons_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        soup = BeautifulSoup(page.content(), "html.parser")
        top_ratios = soup.find("ul", id="top-ratios")

        # Step B: Standalone Fallback
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
            if sub and sub.find("a") and metrics["sector"] == "N/A":
                metrics["sector"] = sub.find("a").text.strip()
                if metrics["industry"] == "N/A":
                    metrics["industry"] = metrics["sector"]

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

    # Exact Field Mapping from Custom Box
    if data:
        metrics["market_cap"] = find_key(["market cap"])
        metrics["pe"] = find_key(["stock p/e", "p/e"])
        metrics["roce"] = find_key(["roce"])
        metrics["roe"] = find_key(["roe"])
        metrics["debt_to_equity"] = find_key(["debt to equity", "debt to eq"])
        metrics["sales_growth_ttm"] = find_key(["sales growth"])
        metrics["sales_growth_3y"] = find_key(["sales growth 3years", "sales growth 3yr", "sales growth 3yrs"])
        metrics["profit_growth_ttm"] = find_key(["profit growth"])
        metrics["profit_growth_3y"] = find_key(["profit var 3yrs", "profit var 3years"])
        metrics["opm"] = find_key(["opm"])
        metrics["interest_coverage_ttm"] = find_key(["int coverage", "interest coverage"])
        metrics["interest_coverage_fy"] = metrics["interest_coverage_ttm"]

        pio = find_key(["piotroski score", "piotroski"])
        metrics["piotroski_score"] = int(pio) if pio is not None else None

        pledge = find_key(["pledged percentage", "promoter pledge", "pledged"])
        metrics["pledged_percentage"] = pledge
        metrics["promoter_pledge"] = pledge

        metrics["promoter_holding"] = find_key(["promoter holding"])
        metrics["fii_holding"] = find_key(["fii holding"])
        metrics["dii_holding"] = find_key(["dii holding"])
        metrics["price_cagr_1y"] = find_key(["return over 1year", "return over 1 year"])
        metrics["price_cagr_3y"] = find_key(["return over 3years", "return over 3 years"])

    # YFinance Fallback for missing fields
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        info = ticker.info or {}
        if metrics["opm"] is None and info.get("operatingMargins"):
            metrics["opm"] = info["operatingMargins"] * 100
        if metrics["debt_to_equity"] is None and info.get("debtToEquity"):
            metrics["debt_to_equity"] = info["debtToEquity"] / 100
        if metrics["roe"] is None and info.get("returnOnEquity"):
            metrics["roe"] = info["returnOnEquity"] * 100
        if metrics["pe"] is None:
            metrics["pe"] = info.get("trailingPE") or info.get("forwardPE")
        if metrics["market_cap"] is None and info.get("marketCap"):
            metrics["market_cap"] = info["marketCap"] / 10000000
        if metrics["promoter_holding"] is None and info.get("heldPercentInsiders"):
            metrics["promoter_holding"] = info["heldPercentInsiders"] * 100
        if metrics["dii_holding"] is None and info.get("heldPercentInstitutions"):
            metrics["dii_holding"] = info["heldPercentInstitutions"] * 100
    except Exception:
        pass

    # Round Decimals
    for key in metrics:
        if key not in ["sector", "industry", "cap_category", "piotroski_score"] and metrics[key] is not None:
            metrics[key] = _clean(metrics[key], 2)

    # Market Cap Classification
    mc = metrics["market_cap"] or 0
    if mc >= 20000:
        metrics["cap_category"] = "LARGE CAP"
    elif mc >= 5000:
        metrics["cap_category"] = "MID CAP"
    else:
        metrics["cap_category"] = "SMALL CAP"

    score, quality, marks = _score(metrics)

    return {
        "available": True,
        "metrics": metrics,
        "marks": marks,
        "score": score,
        "quality": quality,
        "rejection_reasons": []
    }
