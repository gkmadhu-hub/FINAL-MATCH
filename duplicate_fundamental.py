import requests
from bs4 import BeautifulSoup

# Screener Session Manager
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
})

def login_screener():
    login_url = "https://www.screener.in/login/"
    try:
        r = session.get(login_url, timeout=15)
        soup = BeautifulSoup(r.content, "html.parser")
        csrf = soup.find("input", {"name": "csrfmiddlewaretoken"})
        csrf_token = csrf["value"] if csrf else ""
        
        payload = {
            "username": "bsbindurani@gmail.com",
            "password": "cricket786",
            "csrfmiddlewaretoken": csrf_token
        }
        headers = {
            "Referer": login_url,
            "Origin": "https://www.screener.in"
        }
        post_r = session.post(login_url, data=payload, headers=headers, timeout=15)
        return post_r.status_code == 200
    except Exception as e:
        print(f"Login failed: {e}")
        return False

# Perform login once
login_screener()

def get_screener_ratios(ticker):
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    
    resp = session.get(url, timeout=15)
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = session.get(url, timeout=15)
        
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # 1. Direct ratios box parsing (Extracts all customized metrics)
    raw_data = {}
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        for li in top_ratios.find_all("li"):
            name_elem = li.find("span", class_="name")
            val_elem = li.find("span", class_="number")
            if not val_elem:
                val_elem = li.find("span", class_="value")
            if name_elem and val_elem:
                key = name_elem.text.strip().lower()
                val = val_elem.text.strip().replace(",", "").replace("%", "")
                raw_data[key] = val

    # Helper function to find keys matching user terms
    def get_val(keys, default="N/A"):
        for k in raw_data:
            for term in keys:
                if term in k:
                    return raw_data[k]
        return default

    # 2. Extract Sector
    sector = "Diversified"
    peers_section = soup.find("section", id="peers")
    if peers_section:
        sub_p = peers_section.find("p", class_="sub")
        if sub_p and sub_p.find("a"):
            sector = sub_p.find("a").text.strip()

    # Direct mapping strictly from logged-in account table
    return {
        "market_cap": get_val(["market cap"]),
        "current_price": get_val(["current price"]),
        "pe": get_val(["stock p/e", "p/e"]),
        "roce": get_val(["roce"]),
        "roe": get_val(["roe"]),
        "debt_equity": get_val(["debt to equity"]),
        "sales_growth": get_val(["sales growth"]),
        "sales_growth_3yr": get_val(["sales growth 3years", "sales growth 3yr"]),
        "profit_growth": get_val(["profit growth"]),
        "profit_var_3yr": get_val(["profit var 3yrs", "profit var 3years"]),
        "opm": get_val(["opm"]),
        "int_coverage": get_val(["int coverage", "interest coverage"]),
        "piotroski": get_val(["piotroski score", "piotroski"]),
        "pledged": get_val(["pledged percentage", "pledged"]),
        "promoter": get_val(["promoter holding"]),
        "fii": get_val(["fii holding"]),
        "dii": get_val(["dii holding"]),
        "cagr_1y": get_val(["return over 1year", "return over 1 year"]),
        "cagr_3y": get_val(["return over 3years", "return over 3 years"]),
        "sector": sector
    }

if __name__ == "__main__":
    data = get_screener_ratios("HINDZINC")
    for k, v in data.items():
        print(f"{k}: {v}")
