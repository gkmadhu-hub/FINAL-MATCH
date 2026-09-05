import os
import re
import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

# ============================================================
# 🇮🇳 GK FUNDAMENTAL ENGINE — PURE SCREENER (AUTHENTIC DATA)
# ============================================================

SCREENER_EMAIL = "bsbindurani@gmail.com"
SCREENER_PASS = "cricket786"

_GLOBAL_SESSION = None

def _num(v):
    if v is None: return None
    s = str(v).replace(",", "").replace("₹", "").replace("%", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None

def _clean(v, digits=2):
    if v is None: return None
    return round(float(v), digits)

# --- 1. SCREENER LOGIN ---
def _get_authenticated_session():
    global _GLOBAL_SESSION
    if _GLOBAL_SESSION is not None:
        return _GLOBAL_SESSION

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.screener.in/login/"
    }

    session = cloudscraper.create_scraper() if cloudscraper else requests.Session()
    session.headers.update(headers)
    
    try:
        login_url = "https://www.screener.in/login/"
        r = session.get(login_url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf_tag = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if csrf_tag:
            payload = {
                'csrfmiddlewaretoken': csrf_tag.get('value'),
                'username': SCREENER_EMAIL,
                'password': SCREENER_PASS,
                'next': '/'
            }
            session.post(login_url, data=payload, timeout=15)
    except: pass
        
    _GLOBAL_SESSION = session
    return session

def _fetch_screener(symbol):
    session = _get_authenticated_session()
    urls = [f"https://www.screener.in/company/{symbol}/consolidated/", f"https://www.screener.in/company/{symbol}/"]
    for url in urls:
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 200 and "Market Cap" in r.text:
                return BeautifulSoup(r.text, "html.parser")
        except: continue
    return None

def _top_ratio_value(soup, labels):
    clean_labels = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in labels]
    for element in soup.select("ul#top-ratios li, div.company-ratios li, .flex-table li"):
        n = element.select_one(".name")
        v = element.select_one(".number")
        if not n: continue
        label_text = n.get_text(separator=" ", strip=True).lower()
        clean_label = re.sub(r"[^a-z0-9]", "", label_text)
        if clean_label in clean_labels:
            if v:
                val = _num(v.get_text(" ", strip=True))
                if val is not None: return val
            nums = element.find_all(class_="number")
            for num in nums:
                val = _num(num.get_text())
                if val is not None: return val
    return None

def _get_compounded_growth(soup, section_name, row_name):
    clean_sec = re.sub(r"[^a-z0-9]", "", section_name.lower())
    clean_row = re.sub(r"[^a-z0-9]", "", row_name.lower())
    
    for card in soup.select("div.card, div.flex-row, section, div"):
        txt = card.get_text(separator=" ").lower()
        if clean_sec in re.sub(r"[^a-z0-9]", "", txt):
            for tr in card.select("tr, li"):
                row_txt = tr.get_text(separator=" ").lower()
                if clean_row in re.sub(r"[^a-z0-9]", "", row_txt):
                    nums = tr.find_all(class_="number") or tr.find_all("span") or tr.find_all("td")
                    for num in reversed(nums):
                        val = _num(num.get_text())
                        if val is not None: return val
    return None

def _get_shareholding(soup, holder_name):
    clean_holder = re.sub(r"[^a-z0-9]", "", holder_name.lower())
    section = soup.find(id="shareholding") or soup.find(id="quarters") or soup.select_one(".shareholding-table")
    
    for elem in soup.select("tr, div, section"):
        txt = elem.get_text(separator=" ").lower()
        if clean_holder in re.sub(r"[^a-z0-9]", "", txt):
            nums = elem.find_all(class_="number") or elem.find_all("td") or elem.find_all("span")
            for num in reversed(nums):
                val = _num(num.get_text())
                if val is not None and val <= 100:  # Holding percentage cannot exceed 100
                    return val
    return None

def _sector(symbol):
    sectors = {
        "ASIANPAINT": "Paints / Home Decor",
        "TEGA": "Abrasives & Industrial Products",
        "GRAVITA": "Metal - Non Ferrous / Recycling",
        "TITAGARH": "Heavy Engineering / Railways",
        "WABAG": "Water Treatment / Infrastructure"
    }
    return sectors.get(symbol.upper(), "Paints / Home Decor")

def _score(m):
    rules = {
        "profit_growth_ttm": (15, lambda x: x > 12), "roce": (15, lambda x: x > 15),
        "debt_to_equity": (15, lambda x: x < 1), "roe": (12, lambda x: x > 15),
        "sales_growth_ttm": (12, lambda x: x > 10), "opm": (12, lambda x: x > 15),
        "pe": (10, lambda x: 10 <= x <= 45), "interest_coverage_ttm": (9, lambda x: x > 3.5),
    }
    marks, total = {}, 0
    for key, (weight, rule) in rules.items():
        value = m.get(key)
        marks[key] = bool(rule(value)) if value is not None else None
        if marks[key]: total += weight

    marks["sales_growth"] = marks.get("sales_growth_ttm")
    marks["profit_growth"] = marks.get("profit_growth_ttm")
    marks["interest_coverage"] = marks.get("interest_coverage_ttm")

    if total >= 85: q = "🟢 A+ EXCELLENT"
    elif total >= 70: q = "🟢 A GOOD QUALITY"
    elif total >= 50: q = "🟡 B AVERAGE"
    else: q = "🔴 C WEAK"
    return total, q, marks

def get_fundamental_analysis(symbol):
    symbol = str(symbol).upper().replace(".NS", "").strip()
    soup = _fetch_screener(symbol)

    metrics = {k: None for k in ["market_cap", "pe", "roce", "roe", "debt_to_equity", "sales_growth_ttm", "sales_growth_3y", "profit_growth_ttm", "profit_growth_3y", "opm", "interest_coverage_ttm", "interest_coverage_fy", "price_cagr_1y", "price_cagr_3y", "promoter_holding", "percentage_pledge", "fii_holding", "dii_holding", "piotroski_score", "high_52w", "low_52w"]}
    metrics["sector"] = _sector(symbol)
    metrics["cap_category"] = "⚪ SMALL CAP"

    if soup is not None:
        metrics["market_cap"] = _top_ratio_value(soup, ["market cap"])
        metrics["pe"] = _top_ratio_value(soup, ["stock p/e", "p/e"])
        metrics["roce"] = _top_ratio_value(soup, ["roce"])
        metrics["roe"] = _top_ratio_value(soup, ["roe"])
        metrics["debt_to_equity"] = _top_ratio_value(soup, ["debt to equity", "debt to eq"])
        
        metrics["opm"] = _top_ratio_value(soup, ["opm"])
        metrics["piotroski_score"] = _top_ratio_value(soup, ["piotroski score"])
        metrics["percentage_pledge"] = _top_ratio_value(soup, ["pledged percentage", "pledged %", "promoter pledge"])

        # Sales Growth
        metrics["sales_growth_ttm"] = _top_ratio_value(soup, ["sales growth"]) or _get_compounded_growth(soup, "Compounded Sales Growth", "TTM")
        metrics["sales_growth_3y"] = _top_ratio_value(soup, ["sales growth 3years", "sales growth 3yrs"]) or _get_compounded_growth(soup, "Compounded Sales Growth", "3 Years")
        
        # Profit Growth
        metrics["profit_growth_ttm"] = _top_ratio_value(soup, ["profit growth"]) or _get_compounded_growth(soup, "Compounded Profit Growth", "TTM")
        metrics["profit_growth_3y"] = _top_ratio_value(soup, ["profit var 3yrs", "profit growth 3years"]) or _get_compounded_growth(soup, "Compounded Profit Growth", "3 Years")

        # CAGR
        metrics["price_cagr_1y"] = _top_ratio_value(soup, ["return over 1year"]) or _get_compounded_growth(soup, "Stock Price CAGR", "1 Year")
        metrics["price_cagr_3y"] = _top_ratio_value(soup, ["return over 3years"]) or _get_compounded_growth(soup, "Stock Price CAGR", "3 Years")

        metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = _top_ratio_value(soup, ["int coverage", "interest coverage"])
        
        # Shareholding
        metrics["promoter_holding"] = _top_ratio_value(soup, ["promoter holding"]) or _get_shareholding(soup, "Promoters")
        metrics["fii_holding"] = _top_ratio_value(soup, ["fii holding"]) or _get_shareholding(soup, "FIIs")
        metrics["dii_holding"] = _top_ratio_value(soup, ["dii holding"]) or _get_shareholding(soup, "DIIs")
        
        for element in soup.select("li, tr"):
            n = element.select_one(".name, th")
            if n and "highlow" in re.sub(r"[^a-z0-9]", "", n.get_text().lower()):
                numbers = element.find_all(class_="number")
                if len(numbers) >= 2:
                    metrics["high_52w"] = _num(numbers[0].get_text())
                    metrics["low_52w"] = _num(numbers[1].get_text())

    for key in metrics:
        if key not in ["sector", "cap_category"] and metrics[key] is not None:
            metrics[key] = _clean(metrics[key], 2)

    mc = metrics["market_cap"] or 0
    if mc >= 20000: metrics["cap_category"] = "🟢 LARGE CAP"
    elif mc >= 5000: metrics["cap_category"] = "🟡 MID CAP"
    else: metrics["cap_category"] = "⚪ SMALL CAP"

    score, quality, marks = _score(metrics)

    return {
        "available": True, 
        "metrics": metrics, 
        "marks": marks, 
        "score": score, 
        "quality": quality,
        "rejection_reasons": []
        }
        
