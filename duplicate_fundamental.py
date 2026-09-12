from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def get_screener_ratios(ticker):
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        try:
            # 1. Login to Screener
            page.goto("https://www.screener.in/login/", timeout=60000)
            page.fill("input[name='username']", "bsbindurani@gmail.com")
            page.fill("input[name='password']", "cricket786")
            page.click("button[type='submit']")
            page.wait_for_timeout(3000)

            # 2. Open Stock Page
            page.goto(f"https://www.screener.in/company/{clean_sym}/", timeout=60000)
            page.wait_for_timeout(3000)

            soup = BeautifulSoup(page.content(), "html.parser")

            # 3. Read custom top ratios box
            top_ratios = soup.find("ul", id="top-ratios")
            if top_ratios:
                for li in top_ratios.find_all("li"):
                    name_elem = li.find("span", class_="name")
                    val_elem = li.find("span", class_="number") or li.find("span", class_="value")
                    if name_elem and val_elem:
                        k = name_elem.text.strip().lower()
                        v = val_elem.text.strip().replace(",", "").replace("%", "")
                        data[k] = v

            # 4. Sector
            sector = "Paints"
            peers_sec = soup.find("section", id="peers")
            if peers_sec:
                sub = peers_sec.find("p", class_="sub")
                if sub and sub.find("a"):
                    sector = sub.find("a").text.strip()
            data['sector'] = sector

        except Exception as e:
            print(f"Error scraping: {e}")
        finally:
            browser.close()

    def find_key(names):
        for k in data:
            for n in names:
                if n == k:
                    return data[k]
        for k in data:
            for n in names:
                if n in k:
                    return data[k]
        return "N/A"

    return {
        "market_cap": find_key(["market cap"]),
        "current_price": find_key(["current price"]),
        "pe": find_key(["stock p/e", "p/e"]),
        "roce": find_key(["roce"]),
        "roe": find_key(["roe"]),
        "debt_equity": find_key(["debt to equity"]),
        "sales_growth": find_key(["sales growth"]),
        "sales_growth_3yr": find_key(["sales growth 3years", "sales growth 3yr"]),
        "profit_growth": find_key(["profit growth"]),
        "profit_var_3yr": find_key(["profit var 3yrs", "profit var 3years"]),
        "opm": find_key(["opm"]),
        "int_coverage": find_key(["int coverage", "interest coverage"]),
        "piotroski": find_key(["piotroski score", "piotroski"]),
        "pledged": find_key(["pledged percentage", "pledged"]),
        "promoter": find_key(["promoter holding"]),
        "fii": find_key(["fii holding"]),
        "dii": find_key(["dii holding"]),
        "cagr_1y": find_key(["return over 1year", "return over 1 year"]),
        "cagr_3y": find_key(["return over 3years", "return over 3 years"]),
        "sector": data.get("sector", "Paints")
    }

if __name__ == "__main__":
    ticker = "ASIANPAINT"
    print(f"Fetching live Screener data for: {ticker}...")
    res = get_screener_ratios(ticker)
    print("------------------------------------------")
    for k, v in res.items():
        print(f"{k}: {v}")
    print("------------------------------------------")
            
