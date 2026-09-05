import os
import re
import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

# ============================================================
# GK FUNDAMENTAL ENGINE — PURE SCREENER (AUTHENTIC DATA)
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
            if r.status_code == 200 and ("Market Cap" in r.text or "market cap" in r.text):
                return BeautifulSoup(r.text, "html.parser")
        except: continue
    return None

def _find_ratio(soup, possible_names):
    # Search every list item and table row in the entire document for exact text matches
    target_names = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in possible_names]
    
    for element in soup.select("li, tr, div.flex"):
        text = element.get_text(separator=" ", strip=True)
        # Look for name and number inside the element
        parts = element.find_all(class_=["name", "number", "span"])
        
        # General text matching
        elem_clean = re.sub(r"[^a-z0-9]", "", text.lower())
        for tn in target_names:
            if elem_clean.startswith(tn) or tn in elem_clean:
                # Extract numbers from this element
                nums = re.findall(r"[-+]?\d[\d,\.]*", text)
                if nums:
                    # Filter out the label if it contains numbers, take the last numeric value
                    for num_str in reversed(nums):
                        val = _num(num_str)
                        if val is not None:
                            return val
    return None

def _sector(soup):
    for a in soup.select("div.company-links a, #peers a, a[href*='/screens/'], .sub-category a"):
        text = a.get_text(" ", strip=True)
        if text and "edit" not in text.lower() and "columns" not in text.lower() and "f&o" not in text.lower() and "nse" not in text.lower():
            if len(text) > 3:
                return text
    return "Consumer Discretionary"

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
    metrics["sector"] = "Consumer Discretionary"
    metrics["cap_category"] = "⚪ SMALL CAP"

    if soup is not None:
        metrics["market_cap"] = _find_ratio(soup, ["Market Cap"])
        metrics["pe"] = _find_ratio(soup, ["Stock P/E", "P/E"])
        metrics["roce"] = _find_ratio(soup, ["ROCE"])
        metrics["roe"] = _find_ratio(soup, ["ROE"])
        metrics["debt_to_equity"] = _find_ratio(soup, ["Debt to equity", "Debt to eq"])
        metrics["opm"] = _find_ratio(soup, ["OPM"])
        metrics["piotroski_score"] = _find_ratio(soup, ["Piotroski score"])
        metrics["percentage_pledge"] = _find_ratio(soup, ["Pledged percentage", "Percentage pledge"])

        metrics["sales_growth_ttm"] = _find_ratio(soup, ["Sales growth"])
        metrics["sales_growth_3y"] = _find_ratio(soup, ["Sales growth 3Years", "Sales growth 3 years"])
        metrics["profit_growth_ttm"] = _find_ratio(soup, ["Profit growth"])
        metrics["profit_growth_3y"] = _find_ratio(soup, ["Profit Var 3yrs", "Profit growth 3 years"])

        metrics["price_cagr_1y"] = _find_ratio(soup, ["Return over 1year", "Price CAGR 1 year"])
        metrics["price_cagr_3y"] = _find_ratio(soup, ["Return over 3years", "Price CAGR 3 years"])

        metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = _find_ratio(soup, ["Int Coverage", "Interest Coverage"])

        metrics["promoter_holding"] = _find_ratio(soup, ["Promoter holding"])
        metrics["fii_holding"] = _find_ratio(soup, ["FII holding"])
        metrics["dii_holding"] = _find_ratio(soup, ["DII holding"])
        
        sec = _sector(soup)
        if sec and "edit" not in sec.lower():
            metrics["sector"] = sec
        
        for element in soup.select("ul#top-ratios li, div.company-ratios li"):
            n = element.select_one(".name, span")
            if n:
                label_clean = re.sub(r"[^a-z0-9]", "", n.get_text(separator=" ", strip=True).lower())
                if "highlow" in label_clean:
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

