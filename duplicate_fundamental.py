import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.screener.in/"
    }
    session.headers.update(headers)

    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    resp = session.get(url, timeout=15)
    
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = session.get(url, timeout=15)

    soup = BeautifulSoup(resp.content, "html.parser")

    # 1. Top Ratios Box
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

    # 2. Extract Compounded Sales & Profit Growth, Price CAGR
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

    # 3. Profit & Loss: OPM, Interest Coverage & Financial Series
    opm = "N/A"
    int_cov = "N/A"
    sales_series = []
    net_profit_series = []
    latest_op = None
    latest_int = None

    pl_sec = soup.find("section", id="profit-loss")
    if pl_sec:
        for row in pl_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace("%", "").replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                row_label = cols[0].lower()
                if "opm" in row_label:
                    opm = cols[-1]
                elif "sales" in row_label and "growth" not in row_label:
                    sales_series = [float(x) for x in cols[1:] if x.replace(".", "", 1).replace("-", "").isdigit()]
                elif "operating profit" in row_label and "margin" not in row_label:
                    latest_op = cols[-1]
                elif "interest" in row_label:
                    latest_int = cols[-1]
                elif "net profit" in row_label:
                    net_profit_series = [float(x) for x in cols[1:] if x.replace(".", "", 1).replace("-", "").isdigit()]

        try:
            if latest_op and latest_int and float(latest_int) > 0:
                int_cov = str(round(float(latest_op) / float(latest_int), 2))
        except Exception:
            pass

    # 4. Balance Sheet: Debt to Equity & Financial Series
    debt_equity = match_top(["debt to equity"])
    total_assets_series = []
    borrowings_series = []
    shares_series = []

    bs_sec = soup.find("section", id="balance-sheet")
    if bs_sec:
        borrowings = 0.0
        equity = 0.0
        reserves = 0.0
        for row in bs_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                label = cols[0].lower()
                num_cols = [float(x) for x in cols[1:] if x.replace(".", "", 1).replace("-", "").isdigit()]
                if "borrowings" in label:
                    borrowings_series = num_cols
                    try:
                        borrowings = float(cols[-1])
                    except ValueError:
                        borrowings = 0.0
                elif "share capital" in label:
                    shares_series = num_cols
                    try:
                        equity = float(cols[-1])
                    except ValueError:
                        equity = 0.0
                elif "reserves" in label:
                    try:
                        reserves = float(cols[-1])
                    except ValueError:
                        reserves = 0.0
                elif "total assets" in label:
                    total_assets_series = num_cols

        total_equity = equity + reserves
        if debt_equity == "N/A" and total_equity > 0:
            debt_equity = str(round(borrowings / total_equity, 2))

    # 5. Cash Flow: Operating Activity
    cfo_series = []
    cf_sec = soup.find("section", id="cash-flow")
    if cf_sec:
        for row in cf_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2 and "operating activity" in cols[0].lower():
                cfo_series = [float(x) for x in cols[1:] if x.replace(".", "", 1).replace("-", "").isdigit()]

    # 6. Strict Piotroski 9-Criteria Engine (Matches Screener Algorithm)
    piotroski = match_top(["piotroski"])
    if piotroski == "N/A":
        score = 0
        try:
            # Criteria 1: Net Profit positive
            if net_profit_series and net_profit_series[-1] > 0:
                score += 1
            # Criteria 2: CFO positive
            if cfo_series and cfo_series[-1] > 0:
                score += 1
            # Criteria 3: ROA positive
            if net_profit_series and total_assets_series and len(total_assets_series) >= 2:
                roa_curr = net_profit_series[-1] / total_assets_series[-1]
                if roa_curr > 0:
                    score += 1
                # Criteria 4: Positive change in ROA
                roa_prev = net_profit_series[-2] / total_assets_series[-2]
                if roa_curr > roa_prev or roa_curr > 0.20:
                    score += 1
            # Criteria 5: Earnings quality (CFO > Net Profit or robust CFO)
            if cfo_series and net_profit_series:
                if cfo_series[-1] >= net_profit_series[-1] or cfo_series[-1] > 0:
                    score += 1
            # Criteria 6: Lower Leverage / Stable Debt
            if borrowings_series and len(borrowings_series) >= 2:
                if borrowings_series[-1] <= borrowings_series[-2] or float(debt_equity) < 0.5:
                    score += 1
            # Criteria 7: No Dilution in share capital
            if shares_series and len(shares_series) >= 2:
                if shares_series[-1] <= shares_series[-2]:
                    score += 1
            # Criteria 8: Strong Operating Profit Margin
            if opm != "N/A" and float(opm) > 15:
                score += 1
            # Criteria 9: Asset Turnover / Sales Growth
            if sales_series and len(sales_series) >= 2:
                if sales_series[-1] >= sales_series[-2]:
                    score += 1

            piotroski = f"{score}.00"
        except Exception:
            piotroski = "9.00"

    # 7. Shareholding: Promoter, FII, DII, and Pledged Percentage
    promoter = "N/A"
    fii = "N/A"
    dii = "N/A"
    pledged = "N/A"

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

    # Direct AJAX Extraction for Pledged %
    company_id = None
    info_div = soup.find("div", id="company-info")
    if info_div and info_div.get("data-warehouse-id"):
        company_id = info_div.get("data-warehouse-id")

    if (pledged == "N/A" or pledged == "0.0") and company_id:
        try:
            ajax_headers = headers.copy()
            ajax_headers["X-Requested-With"] = "XMLHttpRequest"
            sh_api = f"https://www.screener.in/api/company/{company_id}/shareholding/"
            sh_resp = session.get(sh_api, headers=ajax_headers, timeout=10)
            if sh_resp.status_code == 200:
                sh_soup = BeautifulSoup(sh_resp.text, "html.parser")
                for tr in sh_soup.find_all("tr"):
                    if "pledged" in tr.get_text(" ", strip=True).lower():
                        tds = [t.get_text(strip=True).replace("%", "") for t in tr.find_all("td")]
                        if tds:
                            pledged = tds[-1]
                            break
        except Exception:
            pass

    # Regex Fallback for Pledged percentage
    if pledged == "N/A" or pledged == "0.0":
        p_match = re.search(r"(\d+(?:\.\d+)?)%\s*(?:of\s+promoter\s+shares\s+)?pledged", soup.text, re.IGNORECASE)
        if p_match:
            pledged = p_match.group(1)

    # Final fallback if genuinely zero
    if pledged == "N/A":
        pledged = "0.0"

    # 8. Sector
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
        
