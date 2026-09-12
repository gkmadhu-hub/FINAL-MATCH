from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

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
            page.goto(f"https://www.screener.in/company/{clean_sym}/consolidated/", timeout=60000)
            page.wait_for_timeout(3000)

            soup = BeautifulSoup(page.content(), "html.parser")

            # 3. Scrape exact customized top ratios
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
            sector = "Diversified"
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

    def get_val(keys):
        for k in data:
            for item in keys:
                if item in k:
                    return data[k]
        return "N/A"

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
        "sector": data.get("sector", "N/A")
    }

if __name__ == "__main__":
    res = get_screener_ratios("GRAVITA")
    for k, v in res.items():
        print(f"{k}: {v}")
                    
