import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })

    # 1. Login to Screener to get custom top-ratios
    login_url = "https://www.screener.in/login/"
    try:
        r_get = session.get(login_url, timeout=15)
        soup_login = BeautifulSoup(r_get.text, "html.parser")
        csrf_elem = soup_login.find("input", {"name": "csrfmiddlewaretoken"})
        csrf_token = csrf_elem["value"] if csrf_elem else session.cookies.get("csrftoken", "")

        login_payload = {
            "username": "bsbindurani@gmail.com",
            "password": "cricket786",
            "csrfmiddlewaretoken": csrf_token
        }
        login_headers = {
            "Referer": login_url,
            "Origin": "https://www.screener.in"
        }
        session.post(login_url, data=login_payload, headers=login_headers, timeout=15)
    except Exception as e:
        print(f"Login error: {e}")

    # 2. Fetch Stock Page
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    resp = session.get(url, timeout=15)
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = session.get(url, timeout=15)

    soup = BeautifulSoup(resp.content, "html.parser")

    # 3. Parse Top Ratios Box
    raw_data = {}
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        for li in top_ratios.find_all("li"):
            name_elem = li.find("span", class_="name")
            val_elem = li.find("span", class_="number")
            if not val_elem:
                val_elem = li.find("span", class_="value")
            if name_elem and val_elem:
                k = name_elem.text.strip().lower()
                v = val_elem.text.strip().replace(",", "").replace("%", "")
                raw_data[k] = v

    def match(keys, default="N/A"):
        for item in keys:
            for k in raw_data:
                if item == k or item in k:
                    return raw_data[k]
        return default

    # 4. Fallback: Parse Shareholding Table if missing from top-ratios
    promoter = match(["promoter holding"])
    fii = match(["fii holding"])
    dii = match(["dii holding"])
    
    sh_sec = soup.find("section", id="shareholding")
    if sh_sec:
        for row in sh_sec.find_all("tr"):
            row_text = row.get_text(" ", strip=True)
            cols = [td.get_text(strip=True).replace("%", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                label = cols[0].lower()
                latest_val = cols[-1]
                if "promoter" in label and promoter == "N/A":
                    promoter = latest_val
                elif "fii" in label and fii == "N/A":
                    fii = latest_val
                elif "dii" in label and dii == "N/A":
                    dii = latest_val

    # 5. Sector
    sector = "Metals & Mining"
    peers_sec = soup.find("section", id="peers")
    if peers_sec:
        sub = peers_sec.find("p", class_="sub")
        if sub and sub.find("a"):
            sector = sub.find("a").text.strip()

    return {
        "market_cap": match(["market cap"]),
        "current_price": match(["current price"]),
        "pe": match(["stock p/e", "p/e"]),
        "roce": match(["roce"]),
        "roe": match(["roe"]),
        "debt_equity": match(["debt to equity"]),
        "sales_growth": match(["sales growth"]),
        "sales_growth_3yr": match(["sales growth 3years", "sales growth 3yr"]),
        "profit_growth": match(["profit growth"]),
        "profit_var_3yr": match(["profit var 3yrs", "profit var 3years"]),
        "opm": match(["opm"]),
        "int_coverage": match(["int coverage", "interest coverage"]),
        "piotroski": match(["piotroski score", "piotroski"]),
        "pledged": match(["pledged percentage", "pledged"]),
        "promoter": promoter,
        "fii": fii,
        "dii": dii,
        "cagr_1y": match(["return over 1year", "return over 1 year"]),
        "cagr_3y": match(["return over 3years", "return over 3 years"]),
        "sector": sector
    }

