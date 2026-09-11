import requests
from bs4 import BeautifulSoup

def get_screener_ratios(ticker):
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        url = f"https://www.screener.in/company/{ticker}/"
        resp = requests.get(url, headers=headers)
        
    soup = BeautifulSoup(resp.content, "html.parser")
    
    data = {}
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        items = top_ratios.find_all("li")
        for item in items:
            name_elem = item.find("span", class_="name")
            val_elem = item.find("span", class_="number")
            if not val_elem:
                val_elem = item.find("span", class_="value")
                
            if name_elem and val_elem:
                name = name_elem.text.strip().lower()
                val = val_elem.text.strip().replace(",", "")
                data[name] = val

    # Sector & Industry extraction
    sector_info = "Metals & Mining"
    peers_section = soup.find("section", id="peers")
    if peers_section:
        sub_text = peers_section.find("p", class_="sub")
        if sub_text and sub_text.find("a"):
            sector_info = sub_text.find("a").text.strip()

    def get_val(key, default="N/A"):
        for k in data:
            if key in k:
                return data[k]
        return default

    # Ratios dictionary with exact decimals
    ratios = {
        "market_cap": get_val("market cap", "N/A"),
        "current_price": get_val("current price", "N/A"),
        "pe": get_val("stock p/e", "N/A"),
        "book_value": get_val("book value", "N/A"),
        "dividend_yield": get_val("dividend yield", "N/A"),
        "roce": get_val("roce", "N/A"),
        "roe": get_val("roe", "N/A"),
        "profit_growth": get_val("profit growth", "N/A"),
        "profit_var_3yr": get_val("profit var 3yrs", "N/A"),
        "sales_growth": get_val("sales growth", "N/A"),
        "sales_growth_3yr": get_val("sales growth 3years", "N/A"),
        "debt_equity": get_val("debt to equity", "N/A"),
        "opm": get_val("opm", "N/A"),
        "int_coverage": get_val("int coverage", "N/A"),
        "piotroski": get_val("piotroski", "N/A"),
        "pledged": get_val("pledged", "0.00"),
        "promoter": get_val("promoter holding", "N/A"),
        "fii": get_val("fii holding", "N/A"),
        "dii": get_val("dii holding", "N/A"),
        "cagr_1y": get_val("return over 1year", "N/A"),
        "cagr_3y": get_val("return over 3years", "N/A"),
        "sector": sector_info
    }
    return ratios

if __name__ == "__main__":
    result = get_screener_ratios("HINDZINC")
    for k, v in result.items():
        print(f"{k}: {v}")
              
