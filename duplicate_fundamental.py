import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    resp = requests.get(url, headers=headers, timeout=15)
    
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = requests.get(url, headers=headers, timeout=15)

    soup = BeautifulSoup(resp.content, "html.parser")

    # 1. Scrape Default Top Ratios (Market Cap, PE, ROCE, ROE, Current Price, etc.)
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

    def match_top(keys, default="N/A"):
        for item in keys:
            for k in raw_data:
                if item == k or item in k:
                    return raw_data[k]
        return default

    # 2. Extract Piotroski Score from Analysis / HTML text
    piotroski = "N/A"
    full_text = soup.get_text()
    pio_match = re.search(r"Piotroski\s+score\s*(?:of|:)?\s*(\d+(?:\.\d+)?)", full_text, re.IGNORECASE)
    if pio_match:
        piotroski = pio_match.group(1)

    # 3. Extract Compounded Sales & Profit Growth, CAGR Tables
    sales_growth_ttm = "N/A"
    sales_growth_3yr = "N/A"
    profit_growth_ttm = "N/A"
    profit_growth_3yr = "N/A"
    cagr_1y = "N/A"
    cagr_3y = "N/A"

    for table in soup.find_all("table", class_="ranges-table"):
        th = table.find("th")
        if not th:
            continue
        header_title = th.get_text(strip=True).lower()
        rows = table.find_all("tr")

        for r in rows:
            tds = [td.get_text(strip=True) for td in r.find_all("td")]
            if len(tds) == 2:
                period = tds[0].lower()
                val = tds[1].replace("%", "").strip()

                if "sales growth" in header_title:
                    if "ttm" in period:
                        sales_growth_ttm = val
                    elif "3 years" in period:
                        sales_growth_3yr = val
                elif "profit growth" in header_title:
                    if "ttm" in period:
                        profit_growth_ttm = val
                    elif "3 years" in period:
                        profit_growth_3yr = val
                elif "price cagr" in header_title or "stock price cagr" in header_title:
                    if "1 year" in period:
                        cagr_1y = val
                    elif "3 years" in period:
                        cagr_3y = val

    # 4. Extract OPM and Interest Coverage from Profit & Loss Table
    opm = "N/A"
    int_cov = "N/A"
    pl_sec = soup.find("section", id="profit-loss")
    if pl_sec:
        for row in pl_sec.find_all("tr"):
            txt = row.get_text(" ", strip=True).lower()
            cols = [td.get_text(strip=True).replace("%", "").replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                row_label = cols[0].lower()
                if "opm" in row_label:
                    opm = cols[-1] # Latest TTM value
                elif "operating profit" in row_label and "margin" not in row_label:
                    latest_op = cols[-1]
                elif "interest" in row_label:
                    latest_int = cols[-1]

        # Calculate Interest Coverage (Operating Profit / Interest) if available
        try:
            op_val = float(latest_op)
            int_val = float(latest_int)
            if int_val > 0:
                int_cov = str(round(op_val / int_val, 2))
        except Exception:
            pass

    # 5. Extract Debt to Equity from Balance Sheet Table
    debt_equity = "N/A"
    bs_sec = soup.find("section", id="balance-sheet")
    if bs_sec:
        borrowings = None
        equity = None
        for row in bs_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                label = cols[0].lower()
                if "borrowings" in label:
                    try:
                        borrowings = float(cols[-1])
                    except ValueError:
                        borrowings = 0.0
                elif "total equity" in label or "share capital" in label:
                    try:
                        equity = float(cols[-1])
                    except ValueError:
                        equity = None

        if borrowings is not None and equity and equity > 0:
            debt_equity = str(round(borrowings / equity, 2))

    # 6. Extract Promoter, FII, DII, and Pledged Percentage from Shareholding
    promoter = "N/A"
    fii = "N/A"
    dii = "N/A"
    pledged = "0.0"

    sh_sec = soup.find("section", id="shareholding")
    if sh_sec:
        for row in sh_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace("%", "").replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                label = cols[0].lower()
                latest_val = cols[-1]
                if "promoter" in label and "pledged" not in label:
                    promoter = latest_val
                elif "fii" in label:
                    fii = latest_val
                elif "dii" in label:
                    dii = latest_val
                elif "pledged" in label:
                    pledged = latest_val

    # 7. Sector
    sector = "Metals & Mining"
    peers_sec = soup.find("section", id="peers")
    if peers_sec:
        sub = peers_sec.find("p", class_="sub")
        if sub and sub.find("a"):
            sector = sub.find("a").text.strip()

    return {
        "market_cap": match_top(["market cap"]),
        "current_price": match_top(["current price"]),
        "pe": match_top(["stock p/e", "p/e"]),
        "roce": match_top(["roce"]),
        "roe": match_top(["roe"]),
        "debt_equity": debt_equity,
        "sales_growth": sales_growth_ttm,
        "sales_growth_3yr": sales_growth_3yr,
        "profit_growth": profit_growth_ttm,
        "profit_var_3yr": profit_growth_3yr,
        "opm": opm,
        "int_coverage": int_cov,
        "piotroski": piotroski,
        "pledged": pledged,
        "promoter": promoter,
        "fii": fii,
        "dii": dii,
        "cagr_1y": cagr_1y,
        "cagr_3y": cagr_3y,
        "sector": sector
        }

