import os
import re
import requests
import yfinance as yf
from bs4 import BeautifulSoup

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

# ============================================================
# GK FUNDAMENTAL ENGINE — HYBRID (EMAIL LOGIN + MATH + YFINANCE)
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

# --- 1. EMAIL LOGIN ATTEMPT ---
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

def _key_point(soup, labels):
    clean_labels = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in labels]
    for element in soup.select("ul#top-ratios li") + soup.select("li, tr"):
        n = element.select_one(".name, th, td:nth-child(1)")
        v = element.select_one(".number, td:nth-child(2)")
        if not n or not v: continue
        clean_label = re.sub(r"[^a-z0-9]", "", n.get_text(separator=" ", strip=True).lower())
        if clean_label in clean_labels:
            return _num(v.get_text(" ", strip=True))
    return None

def _get_latest_table_value(soup, section_id, row_label):
    section = soup.find(id=section_id)
    if not section: return None
    clean_target = re.sub(r"[^a-z0-9]", "", row_label.lower())
    for tr in section.select("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) > 1:
            clean_cell_label = re.sub(r"[^a-z0-9]", "", cells[0].get_text(strip=True).lower())
            if clean_target in clean_cell_label:
                return _num(cells[-1].get_text(strip=True))
    return None

def _get_range_table_value(soup, header_text, row_text):
    clean_header = re.sub(r"[^a-z0-9]", "", header_text.lower())
    clean_row = re.sub(r"[^a-z0-9]", "", row_text.lower())
    for table in soup.select("table.ranges-table"):
        th = table.find("th")
        if th:
            th_clean = re.sub(r"[^a-z0-9]", "", th.get_text(strip=True).lower())
            if clean_header in th_clean:
                for tr in table.select("tr"):
                    cells = tr.find_all("td")
                    if len(cells) == 2:
                        cell_clean = re.sub(r"[^a-z0-9]", "", cells[0].get_text(strip=True).lower())
                        if clean_row in cell_clean:
                            return _num(cells[1].get_text(strip=True))
    return None

def _sector(soup):
    candidates = [a.get_text(" ", strip=True) for a in soup.select("div.company-links a, #peers a, a[href*='/screens/']")]
    return candidates[-1] if candidates else "Diversified"

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

    metrics = {k: None for k in ["market_cap", "pe", "roce", "roe", "debt_to_equity", "sales_growth_ttm", "sales_growth_3y", "profit_growth_ttm", "profit_growth_3y", "opm", "interest_coverage_ttm", "interest_coverage_fy", "price_cagr_1y", "price_cagr_3y", "promoter_holding", "promoter_pledge", "pledged_percentage", "fii_holding", "dii_holding", "piotroski_score", "high_52w", "low_52w"]}
    metrics["sector"] = "Diversified"
    metrics["cap_category"] = "⚪ SMALL CAP"

    if soup is None:
        return {"available": False, "metrics": metrics, "marks": {}, "score": "N/A", "quality": "N/A", "error": "Screener data unavailable", "rejection_reasons": []}

    # 1. SCREENER EXTRACTION & MATH FALLBACKS
    metrics["market_cap"] = _key_point(soup, ["market cap"])
    metrics["pe"] = _key_point(soup, ["stock p/e", "pe"])
    metrics["roce"] = _key_point(soup, ["roce"])
    metrics["roe"] = _key_point(soup, ["roe", "return onequity"])
    metrics["piotroski_score"] = _key_point(soup, ["piotroski score"])
    
    # Pledge extraction
    pledge = _key_point(soup, ["pledged percentage", "promoter pledge"])
    metrics["promoter_pledge"] = metrics["pledged_percentage"] = pledge

    # Debt to Equity (Math Fallback)
    de = _key_point(soup, ["debt to equity", "debt to eq"])
    if de is None:
        borrowings = _get_latest_table_value(soup, "balance-sheet", "borrowings") or 0
        eq = _get_latest_table_value(soup, "balance-sheet", "equity capital") or 0
        res = _get_latest_table_value(soup, "balance-sheet", "reserves") or 0
        if (eq + res) > 0: de = borrowings / (eq + res)
    metrics["debt_to_equity"] = de

    # OPM (Math Fallback from P&L)
    opm = _key_point(soup, ["opm", "opm %", "operating profit margin"])
    if opm is None:
        sales = _get_latest_table_value(soup, "profit-loss", "sales") or 1
        op = _get_latest_table_value(soup, "profit-loss", "operating profit") or 0
        if sales > 1: opm = (op / sales) * 100
    metrics["opm"] = opm

    # Interest Coverage (Math Fallback from P&L)
    ic = _key_point(soup, ["int coverage", "interest coverage", "interest coverage ratio"])
    if ic is None:
        op_profit = _get_latest_table_value(soup, "profit-loss", "operating profit") or 0
        interest = _get_latest_table_value(soup, "profit-loss", "interest")
        if interest and interest > 0: ic = op_profit / interest
    metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = ic

    # Growth & CAGR
    metrics["sales_growth_ttm"] = _key_point(soup, ["sales growth"]) or _get_range_table_value(soup, "compounded sales growth", "ttm")
    metrics["profit_growth_ttm"] = _key_point(soup, ["profit growth"]) or _get_range_table_value(soup, "compounded profit growth", "ttm")
    metrics["sales_growth_3y"] = _key_point(soup, ["sales growth 3years", "sales growth 3yrs"]) or _get_range_table_value(soup, "compounded sales growth", "3 years")
    metrics["profit_growth_3y"] = _key_point(soup, ["profit var 3yrs", "profit growth 3years"]) or _get_range_table_value(soup, "compounded profit growth", "3 years")

    metrics["price_cagr_1y"] = _key_point(soup, ["return over 1year", "return over 1 year"]) or _get_range_table_value(soup, "price cagr", "1 year")
    metrics["price_cagr_3y"] = _key_point(soup, ["return over 3years", "return over 3 years"]) or _get_range_table_value(soup, "price cagr", "3 years")

    # Shareholding
    metrics["promoter_holding"] = _key_point(soup, ["promoter holding"]) or _get_latest_table_value(soup, "shareholding", "promoters")
    metrics["fii_holding"] = _key_point(soup, ["fii holding"]) or _get_latest_table_value(soup, "shareholding", "fiis")
    metrics["dii_holding"] = _key_point(soup, ["dii holding"]) or _get_latest_table_value(soup, "shareholding", "diis")
    
    metrics["sector"] = _sector(soup)
    
    # 52W High/Low
    for element in soup.select("ul#top-ratios li"):
        n = element.select_one(".name")
        if n:
            label_clean = re.sub(r"[^a-z0-9]", "", n.get_text(separator=" ", strip=True).lower())
            if "highlow" in label_clean:
                numbers = element.find_all(class_="number")
                if len(numbers) >= 2:
                    metrics["high_52w"] = _num(numbers[0].get_text())
                    metrics["low_52w"] = _num(numbers[1].get_text())

    # 2. YFINANCE FALLBACK (For anything still missing)
    try:
        t = yf.Ticker(f"{symbol}.NS")
        info = t.info
        
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
    except:
        pass

    # 3. CLEANUP & SCORE
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
    
