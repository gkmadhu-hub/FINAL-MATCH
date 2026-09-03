import os
import re
import requests
import yfinance as yf
from bs4 import BeautifulSoup

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# Screener Login Credentials
SCREENER_USER = os.getenv("SCREENER_USERNAME", "bsbindurani@gmail.com")
SCREENER_PASS = os.getenv("SCREENER_PASSWORD", "cricket786")

def get_screener_session():
    if HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
    else:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        })

    try:
        login_url = "https://www.screener.in/login/"
        res = session.get(login_url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        csrf_token = soup.find("input", {"name": "csrfmiddlewaretoken"})

        if csrf_token:
            payload = {
                "username": SCREENER_USER,
                "password": SCREENER_PASS,
                "csrfmiddlewaretoken": csrf_token["value"],
            }
            headers = {
                "Referer": login_url,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            }
            session.post(login_url, data=payload, headers=headers, timeout=10)
    except Exception:
        pass

    return session

screener_session = get_screener_session()

def get_screener_data(symbol):
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

    metrics = {
        "market_cap": None,
        "cap_category": "N/A",
        "sector": "N/A",
        "industry": "N/A",
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
        "promoter_holding": None,
        "pledged_percentage": None,
        "fii_holding": None,
        "dii_holding": None,
        "piotroski": None,
    }

    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/",
    ]

    for url in urls:
        try:
            res = screener_session.get(url, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")

                # Sector info
                peers_sec = soup.find("section", {"id": "peers"})
                if peers_sec:
                    p_links = peers_sec.find_all("a", href=re.compile(r"/market/"))
                    if p_links:
                        metrics["sector"] = p_links[-1].text.strip()
                        if len(p_links) > 1:
                            metrics["industry"] = p_links[0].text.strip()

                # Direct Exact Mapping from Top Ratios Box
                for li in soup.find_all('li', class_='flex flex-space-between'):
                    name_span = li.find('span', class_='name')
                    val_span = li.find('span', class_='number')
                    if name_span and val_span:
                        n_text = name_span.get_text(strip=True).lower()
                        v_text = val_span.get_text(strip=True).replace(',', '').replace('%', '').replace('₹', '').replace('Cr.', '').strip()
                        match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", v_text)
                        if not match:
                            continue
                        val = float(match.group())

                        if 'market cap' in n_text: metrics["market_cap"] = val
                        elif n_text in ['stock p/e', 'p/e']: metrics["pe"] = val
                        elif n_text == 'roce': metrics["roce"] = val
                        elif n_text == 'roe': metrics["roe"] = val
                        elif n_text == 'debt to equity': metrics["debt_to_equity"] = val
                        elif n_text in ['sales growth 3years', 'sales growth 3 yrs']: metrics["sales_growth_3y"] = val
                        elif n_text == 'sales growth': metrics["sales_growth_ttm"] = val
                        elif n_text in ['profit var 3yrs', 'profit growth 3years']: metrics["profit_growth_3y"] = val
                        elif n_text == 'profit growth': metrics["profit_growth_ttm"] = val
                        elif n_text == 'opm': metrics["opm"] = val
                        elif n_text in ['int coverage', 'interest coverage']: metrics["interest_coverage_ttm"] = val
                        elif n_text == 'promoter holding': metrics["promoter_holding"] = val
                        elif n_text in ['pledged percentage', 'pledged %', 'pledge']: metrics["pledged_percentage"] = val
                        elif n_text == 'fii holding': metrics["fii_holding"] = val
                        elif n_text == 'dii holding': metrics["dii_holding"] = val
                        elif n_text == 'piotroski score': metrics["piotroski"] = int(val)

                if metrics["market_cap"] is not None:
                    break
        except Exception:
            pass

    # Cap Category
    if metrics["market_cap"] is not None:
        if metrics["market_cap"] >= 20000: metrics["cap_category"] = "🟢 LARGE CAP"
        elif metrics["market_cap"] >= 5000: metrics["cap_category"] = "🟡 MID CAP"
        else: metrics["cap_category"] = "🔴 SMALL CAP"

    return metrics

def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    pg = m["profit_growth_ttm"] if m["profit_growth_ttm"] is not None else m["profit_growth_3y"]
    if pg is not None:
        max_possible_score += 15
        if pg >= 12.0: earned_score += 15; marks["profit_growth"] = True
        else: earned_score += 5 if pg >= 5.0 else 0; marks["profit_growth"] = False
    else: marks["profit_growth"] = None

    if m["roce"] is not None:
        max_possible_score += 15
        if m["roce"] >= 15.0: earned_score += 15; marks["roce"] = True
        else: earned_score += 6 if m["roce"] >= 10.0 else 0; marks["roce"] = False
    else: marks["roce"] = None

    if m["debt_to_equity"] is not None:
        max_possible_score += 15
        if m["debt_to_equity"] < 1.0: earned_score += 15; marks["debt_to_equity"] = True
        else: earned_score += 5 if m["debt_to_equity"] < 1.5 else 0; marks["debt_to_equity"] = False
    else: marks["debt_to_equity"] = None

    if m["roe"] is not None:
        max_possible_score += 12
        if m["roe"] >= 15.0: earned_score += 12; marks["roe"] = True
        else: earned_score += 5 if m["roe"] >= 10.0 else 0; marks["roe"] = False
    else: marks["roe"] = None

    sg = m["sales_growth_ttm"] if m["sales_growth_ttm"] is not None else m["sales_growth_3y"]
    if sg is not None:
        max_possible_score += 12
        if sg >= 10.0: earned_score += 12; marks["sales_growth"] = True
        else: earned_score += 4 if sg >= 5.0 else 0; marks["sales_growth"] = False
    else: marks["sales_growth"] = None

    if m["opm"] is not None:
        max_possible_score += 12
        if m["opm"] >= 15.0: earned_score += 12; marks["opm"] = True
        else: earned_score += 4 if m["opm"] >= 8.0 else 0; marks["opm"] = False
    else: marks["opm"] = None

    if m["pe"] is not None:
        max_possible_score += 10
        if 10.0 <= m["pe"] <= 45.0: earned_score += 10; marks["pe"] = True
        else: earned_score += 4 if m["pe"] <= 60.0 else 0; marks["pe"] = False
    else: marks["pe"] = None

    ic = m["interest_coverage_ttm"] if m["interest_coverage_ttm"] is not None else m["interest_coverage_fy"]
    if ic is not None:
        max_possible_score += 9
        if ic >= 3.5: earned_score += 9; marks["interest_coverage"] = True
        else: marks["interest_coverage"] = False
    else: marks["interest_coverage"] = None

    if max_possible_score >= 20:
        final_score = int(round((earned_score / max_possible_score) * 100))
        if final_score >= 80: quality = "🟢 A+ SUPER STRONG"
        elif final_score >= 65: quality = "🟢 A GOOD QUALITY"
        elif final_score >= 50: quality = "🟡 B AVERAGE"
        else: quality = "🔴 C WEAK"
    else:
        final_score = "N/A"
        quality = "⚪ DATA UNAVAILABLE"

    return final_score, quality, marks

def get_fundamental_analysis(symbol):
    try:
        metrics = get_screener_data(symbol)
        score, quality, marks = calculate_100M_score(metrics)
        return {
            "available": (score != "N/A"),
            "score": score,
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": [],
        }
    except Exception as e:
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": [],
            }

