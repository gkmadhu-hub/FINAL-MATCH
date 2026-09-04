import os
import re
import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

# ============================================================
# 🇮🇳 GK FUNDAMENTAL ENGINE — MATH MAGIC (NO LOGIN REQUIRED)
# ============================================================

def _num(v):
    if v is None: return None
    s = str(v).replace(",", "").replace("₹", "").replace("%", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return round(float(m.group()), 4) if m else None

def _clean(v, digits=2):
    if v is None: return None
    return round(float(v), digits)

def _get_session():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if cloudscraper:
        try: return cloudscraper.create_scraper(), headers
        except: pass
    return requests.Session(), headers

def _fetch_screener(symbol):
    session, headers = _get_session()
    urls = [f"https://www.screener.in/company/{symbol}/consolidated/", f"https://www.screener.in/company/{symbol}/"]
    for url in urls:
        try:
            r = session.get(url, headers=headers, timeout=20)
            if r.status_code == 200 and "Market Cap" in r.text:
                return BeautifulSoup(r.text, "html.parser")
        except: continue
    return None

def _key_point(soup, labels):
    labels = [x.lower().strip() for x in labels]
    for element in soup.select("li, tr"):
        n = element.select_one(".name, th, td:nth-child(1)")
        v = element.select_one(".number, td:nth-child(2)")
        if not n or not v: continue
        label = re.sub(r"\s+", " ", n.get_text(" ", strip=True).lower()).strip()
        for wanted in labels:
            if wanted == label or wanted in label:
                return _num(v.get_text(" ", strip=True))
    return None

def _get_latest_table_value(soup, section_id, row_label):
    section = soup.find(id=section_id)
    if not section: return None
    for tr in section.select("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) > 1:
            label = cells[0].get_text(strip=True).lower()
            if row_label.lower() in label:
                return _num(cells[-1].get_text(strip=True))
    return None

def _get_range_table_value(soup, header_text, row_text):
    for table in soup.select("table.ranges-table"):
        th = table.find("th")
        if th and header_text.lower() in th.get_text(strip=True).lower():
            for tr in table.select("tr"):
                cells = tr.find_all("td")
                if len(cells) == 2:
                    if row_text.lower() in cells[0].get_text(strip=True).lower():
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

    metrics = {k: None for k in ["market_cap", "pe", "roce", "roe", "debt_to_equity", "sales_growth_ttm", "sales_growth_3y", "profit_growth_ttm", "profit_growth_3y", "opm", "interest_coverage_ttm", "interest_coverage_fy", "price_cagr_1y", "price_cagr_3y", "promoter_holding", "promoter_pledge", "pledged_percentage", "fii_holding", "dii_holding", "piotroski_score"]}
    metrics["sector"] = "Diversified"
    metrics["cap_category"] = "⚪ SMALL CAP"

    if soup is None:
        return {"available": False, "metrics": metrics, "marks": {}, "score": "N/A", "quality": "N/A", "error": "Screener data unavailable", "rejection_reasons": []}

    # 1. Basic Top Data (Always Visible)
    metrics["market_cap"] = _key_point(soup, ["market cap"])
    metrics["pe"] = _key_point(soup, ["stock p/e", "p/e"])
    metrics["roce"] = _key_point(soup, ["roce"])
    metrics["roe"] = _key_point(soup, ["roe"])
    metrics["piotroski_score"] = _key_point(soup, ["piotroski score"])
    
    # Pledged Percentage (Fallback to 0.00 if hidden)
    pledge = _key_point(soup, ["pledged percentage", "promoter pledge"])
    metrics["promoter_pledge"] = metrics["pledged_percentage"] = pledge if pledge is not None else 0.00

    # 2. CA LOGIC: OPM Calculation
    opm = _key_point(soup, ["opm"])
    if opm is None:
        sales = _get_latest_table_value(soup, "profit-loss", "sales") or 1
        op = _get_latest_table_value(soup, "profit-loss", "operating profit") or 0
        if sales > 1: opm = (op / sales) * 100
    metrics["opm"] = opm

    # 3. SHAREHOLDING
    metrics["promoter_holding"] = _key_point(soup, ["promoter holding"]) or _get_latest_table_value(soup, "shareholding", "promoters")
    metrics["fii_holding"] = _key_point(soup, ["fii holding"]) or _get_latest_table_value(soup, "shareholding", "fiis")
    metrics["dii_holding"] = _key_point(soup, ["dii holding"]) or _get_latest_table_value(soup, "shareholding", "diis")

    # 4. CA LOGIC: Debt to Equity Calculation
    de = _key_point(soup, ["debt to equity", "debt to eq"])
    if de is None:
        borrowings = _get_latest_table_value(soup, "balance-sheet", "borrowings") or 0
        eq = _get_latest_table_value(soup, "balance-sheet", "equity capital") or 0
        res = _get_latest_table_value(soup, "balance-sheet", "reserves") or 0
        if (eq + res) > 0: de = borrowings / (eq + res)
    metrics["debt_to_equity"] = de

    # 5. CA LOGIC: Interest Coverage Calculation
    ic = _key_point(soup, ["int coverage", "interest coverage"])
    if ic is None:
        op_profit = _get_latest_table_value(soup, "profit-loss", "operating profit") or 0
        interest = _get_latest_table_value(soup, "profit-loss", "interest")
        if interest and interest > 0: ic = op_profit / interest
    metrics["interest_coverage_ttm"] = metrics["interest_coverage_fy"] = ic

    # 6. GROWTH TTM
    metrics["sales_growth_ttm"] = _key_point(soup, ["sales growth"]) or _get_range_table_value(soup, "sales growth", "ttm")
    metrics["profit_growth_ttm"] = _key_point(soup, ["profit growth"]) or _get_range_table_value(soup, "profit growth", "ttm")
    metrics["sales_growth_3y"] = _key_point(soup, ["sales growth 3years", "sales growth 3yrs"]) or _get_range_table_value(soup, "sales growth", "3 years")
    metrics["profit_growth_3y"] = _key_point(soup, ["profit var 3yrs"]) or _get_range_table_value(soup, "profit growth", "3 years")

    # Clean up decimals to exactly 2 points like Screener
    for key in metrics:
        if key not in ["sector", "cap_category"] and metrics[key] is not None:
            metrics[key] = _clean(metrics[key], 2)

    # Cap Category
    mc = metrics["market_cap"] or 0
    if mc >= 20000: metrics["cap_category"] = "🟢 LARGE CAP"
    elif mc >= 5000: metrics["cap_category"] = "🟡 MID CAP"
    else: metrics["cap_category"] = "⚪ SMALL CAP"

    metrics["sector"] = _sector(soup)
    score, quality, marks = _score(metrics)

    return {
        "available": True, 
        "metrics": metrics, 
        "marks": marks, 
        "score": score, 
        "quality": quality,
        "rejection_reasons": []
  }

