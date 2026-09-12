import requests
from bs4 import BeautifulSoup

def get_screener_ratios(ticker):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    session.headers.update(headers)

    # 1. Login to Screener.in
    login_url = "https://www.screener.in/login/"
    try:
        r_get = session.get(login_url, timeout=15)
        soup_login = BeautifulSoup(r_get.content, "html.parser")
        csrf_input = soup_login.find("input", {"name": "csrfmiddlewaretoken"})
        csrf_token = csrf_input["value"] if csrf_input else session.cookies.get("csrftoken", "")

        login_payload = {
            "username": "bsbindurani@gmail.com",
            "password": "cricket786",
            "csrfmiddlewaretoken": csrf_token
        }
        login_headers = {
            "Referer": login_url,
            "Origin": "https://www.screener.in"
        }
        post_resp = session.post(login_url, data=login_payload, headers=login_headers, timeout=15)
    except Exception as e:
        print(f"Login connection error: {e}")

    # 2. Fetch Stock Page under Authenticated Session
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    
    resp = session.get(url, timeout=15)
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = session.get(url, timeout=15)

    soup = BeautifulSoup(resp.content, "html.parser")

    # 3. Scrape Top Ratio Box (Contains user's custom metrics)
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
        for k in raw_data:
            for item in keys:
                if item in k:
                    return raw_data[k]
        return default

    # 4. Sector
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
        "promoter": match(["promoter holding"]),
        "fii": match(["fii holding"]),
        "dii": match(["dii holding"]),
        "cagr_1y": match(["return over 1year", "return over 1 year"]),
        "cagr_3y": match(["return over 3years", "return over 3 years"]),
        "sector": sector
    }

if __name__ == "__main__":
    res = get_screener_ratios("HINDZINC")
    for key, value in res.items():
        print(f"{key}: {value}")

