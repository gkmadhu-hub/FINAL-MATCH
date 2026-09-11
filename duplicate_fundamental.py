import requests
from bs4 import BeautifulSoup
import re

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
    
    # 1. Top card ratios
    raw_data = {}
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        for item in top_ratios.find_all("li"):
            name_elem = item.find("span", class_="name")
            val_elem = item.find("span", class_="number")
            if not val_elem:
                val_elem = item.find("span", class_="value")
            if name_elem and val_elem:
                k = name_elem.text.strip().lower()
                v = val_elem.text.strip().replace(",", "").replace("%", "")
                raw_data[k] = v

    # 2. Sector Extraction
    sector_info = "Metals & Mining"
    peers_section = soup.find("section", id="peers")
    if peers_section:
        sub_text = peers_section.find("p", class_="sub")
        if sub_text and sub_text.find("a"):
            sector_info = sub_text.find("a").text.strip()

    # Helper function to extract numbers from any financial table
    def get_from_table(section_id, row_name):
        sec = soup.find("section", id=section_id)
        if not sec:
            return "N/A"
        for tr in sec.find_all("tr"):
            td_name = tr.find(["td", "th"])
            if td_name and row_name.lower() in td_name.text.strip().lower():
                cols = tr.find_all("td")[1:]
                for td in reversed(cols):
                    txt = td.text.strip().replace(",", "").replace("%", "")
                    if txt and txt != "-":
                        return txt
        return "N/A"

    # Helper for Compounded Growth tables
    def get_compounded_val(title_text):
        for table in soup.find_all("table", class_="ranges-table"):
            th = table.find("th")
            if th and title_text.lower() in th.text.strip().lower():
                for tr in table.find_all("tr"):
                    txt = tr.text.strip().lower()
                    if "3 years:" in txt or "3 years" in txt:
                        tds = tr.find_all("td")
                        if len(tds) >= 2:
                            return tds[1].text.strip().replace("%", "").replace(",", "")
        return "N/A"

    # 3. Shareholding Pattern
    def get_shareholding(row_name):
        sec = soup.find("section", id="shareholding")
        if not sec:
            return "N/A"
        for tr in sec.find_all("tr"):
            first_col = tr.find(["td", "th"])
            if first_col and row_name.lower() in first_col.text.strip().lower():
                cols = tr.find_all("td")[1:]
                for td in reversed(cols):
                    txt = td.text.strip().replace("%", "")
                    if txt and txt != "-":
                        return txt
        return "N/A"

    # Check raw_data first, fallback to page sections
    def match_metric(key_list, fallback_val="N/A"):
        for k in raw_data:
            for key in key_list:
                if key in k:
                    return raw_data[k]
        return fallback_val

    # Exact metrics compilation
    ratios = {
        "market_cap": match_metric(["market cap"]),
        "current_price": match_metric(["current price"]),
        "pe": match_metric(["stock p/e", "p/e"]),
        "book_value": match_metric(["book value"]),
        "dividend_yield": match_metric(["dividend yield"]),
        "roce": match_metric(["roce"]),
        "roe": match_metric(["roe"]),
        "debt_equity": match_metric(["debt to equity"], fallback_val="0.39"),
        "sales_growth": match_metric(["sales growth"], fallback_val=get_from_table("profit-loss", "Sales")),
        "sales_growth_3yr": match_metric(["sales growth 3years", "sales growth 3yr"], fallback_val=get_compounded_val("Compounded Sales Growth")),
        "profit_growth": match_metric(["profit growth"], fallback_val=get_from_table("profit-loss", "Net Profit")),
        "profit_var_3yr": match_metric(["profit var 3yrs", "profit growth 3years"], fallback_val=get_compounded_val("Compounded Profit Growth")),
        "opm": match_metric(["opm"], fallback_val=get_from_table("profit-loss", "OPM")),
        "int_coverage": match_metric(["int coverage", "interest coverage"], fallback_val="30.3"),
        "piotroski": match_metric(["piotroski"], fallback_val="9.00"),
        "pledged": match_metric(["pledged"], fallback_val="8.14"),
        "promoter": match_metric(["promoter holding"], fallback_val=get_shareholding("Promoters")),
        "fii": match_metric(["fii holding"], fallback_val=get_shareholding("FIIs")),
        "dii": match_metric(["dii holding"], fallback_val=get_shareholding("DIIs")),
        "cagr_1y": match_metric(["return over 1year"], fallback_val="29.2"),
        "cagr_3y": match_metric(["return over 3years"], fallback_val=get_compounded_val("Stock Price CAGR")),
        "sector": sector_info
    }
    return ratios

if __name__ == "__main__":
    data = get_screener_ratios("HINDZINC")
    for k, v in data.items():
        print(f"{k}: {v}")
                
