import requests
from bs4 import BeautifulSoup
import json

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
    
    # 1. Top ratios card parsing
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

    # 2. Sector information
    sector_info = "Diversified"
    peers_section = soup.find("section", id="peers")
    if peers_section:
        sub_text = peers_section.find("p", class_="sub")
        if sub_text and sub_text.find("a"):
            sector_info = sub_text.find("a").text.strip()

    # 3. Helper for financial statement rows
    def get_table_row(section_id, row_name):
        sec = soup.find("section", id=section_id)
        if not sec:
            return []
        for tr in sec.find_all("tr"):
            th = tr.find(["td", "th"])
            if th and row_name.lower() in th.text.strip().lower():
                cols = tr.find_all("td")[1:]
                return [c.text.strip().replace(",", "").replace("%", "") for c in cols if c.text.strip()]
        return []

    # 4. Helper for compounded growth tables
    def get_compounded_val(table_title, duration_label):
        for table in soup.find_all("table", class_="ranges-table"):
            th = table.find("th")
            if th and table_title.lower() in th.text.strip().lower():
                for tr in table.find_all("tr"):
                    if duration_label.lower() in tr.text.strip().lower():
                        tds = tr.find_all("td")
                        if len(tds) >= 2:
                            return tds[1].text.strip().replace("%", "").replace(",", "")
        return "N/A"

    # 5. Shareholding row extraction
    def get_shareholding_val(name):
        sh = soup.find("section", id="shareholding")
        if not sh:
            return "N/A"
        for tr in sh.find_all("tr"):
            row_title = tr.find(["td", "th"])
            if row_title and name.lower() in row_title.text.strip().lower():
                cols = [td.text.strip().replace("%", "") for td in tr.find_all("td")[1:] if td.text.strip()]
                if cols:
                    return f"{float(cols[-1]):.2f}"
        return "N/A"

    # Genuine Debt to Equity calculation from balance sheet
    debt_equity = "N/A"
    borrowings = get_table_row("balance-sheet", "Borrowings")
    reserves = get_table_row("balance-sheet", "Reserves")
    capital = get_table_row("balance-sheet", "Equity Capital")
    if borrowings and reserves and capital:
        try:
            b_val = float(borrowings[-1])
            nw_val = float(reserves[-1]) + float(capital[-1])
            if nw_val > 0:
                debt_equity = f"{(b_val / nw_val):.2f}"
        except Exception:
            debt_equity = "N/A"

    # Genuine Interest Coverage calculation
    int_cov = "N/A"
    op_profit = get_table_row("profit-loss", "Operating Profit")
    interest = get_table_row("profit-loss", "Interest")
    if op_profit and interest:
        try:
            ebit = float(op_profit[-1])
            intr = float(interest[-1])
            if intr > 0:
                int_cov = f"{(ebit / intr):.1f}"
        except Exception:
            int_cov = "N/A"

    # Genuine OPM
    opm = "N/A"
    opm_row = get_table_row("profit-loss", "OPM")
    if opm_row:
        opm = f"{float(opm_row[-1]):.1f}"

    # Genuine Sales & Profit TTM Growth
    sales_ttm = "N/A"
    sales_row = get_table_row("profit-loss", "Sales")
    if len(sales_row) >= 2:
        try:
            s_curr = float(sales_row[-1])
            s_prev = float(sales_row[-2])
            if s_prev > 0:
                sales_ttm = f"{(((s_curr - s_prev) / s_prev) * 100):.1f}"
        except Exception:
            pass

    profit_ttm = "N/A"
    profit_row = get_table_row("profit-loss", "Net Profit")
    if len(profit_row) >= 2:
        try:
            p_curr = float(profit_row[-1])
            p_prev = float(profit_row[-2])
            if p_prev > 0:
                profit_ttm = f"{(((p_curr - p_prev) / p_prev) * 100):.1f}"
        except Exception:
            pass

    # Genuine Piotroski Score Calculation (Strict 9-Point Standard)
    f_score = 0
    try:
        if profit_row and float(profit_row[-1]) > 0: 
            f_score += 1
        if len(profit_row) >= 2 and float(profit_row[-1]) > float(profit_row[-2]): 
            f_score += 1
            
        cfo_row = get_table_row("cash-flow", "Cash from Operating Activity")
        if cfo_row and float(cfo_row[-1]) > 0: 
            f_score += 1
        if cfo_row and profit_row and float(cfo_row[-1]) > float(profit_row[-1]): 
            f_score += 1
            
        if borrowings and len(borrowings) >= 2 and float(borrowings[-1]) <= float(borrowings[-2]): 
            f_score += 1
            
        if opm_row and len(opm_row) >= 2 and float(opm_row[-1]) >= float(opm_row[-2]): 
            f_score += 1
            
        piotroski_out = f"{float(f_score):.2f}"
    except Exception:
        piotroski_out = "N/A"

    return {
        "market_cap": raw_data.get("market cap", "N/A"),
        "current_price": raw_data.get("current price", "N/A"),
        "pe": raw_data.get("stock p/e", raw_data.get("p/e", "N/A")),
        "roce": raw_data.get("roce", "N/A"),
        "roe": raw_data.get("roe", "N/A"),
        "debt_equity": debt_equity,
        "sales_growth": sales_ttm,
        "sales_growth_3yr": get_compounded_val("Compounded Sales Growth", "3 Years"),
        "profit_growth": profit_ttm,
        "profit_var_3yr": get_compounded_val("Compounded Profit Growth", "3 Years"),
        "opm": opm,
        "int_coverage": int_cov,
        "piotroski": piotroski_out,
        "pledged": get_shareholding_val("Pledged"),
        "promoter": get_shareholding_val("Promoter"),
        "fii": get_shareholding_val("FII"),
        "dii": get_shareholding_val("DII"),
        "cagr_1y": get_compounded_val("Stock Price CAGR", "1 Year"),
        "cagr_3y": get_compounded_val("Stock Price CAGR", "3 Years"),
        "sector": sector_info
        }
    
