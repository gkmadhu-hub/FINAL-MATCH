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

def clean_val(val_str):
    if val_str is None: return None
    try:
        clean = (str(val_str).replace("%", "").replace(",", "").replace("₹", "").replace("Cr", "").strip())
        return float(clean)
    except Exception:
        return None

def get_screener_session():
    if HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
    else:
        session = requests.Session()
        session.headers.update({
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
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
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
            }
            session.post(login_url, data=payload, headers=headers, timeout=10)
    except Exception:
        pass
    return session

screener_session = get_screener_session()

def get_screener_data(symbol):
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

    metrics = {
        "market_cap": None, "cap_category": "N/A", "sector": "N/A", "industry": "N/A",
        "high_52w": None, "low_52w": None, "pe": None, "roce": None, "roe": None,
        "debt_to_equity": None, "sales_growth_ttm": None, "sales_growth_3y": None,
        "profit_growth_ttm": None, "profit_growth_3y": None, "opm": None,
        "interest_coverage_ttm": None, "interest_coverage_fy": None,
        "price_cagr_1y": None, "price_cagr_3y": None, "promoter_holding": None,
        "pledged_percentage": None, "fii_holding": None, "dii_holding": None, "piotroski": None,
    }

    # 1. Base Data from YFinance (Official API)
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        info = ticker.info or {}
        if info:
            metrics["sector"] = info.get("sector") or "N/A"
            metrics["industry"] = info.get("industry") or "N/A"
            mcap = info.get("marketCap")
            if mcap: metrics["market_cap"] = round(mcap / 10000000.0, 1)
            metrics["pe"] = info.get("trailingPE") or info.get("forwardPE")
            if info.get("debtToEquity") is not None: metrics["debt_to_equity"] = round(info.get("debtToEquity") / 100.0, 2)
            if info.get("operatingMargins") is not None: metrics["opm"] = round(info.get("operatingMargins") * 100.0, 1)
            if info.get("returnOnEquity") is not None: metrics["roe"] = round(info.get("returnOnEquity") * 100.0, 1)
            if info.get("heldPercentInsiders") is not None: metrics["promoter_holding"] = round(info.get("heldPercentInsiders") * 100.0, 2)
            if info.get("heldPercentInstitutions") is not None: metrics["dii_holding"] = round(info.get("heldPercentInstitutions") * 100.0, 2)
    except Exception:
        pass

    # 2. Logged-in Screener Scraping (Original Data Extraction Only)
    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/",
    ]

    for url in urls:
        try:
            res = screener_session.get(url, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                page_text = soup.get_text(" ", strip=True)

                # Peer / Sector info
                peers_sec = soup.find("section", {"id": "peers"})
                if peers_sec:
                    p_links = peers_sec.find_all("a", href=re.compile(r"/market/"))
                    if p_links:
                        metrics["sector"] = p_links[-1].text.strip()
                        if len(p_links) > 1: metrics["industry"] = p_links[0].text.strip()

                # --- TOP RATIOS BOX PARSING (EXACT DECIMALS LOGIC) ---
                top_ratios = soup.find("ul", {"id": "top-ratios"}) or soup.find("div", {"class": "company-ratios"})
                if top_ratios:
                    for li in top_ratios.find_all(["li", "div", "tr"]):
                        name_span = li.find("span", class_="name")
                        val_span = li.find("span", class_="number")
                        if name_span and val_span:
                            raw_txt = name_span.get_text(strip=True).lower()
                            v_text = val_span.get_text(strip=True).replace(",", "")
                            nums = re.findall(r"[-+]?\d*\.?\d+", v_text)
                            if not nums: continue
                            val = float(nums[-1])

                            if "market cap" in raw_txt: metrics["market_cap"] = val
                            elif "stock p/e" in raw_txt: metrics["pe"] = val
                            elif "roce" in raw_txt: metrics["roce"] = val
                            elif "roe" in raw_txt and "3" not in raw_txt: metrics["roe"] = val
                            elif "debt to equity" in raw_txt: metrics["debt_to_equity"] = val
                            elif "opm" in raw_txt: metrics["opm"] = val
                            elif "pledged" in raw_txt or "pledge" in raw_txt: metrics["pledged_percentage"] = val
                            elif "int coverage" in raw_txt or "interest coverage" in raw_txt: metrics["interest_coverage_ttm"] = val
                            elif "sales growth" in raw_txt and "3" not in raw_txt: metrics["sales_growth_ttm"] = val
                            elif "profit growth" in raw_txt and "3" not in raw_txt: metrics["profit_growth_ttm"] = val
                            elif "sales growth 3years" in raw_txt or "sales growth 3 yrs" in raw_txt: metrics["sales_growth_3y"] = val
                            elif "profit var 3yrs" in raw_txt or "profit growth 3years" in raw_txt: metrics["profit_growth_3y"] = val
                            elif "fii holding" in raw_txt: metrics["fii_holding"] = val
                            elif "dii holding" in raw_txt: metrics["dii_holding"] = val
                            elif "promoter holding" in raw_txt: metrics["promoter_holding"] = val

                # Tables (Growth Rates & Price CAGR - Fallback if not found in top box)
                ranges = soup.find_all("table", {"class": re.compile(r"ranges-table")})
                for t in ranges:
                    th = t.find("th")
                    tname = th.text.strip().lower() if th else ""
                    for r in t.find_all("tr"):
                        tds = r.find_all("td")
                        if len(tds) >= 2:
                            dur = tds[0].text.strip().lower()
                            v = clean_val(tds[1].text)
                            if v is not None:
                                if "3 years" in dur or "3 yrs" in dur:
                                    if "price" in tname or "cagr" in tname: metrics["price_cagr_3y"] = v
                                elif "1 year" in dur or "1 yr" in dur:
                                    if "price" in tname or "cagr" in tname: metrics["price_cagr_1y"] = v

                # Shareholding Table (Fallback)
                shp = soup.find("section", {"id": "shareholding"})
                if shp:
                    for tr in shp.find_all("tr"):
                        row_txt = tr.get_text(separator=" ", strip=True).lower()
                        tds = tr.find_all(["td", "th"])
                        nums = [clean_val(td.get_text(strip=True)) for td in tds if clean_val(td.get_text(strip=True)) is not None]
                        if nums:
                            if "promoter" in row_txt and metrics["promoter_holding"] is None: metrics["promoter_holding"] = nums[-1]
                            elif "fii" in row_txt and metrics["fii_holding"] is None: metrics["fii_holding"] = nums[-1]
                            elif "dii" in row_txt and metrics["dii_holding"] is None: metrics["dii_holding"] = nums[-1]

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
        if pg >= 12.0:
            earned_score += 15; marks["profit_growth"] = True
        else:
            earned_score += 5 if pg >= 5.0 else 0; marks["profit_growth"] = False
    else: marks["profit_growth"] = None

    if m["roce"] is not None:
        max_possible_score += 15
        if m["roce"] >= 15.0:
            earned_score += 15; marks["roce"] = True
        else:
            earned_score += 6 if m["roce"] >= 10.0 else 0; marks["roce"] = False
    else: marks["roce"] = None

    if m["debt_to_equity"] is not None:
        max_possible_score += 15
        if m["debt_to_equity"] < 1.0:
            earned_score += 15; marks["debt_to_equity"] = True
        else:
            earned_score += 5 if m["debt_to_equity"] < 1.5 else 0; marks["debt_to_equity"] = False
    else: marks["debt_to_equity"] = None

    if m["roe"] is not None:
        max_possible_score += 12
        if m["roe"] >= 15.0:
            earned_score += 12; marks["roe"] = True
        else:
            earned_score += 5 if m["roe"] >= 10.0 else 0; marks["roe"] = False
    else: marks["roe"] = None

    sg = m["sales_growth_ttm"] if m["sales_growth_ttm"] is not None else m["sales_growth_3y"]
    if sg is not None:
        max_possible_score += 12
        if sg >= 10.0:
            earned_score += 12; marks["sales_growth"] = True
        else:
            earned_score += 4 if sg >= 5.0 else 0; marks["sales_growth"] = False
    else: marks["sales_growth"] = None

    if m["opm"] is not None:
        max_possible_score += 12
        if m["opm"] >= 15.0:
            earned_score += 12; marks["opm"] = True
        else:
            earned_score += 4 if m["opm"] >= 8.0 else 0; marks["opm"] = False
    else: marks["opm"] = None

    if m["pe"] is not None:
        max_possible_score += 10
        if 10.0 <= m["pe"] <= 45.0:
            earned_score += 10; marks["pe"] = True
        else:
            earned_score += 4 if m["pe"] <= 60.0 else 0; marks["pe"] = False
    else: marks["pe"] = None

    ic = m["interest_coverage_ttm"] if m["interest_coverage_ttm"] is not None else m["interest_coverage_fy"]
    if ic is not None:
        max_possible_score += 9
        if ic >= 3.5:
            earned_score += 9; marks["interest_coverage"] = True
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
        }
    except Exception as e:
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
      }
      
