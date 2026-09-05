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

def _extract_all_ratios(soup):
    ratios = {}
    # Scrape all list items inside top-ratios or company-ratios
    for element in soup.select("ul#top-ratios li, div.company-ratios li"):
        n_elem = element.select_one(".name, span:not(.number)")
        v_elem = element.select_one(".number, span.number")
        if n_elem and v_elem:
            label = n_elem.get_text(separator=" ", strip=True).lower()
            clean_key = re.sub(r"[^a-z0-9]", "", label)
            val = _num(v_elem.get_text(" ", strip=True))
            if clean_key and val is not None:
                ratios[clean_key] = val
    return ratios

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
        r = _extract_all_ratios(soup)
        
        metrics["market_cap"] = r.get("marketcap")
        metrics["pe"] = r.get("stockpe") or r.get("pe")
        metrics["roce"] = r.get("roce")
        metrics["roe"] = r.get("roe")
        metrics["debt_to_equity"] = r.get("debttoequity") or r.get("debtoequity")
        metrics["opm"] = r.get("opm")
        metrics["piotroski_score"] = r.get("piotroskiscore") or r.get("piotroski")
        metrics["percentage_pledge"] = r.get("pledgedpercentage") or r.get("percentagepledge") or r.get("pledged")

        metrics["sales_growth_ttm"] = r.get("salesgrowth")
        metrics["sales_growth_3y"] = r.get("salesgrowth3years") or r.get("salesgrowth3yrs")
        metrics["profit_growth_ttm"] = r.get("profitgrowth")
        metrics["profit_growth_3y"] = r.get("profitvar3yrs") or r.get("profitgrowth3years")

        metrics["price_cagr_1y"] = r.get("returnover1year") or r.get("returnover1yr")
        metrics["price_cagr_3y"] = r.get("returnover3years") or r.get("returnover3yrs")

        metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = r.get("intcoverage") or r.get("interestcoverage")

        metrics["promoter_holding"] = r.get("promoterholding") or r.get("promoters")
        metrics["fii_holding"] = r.get("fiiholding") or r.get("fii")
        metrics["dii_holding"] = r.get("diiholding") or r.get("dii")
        
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
    
