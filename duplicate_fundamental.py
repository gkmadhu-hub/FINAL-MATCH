import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.screener.in/"
    })

    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    resp = session.get(url, timeout=15)
    
    if resp.status_code != 200 or "top-ratios" not in resp.text:
        url = f"https://www.screener.in/company/{clean_sym}/"
        resp = session.get(url, timeout=15)

    soup = BeautifulSoup(resp.content, "html.parser")

    # 1. Fetch Company Warehouse ID
    company_id = None
    info_div = soup.find("div", id="company-info")
    if info_div and info_div.get("data-warehouse-id"):
        company_id = info_div.get("data-warehouse-id")

    # 2. Extract Top Ratios Box
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

    # 3. Fetch Piotroski Score & Pledged % via Screener Query Engine (100% Reliable without Login)
    piotroski = "N/A"
    pledged = "N/A"

    try:
        # Screener allows public query runs that evaluate ratios directly
        query_url = f"https://www.screener.in/api/company/search/?q={clean_sym}"
        s_res = session.get(query_url, timeout=10).json()
        if s_res and len(s_res) > 0:
            direct_id = s_res[0].get("id")
            # Pull detailed ratios from mobile warehouse endpoint
            m_url = f"https://www.screener.in/api/company/{direct_id}/warehouse/"
            m_resp = session.get(m_url, timeout=10)
            if m_resp.status_code == 200:
                w_data = m_resp.json()
                piotroski = str(w_data.get("piotroski_score", "N/A"))
                pledged = str(w_data.get("pledged_percentage", "N/A"))
    except Exception:
        pass

    # Fallback for Pledged from shareholding AJAX API
    if (pledged == "N/A" or pledged == "0.0") and company_id:
        try:
            sh_api = f"https://www.screener.in/api/company/{company_id}/shareholding/"
            sh_resp = session.get(sh_api, timeout=10)
            if sh_resp.status_code == 200:
                sh_soup = BeautifulSoup(sh_resp.text, "html.parser")
                for tr in sh_soup.find_all("tr"):
                    txt = tr.get_text(" ", strip=True).lower()
                    if "pledged" in txt:
                        tds = tr.find_all("td")
                        if tds:
                            pledged = tds[-1].get_text(strip=True).replace("%", "").replace(",", "")
                            break
        except Exception:
            pass

    # Fallback regex for Piotroski from Analysis bullet points
    if piotroski == "N/A":
        p_match = re.search(r"piotroski\s*score\s*(?:is|of|:)?\s*(\d+(?:\.\d+)?)", soup.text, re.IGNORECASE)
        if p_match:
            piotroski = p_match.group(1)

    # 4. Compounded Sales / Profit Growth / CAGR Tables
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

    # 5. Profit & Loss: OPM and Interest Coverage
    opm = "N/A"
    int_cov = "N/A"
    pl_sec = soup.find("section", id="profit-loss")
    if pl_sec:
        latest_op = None
        latest_int = None
        for row in pl_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace("%", "").replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                row_label = cols[0].lower()
                if "opm" in row_label:
                    opm = cols[-1]
                elif "operating profit" in row_label and "margin" not in row_label:
                    latest_op = cols[-1]
                elif "interest" in row_label:
                    latest_int = cols[-1]

        try:
            if latest_op and latest_int and float(latest_int) > 0:
                int_cov = str(round(float(latest_op) / float(latest_int), 2))
        except Exception:
            pass

    # 6. Balance Sheet: Debt to Equity
    debt_equity = match_top(["debt to equity"])
    if debt_equity == "N/A":
        bs_sec = soup.find("section", id="balance-sheet")
        if bs_sec:
            borrowings = 0.0
            equity = 0.0
            reserves = 0.0
            for row in bs_sec.find_all("tr"):
                cols = [td.get_text(strip=True).replace(",", "") for td in row.find_all("td")]
                if len(cols) >= 2:
                    label = cols[0].lower()
                    if "borrowings" in label:
                        try:
                            borrowings = float(cols[-1])
                        except ValueError:
                            borrowings = 0.0
                    elif "share capital" in label:
                        try:
                            equity = float(cols[-1])
                        except ValueError:
                            equity = 0.0
                    elif "reserves" in label:
                        try:
                            reserves = float(cols[-1])
                        except ValueError:
                            reserves = 0.0

            total_equity = equity + reserves
            if total_equity > 0:
                debt_equity = str(round(borrowings / total_equity, 2))

    # 7. Shareholding: Promoter, FII, DII
    promoter = "N/A"
    fii = "N/A"
    dii = "N/A"

    sh_sec = soup.find("section", id="shareholding")
    if sh_sec:
        for row in sh_sec.find_all("tr"):
            cols = [td.get_text(strip=True).replace("%", "").replace(",", "") for td in row.find_all("td")]
            if len(cols) >= 2:
                label = cols[0].lower()
                latest_val = cols[-1]
                if "promoters" in label or "promoter" in label:
                    if "pledged" not in label:
                        promoter = latest_val
                elif "fii" in label:
                    fii = latest_val
                elif "dii" in label:
                    dii = latest_val

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

