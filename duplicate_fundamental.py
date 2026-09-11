import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = requests.get(url, headers=headers, timeout=15)
        
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # 1. Top card ratios parsing
    card_data = {}
    top_ratios = soup.find("ul", id="top-ratios")
    if top_ratios:
        for li in top_ratios.find_all("li"):
            name = li.find("span", class_="name")
            val = li.find("span", class_="number")
            if not val:
                val = li.find("span", class_="value")
            if name and val:
                card_data[name.text.strip().lower()] = val.text.strip().replace(",", "").replace("%", "")

    # Helper: Search through financial statement tables
    def find_table_metric(section_id, row_label):
        sec = soup.find("section", id=section_id)
        if not sec:
            return None
        for tr in sec.find_all("tr"):
            th = tr.find(["td", "th"])
            if th and row_label.lower() in th.text.strip().lower():
                cells = [td.text.strip().replace(",", "").replace("%", "") for td in tr.find_all("td")[1:] if td.text.strip()]
                if cells:
                    return cells[-1]
        return None

    # Helper: Search compounded growth tables
    def find_compounded_ratio(title, term):
        for tbl in soup.find_all("table", class_="ranges-table"):
            header = tbl.find("th")
            if header and title.lower() in header.text.strip().lower():
                for tr in tbl.find_all("tr"):
                    if term.lower() in tr.text.strip().lower():
                        tds = tr.find_all("td")
                        if len(tds) >= 2:
                            return tds[1].text.strip().replace("%", "").replace(",", "")
        return None

    # Helper: Shareholding table
    def find_shareholding_ratio(holder_name):
        sec = soup.find("section", id="shareholding")
        if not sec:
            return "N/A"
        for tr in sec.find_all("tr"):
            row = tr.find(["td", "th"])
            if row and holder_name.lower() in row.text.strip().lower():
                vals = [td.text.strip().replace("%", "") for td in tr.find_all("td")[1:] if td.text.strip()]
                if vals:
                    try:
                        return f"{float(vals[-1]):.2f}"
                    except Exception:
                        return vals[-1]
        return "N/A"

    # Sector
    sector = "Diversified"
    peers_sec = soup.find("section", id="peers")
    if peers_sec:
        sub = peers_sec.find("p", class_="sub")
        if sub and sub.find("a"):
            sector = sub.find("a").text.strip()

    # Exact Metrics from Screener
    opm_raw = find_table_metric("profit-loss", "OPM")
    opm_val = f"{float(opm_raw):.1f}" if opm_raw else "N/A"

    # Sales Growth (3Y)
    sg_3yr = find_compounded_ratio("Compounded Sales Growth", "3 Years")
    if not sg_3yr:
        sg_3yr = card_data.get("sales growth 3years", "N/A")

    # Profit Growth (3Y)
    pg_3yr = find_compounded_ratio("Compounded Profit Growth", "3 Years")
    if not pg_3yr:
        pg_3yr = card_data.get("profit var 3yrs", "N/A")

    # Stock Price CAGR
    cagr_1 = find_compounded_ratio("Stock Price CAGR", "1 Year")
    if not cagr_1:
        cagr_1 = card_data.get("return over 1year", "N/A")
        
    cagr_3 = find_compounded_ratio("Stock Price CAGR", "3 Years")
    if not cagr_3:
        cagr_3 = card_data.get("return over 3years", "N/A")

    # Interest Coverage
    int_cov = card_data.get("int coverage", None)
    if not int_cov:
        op = find_table_metric("profit-loss", "Operating Profit")
        intr = find_table_metric("profit-loss", "Interest")
        if op and intr and float(intr) > 0:
            int_cov = f"{(float(op) / float(intr)):.1f}"
        else:
            int_cov = "N/A"

    # Debt to Equity
    de_val = card_data.get("debt to equity", None)
    if not de_val:
        borr = find_table_metric("balance-sheet", "Borrowings")
        res = find_table_metric("balance-sheet", "Reserves")
        cap = find_table_metric("balance-sheet", "Equity Capital")
        if borr and res and cap:
            net_worth = float(res) + float(cap)
            if net_worth > 0:
                de_val = f"{(float(borr) / net_worth):.2f}"
            else:
                de_val = "N/A"
        else:
            de_val = "N/A"

    return {
        "market_cap": card_data.get("market cap", "N/A"),
        "current_price": card_data.get("current price", "N/A"),
        "pe": card_data.get("stock p/e", card_data.get("p/e", "N/A")),
        "roce": card_data.get("roce", "N/A"),
        "roe": card_data.get("roe", "N/A"),
        "debt_equity": de_val,
        "sales_growth": card_data.get("sales growth", "N/A"),
        "sales_growth_3yr": sg_3yr,
        "profit_growth": card_data.get("profit growth", "N/A"),
        "profit_var_3yr": pg_3yr,
        "opm": opm_val,
        "int_coverage": int_cov,
        "piotroski": card_data.get("piotroski score", "N/A"),
        "pledged": find_shareholding_ratio("Pledged"),
        "promoter": find_shareholding_ratio("Promoter"),
        "fii": find_shareholding_ratio("FII"),
        "dii": find_shareholding_ratio("DII"),
        "cagr_1y": cagr_1,
        "cagr_3y": cagr_3,
        "sector": sector
    }

if __name__ == "__main__":
    r = get_screener_ratios("HINDZINC")
    for k, v in r.items():
        print(f"{k}: {v}")
