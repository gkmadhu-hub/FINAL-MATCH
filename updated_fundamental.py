import requests
from bs4 import BeautifulSoup
import re


# -------------------------------------------------------------
# SAFE NUMBER PARSER
# -------------------------------------------------------------
def parse_number(text):
    """
    Converts Screener text such as:
    ₹1,23,456 Cr.
    18.2
    -14.6%
    into float safely.
    """
    if text is None:
        return None

    text = str(text).strip()

    # Remove commas, currency and percentage
    text = (
        text.replace(",", "")
            .replace("₹", "")
            .replace("%", "")
            .replace("Cr.", "")
            .replace("Cr", "")
            .strip()
    )

    # Find first valid numeric value
    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except (ValueError, TypeError):
        return None


# -------------------------------------------------------------
# SCREENER DATA
# -------------------------------------------------------------
def get_screener_data(clean_sym):

    url = f"https://www.screener.in/company/{clean_sym}/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    metrics = {
        "piotroski": None,
        "mcap": None,
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
        "pledged_percentage": None,
        "promoter_holding": None,
        "fii_holding": None,
        "dii_holding": None,
        "sector": None
    }

    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print(f"Screener HTTP {response.status_code} for {clean_sym}")
            return metrics

        soup = BeautifulSoup(response.content, "html.parser")

        # 1. TOP RATIOS
        ratios_div = soup.find("div", {"id": "top-ratios"})
        if ratios_div:
            for item in ratios_div.find_all("li"):
                name_elem = item.find("span", class_="name")
                value_elem = (
                    item.find("span", class_="number")
                    or item.find("span", class_="value")
                )

                if name_elem:
                    name = " ".join(name_elem.stripped_strings).strip().lower()
                else:
                    name = ""

                if value_elem:
                    raw_value = value_elem.get_text(" ", strip=True)
                else:
                    raw_value = item.get_text(" ", strip=True)
                    if name and raw_value.lower().startswith(name):
                        raw_value = raw_value[len(name):].strip()

                value = parse_number(raw_value)
                if value is None:
                    continue

                if "market capitalization" in name or "market cap" in name:
                    metrics["mcap"] = value
                elif "stock p/e" in name or name == "p/e" or "price to earning" in name:
                    metrics["pe"] = value
                elif "roce" in name or "return on capital employed" in name:
                    metrics["roce"] = value
                elif "roe" in name or "return on equity" in name:
                    metrics["roe"] = value
                elif "debt to equity" in name or "debt/equity" in name or "debt-equity" in name or "debt / equity" in name:
                    metrics["debt_to_equity"] = value
                elif "opm" in name or "operating profit margin" in name:
                    metrics["opm"] = value
                elif "piotroski" in name:
                    metrics["piotroski"] = value
                elif "interest coverage" in name or "int coverage" in name:
                    if "ttm" in name:
                        metrics["interest_coverage_ttm"] = value
                    elif "fy" in name or "year" in name or "annual" in name:
                        metrics["interest_coverage_fy"] = value
                    elif metrics["interest_coverage_ttm"] is None:
                        metrics["interest_coverage_ttm"] = value

        # 2. FULL PAGE TEXT & PATTERNS
        page_text = soup.get_text(" ", strip=True)

        promoter_patterns = [
            r"promoter holding\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"promoters?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"prom\.\s*hold\.\s*([0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in promoter_patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["promoter_holding"] = float(match.group(1))
                break

        fii_patterns = [
            r"fii holding\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"fiis?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"fii\s*hold\.\s*([0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in fii_patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["fii_holding"] = float(match.group(1))
                break

        dii_patterns = [
            r"dii holding\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"diis?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"dii\s*hold\.\s*([0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in dii_patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["dii_holding"] = float(match.group(1))
                break

        pledge_patterns = [
            r"pledged percentage\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"pledged\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            r"pledge\s*([0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in pledge_patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["pledged_percentage"] = float(match.group(1))
                break

        sales_patterns_3y = [
            r"sales growth.*?3\s*years?.*?([\-]?[0-9]+(?:\.[0-9]+)?)\s*%",
            r"sales.*?growth.*?3yr.*?([\-]?[0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in sales_patterns_3y:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["sales_growth_3y"] = float(match.group(1))
                break

        profit_patterns_3y = [
            r"profit growth.*?3\s*years?.*?([\-]?[0-9]+(?:\.[0-9]+)?)\s*%",
            r"profit.*?growth.*?3yr.*?([\-]?[0-9]+(?:\.[0-9]+)?)\s*%"
        ]
        for pattern in profit_patterns_3y:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                metrics["profit_growth_3y"] = float(match.group(1))
                break

        return metrics

    except Exception as e:
        print(f"Screener scraping error for {clean_sym}: {e}")
        return metrics


# -------------------------------------------------------------
# FUNDAMENTAL SCORE
# -------------------------------------------------------------
def calculate_100M_score(metrics):
    marks = {}
    score = 50.0

    pe = metrics.get("pe")
    if isinstance(pe, (int, float)):
        passed = 10 <= pe <= 45
        marks["pe"] = passed
        score += 8 if passed else -4

    roce = metrics.get("roce")
    if isinstance(roce, (int, float)):
        passed = roce > 15
        marks["roce"] = passed
        score += 8 if passed else -4

    roe = metrics.get("roe")
    if isinstance(roe, (int, float)):
        passed = roe > 15
        marks["roe"] = passed
        score += 8 if passed else -4

    de = metrics.get("debt_to_equity")
    if isinstance(de, (int, float)):
        passed = de < 1.0
        marks["debt_to_equity"] = passed
        score += 8 if passed else -8

    sg_ttm = metrics.get("sales_growth_ttm")
    sg_3y = metrics.get("sales_growth_3y")
    if isinstance(sg_ttm, (int, float)):
        passed = sg_ttm > 10
        marks["sales_growth_ttm"] = passed
        score += 8 if passed else -4
    elif isinstance(sg_3y, (int, float)):
        passed = sg_3y > 10
        marks["sales_growth_3y"] = passed
        score += 8 if passed else -4

    pg_ttm = metrics.get("profit_growth_ttm")
    pg_3y = metrics.get("profit_growth_3y")
    if isinstance(pg_ttm, (int, float)):
        passed = pg_ttm > 12
        marks["profit_growth_ttm"] = passed
        score += 8 if passed else -4
    elif isinstance(pg_3y, (int, float)):
        passed = pg_3y > 12
        marks["profit_growth_3y"] = passed
        score += 8 if passed else -4

    opm = metrics.get("opm")
    if isinstance(opm, (int, float)):
        passed = opm > 15
        marks["opm"] = passed
        score += 8 if passed else -4

    ic_ttm = metrics.get("interest_coverage_ttm")
    if isinstance(ic_ttm, (int, float)):
        passed = ic_ttm > 3.5
        marks["interest_coverage"] = passed
        score += 8 if passed else -4

    pledge = metrics.get("pledged_percentage")
    if isinstance(pledge, (int, float)):
        passed = pledge < 5.0
        marks["promoter_pledge"] = passed
        score += 10 if passed else -10

    score = max(0.0, min(100.0, score))

    if score >= 80:
        quality = "🟢 A+ SUPER STRONG"
    elif score >= 65:
        quality = "🟢 STRONG"
    elif score >= 50:
        quality = "🟡 MODERATE"
    else:
        quality = "🔴 WEAK"

    return score, quality, marks


# -------------------------------------------------------------
# FINAL FUNDAMENTAL ANALYSIS
# -------------------------------------------------------------
def get_fundamental_analysis(symbol):
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

    try:
        metrics = get_screener_data(clean_sym)
        score, quality, marks = calculate_100M_score(metrics)

        fundamental_keys = [
            "mcap", "pe", "roce", "roe", "debt_to_equity",
            "sales_growth_ttm", "sales_growth_3y", "profit_growth_ttm",
            "profit_growth_3y", "opm", "interest_coverage_ttm",
            "interest_coverage_fy", "promoter_holding", "fii_holding", "dii_holding"
        ]

        available = any(metrics.get(k) is not None for k in fundamental_keys)

        if not available:
            return {
                "available": False,
                "score": "N/A",
                "quality": "⚪ DATA UNAVAILABLE",
                "marks": {},
                "metrics": metrics,
                "rejections": []
            }

        return {
            "available": True,
            "score": round(score, 1),
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": []
        }

    except Exception as e:
        print(f"Fundamental analysis error for {clean_sym}: {e}")
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
    }
        
