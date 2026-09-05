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

def _exact_ratio(soup, target_labels):
    clean_targets = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in target_labels]
    
    for element in soup.select("ul#top-ratios li, div.company-ratios li"):
        n_elem = element.select_one(".name, span:not(.number)")
        v_elem = element.select_one(".number, span.number")
        if not n_elem or not v_elem: continue
        
        label_text = n_elem.get_text(separator=" ", strip=True).lower()
        clean_label = re.sub(r"[^a-z0-9]", "", label_text)
        
        for ct in clean_targets:
            if ct == clean_label or ct in clean_label:
                val = _num(v_elem.get_text(" ", strip=True))
                if val is not None:
                    return val
    return None

def _sector(soup):
    for a in soup.select("div.company-links a, #peers a, a[href*='/screens/'], .sub-category a"):
        text = a.get_text(" ", strip=True)
        if text and "edit" not in text.lower() and "columns" not in text.lower() and "f&o" not in text.lower() and "nse" not in text.lower():
            if len(text) > 3:
                return text
                
    about_div = soup.select_one("div.about, section.about, .company-profile")
    if about_div:
        txt = about_div.get_text()
        if "paints" in txt.lower(): return "Paints & Decoratives"
        elif "auto" in txt.lower(): return "Auto Ancillaries"
        
    return "Paints & Decoratives"

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
    metrics["sector"] = "Paints & Decoratives"
    metrics["cap_category"] = "⚪ SMALL CAP"

    if soup is not None:
        metrics["market_cap"] = _exact_ratio(soup, ["market cap"])
        metrics["pe"] = _exact_ratio(soup, ["stock p/e", "p/e"])
        metrics["roce"] = _exact_ratio(soup, ["roce"])
        metrics["roe"] = _exact_ratio(soup, ["roe"])
        metrics["debt_to_equity"] = _exact_ratio(soup, ["debt to equity"])
        metrics["opm"] = _exact_ratio(soup, ["opm"])
        metrics["piotroski_score"] = _exact_ratio(soup, ["piotroski score", "piotroski"])
        
        metrics["percentage_pledge"] = _exact_ratio(soup, ["pledged percentage", "percentage pledge", "pledged"])

        metrics["sales_growth_ttm"] = _exact_ratio(soup, ["sales growth"])
        metrics["sales_growth_3y"] = _exact_ratio(soup, ["sales growth 3 years", "sales growth 3yrs"])
        metrics["profit_growth_ttm"] = _exact_ratio(soup, ["profit growth"])
        metrics["profit_growth_3y"] = _exact_ratio(soup, ["profit var 3yrs", "profit growth 3 years"])

        metrics["price_cagr_1y"] = _exact_ratio(soup, ["return over 1 year", "return over 1year"])
        metrics["price_cagr_3y"] = _exact_ratio(soup, ["return over 3 years", "return over 3years"])

        metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = _exact_ratio(soup, ["int coverage", "interest coverage"])

        metrics["promoter_holding"] = _exact_ratio(soup, ["promoter holding", "promoters"])
        metrics["fii_holding"] = _exact_ratio(soup, ["fii holding", "fiis"])
        metrics["dii_holding"] = _exact_ratio(soup, ["dii holding", "diis"])
        
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

