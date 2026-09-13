import os
import re
import requests
from bs4 import BeautifulSoup
import yfinance as yf

# ============================================================
# 🇮🇳 GK FUNDAMENTAL ENGINE — DIRECT HIGH-SPEED SESSION
# ============================================================

SCREENER_EMAIL = os.getenv("SCREENER_USERNAME", "bsbindurani@gmail.com")
SCREENER_PASS = os.getenv("SCREENER_PASSWORD", "cricket786")

_session = None

def get_screener_session():
    """Screener.in ಲಾಗಿನ್ ಸೆಷನ್ ರಚಿಸಿ ಕುಕ್ಕಿಗಳನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ"""
    global _session
    if _session is not None:
        return _session

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.screener.in/login/"
    })

    try:
        # ಮೊದಲು CSRF ಟೋಕನ್ ಪಡೆಯಲು ಲಾಗಿನ್ ಪೇಜ್ ಲೋಡ್ ಮಾಡುವುದು
        login_page = session.get("https://www.screener.in/login/", timeout=15)
        soup = BeautifulSoup(login_page.text, "html.parser")
        csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
        csrf_token = csrf_input["value"] if csrf_input else ""

        login_data = {
            "csrfmiddlewaretoken": csrf_token,
            "username": SCREENER_EMAIL,
            "password": SCREENER_PASS,
        }

        # ಲಾಗಿನ್ ರಿಕ್ವೆಸ್ಟ್ ಕಳುಹಿಸುವುದು
        resp = session.post("https://www.screener.in/login/", data=login_data, timeout=15)
        if "Logout" in resp.text or resp.status_code == 200:
            print("Screener direct session login successful!")
            _session = session
        else:
            print("Screener login response without logout flag, using direct session.")
            _session = session
    except Exception as e:
        print(f"Screener Login Error: {e}")
        _session = session

    return _session

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

    # 2. Screener Extraction (Super Fast Session)
    data = {}
    sector_found = "N/A"
    try:
        session = get_screener_session()
        
        # Consolidated ಚೆಕ್ ಮಾಡುವುದು
        url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
        res = session.get(url, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        top_ratios = soup.find("ul", id="top-ratios") or soup.find("ul", class_="company-ratios")

        # Consolidated ಇಲ್ಲದಿದ್ದರೆ Standalone ಪುಟ
        if not top_ratios:
            url = f"https://www.screener.in/company/{clean_sym}/"
            res = session.get(url, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            top_ratios = soup.find("ul", id="top-ratios") or soup.find("ul", class_="company-ratios")

        # Top Ratios (Custom login ratios) ಪಾರ್ಸ್ ಮಾಡುವುದು
        if top_ratios:
            for li in top_ratios.find_all("li"):
                name_elem = li.find("span", class_="name")
                val_elem = li.find("span", class_="number") or li.find("span", class_="value")
                if name_elem and val_elem:
                    k = name_elem.text.strip().lower()
                    v = val_elem.text.strip().replace(",", "").replace("%", "")
                    data[k] = v

        # Peers / Sector
        peers_sec = soup.find("section", id="peers")
        if peers_sec:
            sub = peers_sec.find("p", class_="sub")
            if sub and sub.find("a"):
                sector_found = sub.find("a").text.strip()

        # Compounded Sales/Profit Growth Tables (Fallback from bottom tables)
        for table in soup.find_all("table", class_="ranges-table"):
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) >= 2:
                    k = tds[0].text.strip().lower()
                    v = tds[1].text.strip().replace("%", "").replace(",", "")
                    if "sales growth" in k or "compounded sales" in k:
                        if "3 years" in k and not data.get("sales growth 3years"):
                            data["sales growth 3years"] = v
                        elif "ttm" in k and not data.get("sales growth"):
                            data["sales growth"] = v
                    if "profit growth" in k or "compounded profit" in k:
                        if "3 years" in k and not data.get("profit var 3yrs"):
                            data["profit var 3yrs"] = v
                        elif "ttm" in k and not data.get("profit growth"):
                            data["profit growth"] = v

        print(f"Extracted {clean_sym}: {len(data)} metrics parsed from Screener.")

    except Exception as e:
        print(f"Error scraping Screener for {clean_sym}: {e}")

    if sector_found != "N/A" and metrics["sector"] == "N/A":
        metrics["sector"] = sector_found
        if metrics["industry"] == "N/A":
            metrics["industry"] = sector_found

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

    # ಅಸಲಿ ರೇಷಿಯೋಗಳನ್ನು ಮ್ಯಾಪ್ ಮಾಡುವುದು
    if data:
        metrics["market_cap"] = find_key(["market cap"])
        metrics["pe"] = find_key(["stock p/e", "p/e"])
        metrics["roce"] = find_key(["roce"])
        metrics["roe"] = find_key(["roe", "return on equity"])
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

        metrics["promoter_holding"] = find_key(["promoter holding", "promoters"])
        metrics["fii_holding"] = find_key(["fii holding", "fiis"])
        metrics["dii_holding"] = find_key(["dii holding", "diis"])
        metrics["price_cagr_1y"] = find_key(["return over 1year", "return over 1 year", "1 year cagr"])
        metrics["price_cagr_3y"] = find_key(["return over 3years", "return over 3 years", "3 year cagr"])

    # 3. YFinance Fallback strictly for missing items
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

    for key in metrics:
        if key not in ["sector", "industry", "cap_category", "piotroski_score"] and metrics[key] is not None:
            metrics[key] = _clean(metrics[key], 2)

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
    
