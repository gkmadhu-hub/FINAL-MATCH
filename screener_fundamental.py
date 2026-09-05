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

def _get_top_ratio(soup, target_name):
    clean_target = re.sub(r"[^a-z0-9]", "", target_name.lower())
    for element in soup.select("ul#top-ratios li"):
        n = element.select_one(".name")
        v = element.select_one(".number")
        if not n or not v: continue
        label_text = n.get_text(separator=" ", strip=True).lower()
        if clean_target in re.sub(r"[^a-z0-9]", "", label_text):
            return _num(v.get_text(" ", strip=True))
    return None

def _get_table_row_value(soup, section_id, row_name):
    clean_target = re.sub(r"[^a-z0-9]", "", row_name.lower())
    section = soup.find(id=section_id)
    if not section:
        sections = soup.find_all("table")
    else:
        sections = [section, *section.find_all("table")]
        
    for sec in sections:
        for tr in sec.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) > 1:
                label = cells[0].get_text(strip=True).lower()
                if clean_target in re.sub(r"[^a-z0-9]", "", label):
                    for cell in reversed(cells[1:]):
                        val = _num(cell.get_text(strip=True))
                        if val is not None:
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
        metrics["market_cap"] = _get_top_ratio(soup, "market cap")
        metrics["pe"] = _get_top_ratio(soup, "stock p/e") or _get_top_ratio(soup, "p/e")
        metrics["roce"] = _get_top_ratio(soup, "roce")
        metrics["roe"] = _get_top_ratio(soup, "roe")
        
        # Exact Debt to Equity matching
        metrics["debt_to_equity"] = _get_top_ratio(soup, "debt to equity")
        
        metrics["opm"] = _get_top_ratio(soup, "opm") or _get_table_row_value(soup, "profit-loss", "opm %")
        metrics["piotroski_score"] = _get_top_ratio(soup, "piotroski score")
        metrics["percentage_pledge"] = _get_top_ratio(soup, "pledged percentage") or _get_top_ratio(soup, "pledged %")

        # Growth metrics
        metrics["sales_growth_ttm"] = _get_top_ratio(soup, "sales growth")
        metrics["profit_growth_ttm"] = _get_top_ratio(soup, "profit growth")
        metrics["sales_growth_3y"] = _get_top_ratio(soup, "sales growth 3years")
        metrics["profit_growth_3y"] = _get_top_ratio(soup, "profit var 3yrs") or _get_top_ratio(soup, "profit growth 3years")

        metrics["price_cagr_1y"] = _get_top_ratio(soup, "return over 1year")
        metrics["price_cagr_3y"] = _get_top_ratio(soup, "return over 3years")

        # Interest Coverage
        metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = _get_top_ratio(soup, "int coverage") or _get_top_ratio(soup, "interest coverage")

        # Shareholding Pattern matching
        metrics["promoter_holding"] = _get_top_ratio(soup, "promoter holding") or _get_table_row_value(soup, "shareholding", "promoters")
        metrics["fii_holding"] = _get_top_ratio(soup, "fii holding") or _get_table_row_value(soup, "shareholding", "fiis")
        metrics["dii_holding"] = _get_top_ratio(soup, "dii holding") or _get_table_row_value(soup, "shareholding", "diis")
        
        # 52W High Low
        for element in soup.select("ul#top-ratios li"):
            n = element.select_one(".name")
            if n and "highlow" in re.sub(r"[^a-z0-9]", "", n.get_text(strip=True).lower()):
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

