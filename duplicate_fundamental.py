import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36"
    })

    clean_sym = ticker.replace(".NS", "").replace(".BO", "").strip().upper()

    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]

    resp = None
    for url in urls:
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200 and "top-ratios" in r.text:
                resp = r
                break
        except Exception:
            pass

    if not resp:
        return {}

    soup = BeautifulSoup(resp.content, "html.parser")

    # ---------------------------------------------------------
    # TOP RATIOS - KEEP SCREENER ORIGINAL DISPLAY VALUE
    # ---------------------------------------------------------
    raw = {}

    top = soup.find("ul", id="top-ratios")
    if top:
        for li in top.find_all("li"):
            name = li.find("span", class_="name")
            value = li.find("span", class_="number")

            if not value:
                value = li.find("span", class_="value")

            if name and value:
                key = re.sub(r"\s+", " ", name.get_text(" ", strip=True)).lower()
                val = re.sub(r"\s+", " ", value.get_text(" ", strip=True))
                raw[key] = val

    def get_ratio(*keys, default="N/A"):
        for wanted in keys:
            wanted = wanted.lower()
            for key, value in raw.items():
                if key == wanted or wanted in key:
                    return value
        return default

    # ---------------------------------------------------------
    # TOP RATIO VALUES
    # ---------------------------------------------------------
    market_cap = get_ratio("market cap")
    current_price = get_ratio("current price")
    pe = get_ratio("stock p/e", "p/e")
    book_value = get_ratio("book value")
    dividend_yield = get_ratio("dividend yield")
    roce = get_ratio("roce")
    roe = get_ratio("roe")
    face_value = get_ratio("face value")

    profit_growth = get_ratio("profit growth")
    sales_growth = get_ratio("sales growth")
    profit_3y = get_ratio("profit 3yrs", "profit 3 years")
    sales_3y = get_ratio("sales growth 3yrs", "sales growth 3 years")

    opm = get_ratio("opm")
    debt_equity = get_ratio("debt to equity")
    int_coverage = get_ratio("int coverage", "interest coverage")

    piotroski = get_ratio("piotroski score", "piotroski")

    promoter = get_ratio("promoter holding", "promoters")
    fii = get_ratio("fii holding", "fii")
    dii = get_ratio("dii holding", "dii")
    pledged = get_ratio("pledged percentage", "pledged")

    return_1y = get_ratio("return over 1year", "return over 1 year")
    return_3y = get_ratio("return over 3years", "return over 3 years")

    # ---------------------------------------------------------
    # GROWTH TABLES - ORIGINAL SCREENER DECIMALS
    # ---------------------------------------------------------
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

        header = th.get_text(" ", strip=True).lower()

        for row in table.find_all("tr"):
            cells = row.find_all("td")

            if len(cells) != 2:
                continue

            period = cells[0].get_text(" ", strip=True).lower()
            value = cells[1].get_text(" ", strip=True)

            if "sales growth" in header:
                if "ttm" in period:
                    sales_growth_ttm = value
                elif "3 years" in period:
                    sales_growth_3yr = value

            elif "profit growth" in header:
                if "ttm" in period:
                    profit_growth_ttm = value
                elif "3 years" in period:
                    profit_growth_3yr = value

            elif "price cagr" in header or "stock price cagr" in header:
                if "1 year" in period:
                    cagr_1y = value
                elif "3 years" in period:
                    cagr_3y = value

    # ---------------------------------------------------------
    # FALLBACKS ONLY WHEN TOP RATIO IS NOT AVAILABLE
    # ---------------------------------------------------------
    if sales_growth_ttm == "N/A":
        sales_growth_ttm = sales_growth

    if profit_growth_ttm == "N/A":
        profit_growth_ttm = profit_growth

    if sales_growth_3yr == "N/A":
        sales_growth_3yr = sales_3y

    if profit_growth_3yr == "N/A":
        profit_growth_3yr = profit_3y

    if cagr_1y == "N/A":
        cagr_1y = return_1y

    if cagr_3y == "N/A":
        cagr_3y = return_3y

    # ---------------------------------------------------------
    # SECTOR
    # ---------------------------------------------------------
    sector = "N/A"

    peers = soup.find("section", id="peers")
    if peers:
        sub = peers.find("p", class_="sub")
        if sub:
            a = sub.find("a")
            if a:
                sector = a.get_text(" ", strip=True)

    if sector == "N/A":
        # Screener company info fallback
        info = soup.find("div", id="company-info")
        if info:
            txt = info.get_text(" ", strip=True)
            m = re.search(r"Industry\s*:\s*([^|]+)", txt, re.I)
            if m:
                sector = m.group(1).strip()

    # ---------------------------------------------------------
    # CLEAN % SYMBOLS ONLY
    # Keep ALL original decimals.
    # ---------------------------------------------------------
    def clean(v):
        if v is None:
            return "N/A"
        return str(v).strip()

    def percent_clean(v):
        v = clean(v)
        return v.replace("%", "").strip()

    return {
        "market_cap": clean(market_cap).replace(",", ""),
        "current_price": clean(current_price).replace(",", ""),

        "pe": clean(pe),
        "book_value": clean(book_value),
        "dividend_yield": percent_clean(dividend_yield),

        "roce": percent_clean(roce),
        "roe": percent_clean(roe),
        "face_value": clean(face_value),

        "sales_growth": percent_clean(sales_growth_ttm),
        "sales_growth_3yr": percent_clean(sales_growth_3yr),

        "profit_growth": percent_clean(profit_growth_ttm),
        "profit_var_3yr": percent_clean(profit_growth_3yr),

        "opm": percent_clean(opm),
        "debt_equity": clean(debt_equity),
        "int_coverage": clean(int_coverage),

        "piotroski": clean(piotroski),

        "promoter": percent_clean(promoter),
        "pledged": percent_clean(pledged),
        "fii": percent_clean(fii),
        "dii": percent_clean(dii),

        "cagr_1y": percent_clean(cagr_1y),
        "cagr_3y": percent_clean(cagr_3y),

        "sector": clean(sector)
    }
