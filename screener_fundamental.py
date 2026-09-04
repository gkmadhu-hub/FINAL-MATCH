import os
import re
import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
except ImportError:
    cloudscraper = None


# ============================================================
# 🇮🇳 GK FUNDAMENTAL ENGINE — 100% PURE ORIGINAL DATA
# ============================================================

def _num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").replace("₹", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    return round(float(m.group()), 4) if m else None


def _clean(v, digits=2):
    if v is None:
        return None
    return round(float(v), digits)


def _get_session():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    if cloudscraper:
        try:
            return cloudscraper.create_scraper(
                browser={
                    "browser": "chrome",
                    "platform": "windows",
                    "mobile": False,
                }
            ), headers
        except Exception:
            pass

    return requests.Session(), headers


def _fetch_screener(symbol):
    session, headers = _get_session()

    urls = [
        f"https://www.screener.in/company/{symbol}/consolidated/",
        f"https://www.screener.in/company/{symbol}/",
    ]

    for url in urls:
        try:
            r = session.get(
                url,
                headers=headers,
                timeout=25,
                allow_redirects=True,
            )
            if r.status_code == 200 and ("Market Cap" in r.text or "market cap" in r.text.lower()):
                return BeautifulSoup(r.text, "html.parser")
        except Exception:
            continue

    return None


def _key_point(soup, labels):
    labels = [x.lower().strip() for x in labels]

    # Robust scanning across all list items and table rows
    for element in soup.select("li, tr"):
        name_elem = element.select_one(".name, th, td:nth-child(1)")
        number_elem = element.select_one(".number, td:nth-child(2)")

        if not name_elem or not number_elem:
            continue

        label = re.sub(
            r"\s+",
            " ",
            name_elem.get_text(" ", strip=True).lower()
        ).strip()

        for wanted in labels:
            if wanted == label or wanted in label:
                value = _num(
                    number_elem.get_text(" ", strip=True)
                )
                if value is not None:
                    return value

    return None


def _pnl_cagr(soup, wanted_year):
    section = soup.find(id="profit-loss")
    if not section:
        return None

    table = section.find("table")
    if not table:
        return None

    headers = []
    for tr in table.select("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        row_text = [
            c.get_text(" ", strip=True)
            for c in cells
        ]

        if any(
            wanted_year.lower() in x.lower()
            for x in row_text
        ):
            headers = row_text
            break

    for tr in table.select("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        label = cells[0].get_text(
            " ",
            strip=True
        ).lower()

        if "stock price cagr" not in label:
            continue

        values = [
            _num(c.get_text(" ", strip=True))
            for c in cells[1:]
        ]

        for i, h in enumerate(headers[1:]):
            if wanted_year.lower() in h.lower():
                return values[i] if i < len(values) else None

        if "3 year" in wanted_year.lower() and len(values) >= 3:
            return values[2]

        if "1 year" in wanted_year.lower() and len(values) >= 4:
            return values[3]

    return None


def _sector(soup):
    candidates = []

    for a in soup.select(
        "div.company-links a, "
        "#peers a, "
        "a[href*='/screens/']"
    ):
        txt = a.get_text(" ", strip=True)
        if txt and len(txt) > 2:
            candidates.append(txt)

    if candidates:
        return candidates[-1]

    return "Diversified"


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

    marks = {}
    total = 0

    for key, (weight, rule) in rules.items():
        value = m.get(key)

        if value is None:
            marks[key] = None
        else:
            marks[key] = bool(rule(value))
            if marks[key]:
                total += weight

    # Aliases for app.py compatibility
    marks["sales_growth"] = marks.get("sales_growth_ttm")
    marks["profit_growth"] = marks.get("profit_growth_ttm")
    marks["interest_coverage"] = marks.get("interest_coverage_ttm")

    if total >= 85:
        quality = "🟢 A+ EXCELLENT"
    elif total >= 70:
        quality = "🟢 A GOOD QUALITY"
    elif total >= 50:
        quality = "🟡 B AVERAGE"
    else:
        quality = "🔴 C WEAK"

    return total, quality, marks


def get_fundamental_analysis(symbol):
    symbol = (
        str(symbol)
        .upper()
        .replace(".NS", "")
        .strip()
    )

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
        "sector": "Diversified",
        "cap_category": "⚪ SMALL CAP",
    }

    soup = _fetch_screener(symbol)

    if soup is None:
        return {
            "available": False,
            "metrics": metrics,
            "marks": {},
            "score": "N/A",
            "quality": "N/A",
            "error": "Screener data unavailable",
        }

    metrics["market_cap"] = _key_point(soup, ["market cap"])
    metrics["pe"] = _key_point(soup, ["stock p/e", "p/e"])
    metrics["roce"] = _key_point(soup, ["roce"])
    metrics["roe"] = _key_point(soup, ["roe"])
    metrics["debt_to_equity"] = _key_point(soup, ["debt to equity", "debt to eq"])
    metrics["profit_growth_ttm"] = _key_point(soup, ["profit growth"])
    metrics["sales_growth_ttm"] = _key_point(soup, ["sales growth"])
    metrics["sales_growth_3y"] = _key_point(
        soup, ["sales growth 3years", "sales growth 3 years", "sales growth 3yrs"]
    )
    metrics["profit_growth_3y"] = _key_point(
        soup, ["profit var 3yrs", "profit var 3 years", "profit var 3y"]
    )
    metrics["opm"] = _key_point(soup, ["opm"])

    int_cov = _key_point(soup, ["int coverage", "interest coverage"])
    metrics["interest_coverage_ttm"] = int_cov
    metrics["interest_coverage_fy"] = int_cov

    metrics["piotroski_score"] = _key_point(soup, ["piotroski score"])

    pledge = _key_point(soup, ["pledged percentage", "promoter pledge", "pledged %"])
    metrics["promoter_pledge"] = pledge
    metrics["pledged_percentage"] = pledge

    metrics["promoter_holding"] = _key_point(soup, ["promoter holding"])
    metrics["fii_holding"] = _key_point(soup, ["fii holding"])
    metrics["dii_holding"] = _key_point(soup, ["dii holding"])

    metrics["price_cagr_1y"] = _pnl_cagr(soup, "1 Year")
    metrics["price_cagr_3y"] = _pnl_cagr(soup, "3 Years")

    for key in list(metrics.keys()):
        if key not in ["sector", "cap_category"] and metrics[key] is not None:
            metrics[key] = _clean(metrics[key], 2)

    mc = metrics["market_cap"] or 0
    if mc >= 20000:
        metrics["cap_category"] = "🟢 LARGE CAP"
    elif mc >= 5000:
        metrics["cap_category"] = "🟡 MID CAP"
    else:
        metrics["cap_category"] = "⚪ SMALL CAP"

    metrics["sector"] = _sector(soup)
    score, quality, marks = _score(metrics)

    return {
        "available": True,
        "metrics": metrics,
        "marks": marks,
        "score": score,
        "quality": quality,
        "rejection_reasons": [],
    }
