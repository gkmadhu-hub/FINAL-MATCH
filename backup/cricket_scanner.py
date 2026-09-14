import os
import re
import time
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# -------------------------------------------------------------
# 1. CHARTINK SCREENERS LIST (ALL 11 SCANNERS - EXACT URLS)
# -------------------------------------------------------------
SCREENS = [
    {
        "name": "Monthly Breakout Scans with Volume updated",
        "url": "https://chartink.com/screener/copy-monthly-breakout-scans-with-volume-2220",
    },
    {
        "name": "MONTHLY CPR Break update 1",
        "url": "https://chartink.com/screener/copy-monthly-cpr-break-4",
    },
    {
        "name": "CPR BY KGS R1/PDH broken Swing Trading",
        "url": "https://chartink.com/screener/copy-cpr-by-kgs-r1-pdh-broken-swing-trading-32",
    },
    {
        "name": "GK Weekly CPR breakout UPDATED",
        "url": "https://chartink.com/screener/copy-weekly-cpr-breakout-50",
    },
    {
        "name": "GK Dynamic dashboard stocks UPDATED",
        "url": "https://chartink.com/screener/gk-dynamic-dashboard-stocks",
    },
    {
        "name": "GK final quality stocks 1",
        "url": "https://chartink.com/screener/gk-final-quality-stocks",
    },
    {
        "name": "The Momentum Trader - CPR SWING SCAN(Swing/Positional) update",
        "url": "https://chartink.com/screener/copy-the-momentum-trader-cpr-swing-scan-swing-positional-698",
    },
    {
        "name": "Dashboard setup Early breakout GK PULL BACK UPDATED",
        "url": "https://chartink.com/screener/dashboard-setup-early-breakout-gk",
    },
    {
        "name": "TTM Trend Positional picks updated",
        "url": "https://chartink.com/screener/copy-ttm-trend-positional-picks-30",
    },
    {
        "name": "GK Powerful Pullback / Dip Buy Scanner updated",
        "url": "https://chartink.com/screener/gk-powerful-pullback-dip-buy-scanner-updated",
    },
    {
        "name": "Institutions candlestick confirmation AI",
        "url": "https://chartink.com/screener/institutions-candlestick-confirmation-ai",
    },
]

# -------------------------------------------------------------
# 2. HELPER FUNCTIONS
# -------------------------------------------------------------
def clean_name(name):
    return name.replace("Copy - ", "").replace("Copy", "").strip()

def format_volume(vol_str):
    if not vol_str or vol_str == "N/A":
        return "N/A"
    try:
        clean_vol = str(vol_str).replace(",", "").replace("%", "").strip()
        vol = float(clean_vol)
        if vol >= 10000000:
            return f"{vol / 10000000:.1f}Cr"
        elif vol >= 100000:
            return f"{vol / 100000:.1f}L"
        elif vol >= 1000:
            return f"{vol / 1000:.1f}k"
        else:
            return str(int(vol))
    except Exception:
        return str(vol_str)

# -------------------------------------------------------------
# 3. SCRAPING LOGIC (STRICT ORIGINAL DATA)
# -------------------------------------------------------------
def scrape_screener_page(page, screen, all_scraped_stocks, stock_metrics):
    page_url = screen["url"]
    screener_name = clean_name(screen["name"])
    stocks = []

    try:
        page.goto(page_url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Trigger Run Scan button
        try:
            run_btn = page.locator(
                "button:has-text('RUN SCAN'), button.btn-primary:has-text('Run'), button:has-text('Run Scan')"
            ).first
            if run_btn.is_visible():
                run_btn.click()
                page.wait_for_timeout(2500)
        except Exception:
            pass

        # Wait for table
        try:
            page.wait_for_selector(
                "table.dataTable tbody tr, table.table-striped tbody tr, table.DataTable tbody tr",
                timeout=15000
            )
            page.wait_for_timeout(2000)
        except Exception:
            pass

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find(
            "table", {"class": lambda x: x and ("table" in x or "dataTable" in x or "DataTable" in x)}
        )

        if table:
            headers = [th.text.strip().lower() for th in table.find_all("th")]
            sym_idx, price_idx, chg_idx, vol_idx = -1, -1, -1, -1

            for i, h in enumerate(headers):
                if "nse" in h or "symbol" in h or "stock" in h:
                    sym_idx = i
                elif "price" in h or "close" in h:
                    price_idx = i
                elif "chg" in h or "change" in h:
                    chg_idx = i
                elif "volume" in h or "vol" in h:
                    vol_idx = i

            if sym_idx == -1: sym_idx = 2
            if price_idx == -1: price_idx = 4
            if chg_idx == -1: chg_idx = 5
            if vol_idx == -1: vol_idx = 6

            rows = (
                table.find("tbody").find_all("tr")
                if table.find("tbody")
                else table.find_all("tr")
            )

            for row in rows:
                cols = row.find_all("td")
                if len(cols) > max(sym_idx, price_idx, chg_idx):
                    symbol = cols[sym_idx].text.strip().upper()
                    price = cols[price_idx].text.strip()
                    chg = cols[chg_idx].text.strip()
                    vol = cols[vol_idx].text.strip() if vol_idx < len(cols) else "N/A"

                    if symbol and "no data" not in symbol.lower() and symbol not in ["N/A", "SYMBOL", "NAME"]:
                        symbol = symbol.replace("NSE:", "").strip()
                        stocks.append({
                            "symbol": symbol,
                            "price": price,
                            "chg": chg,
                            "vol": vol,
                        })
                        all_scraped_stocks[symbol].append(screener_name)

                        if symbol not in stock_metrics:
                            stock_metrics[symbol] = {
                                "price": price,
                                "chg": chg,
                                "vol": vol,
                            }

        print(f"-> Found {len(stocks)} stocks in {screener_name}")

    except Exception as e:
        print(f"❌ Error scraping {screener_name}: {e}")

    return stocks

# -------------------------------------------------------------
# 4. MAIN SCRAPER RUNNER (WITH 1-11 NUMBERING)
# -------------------------------------------------------------
def fetch_all_scanners(callback_process_screener=None):
    all_scraped_stocks = defaultdict(list)
    stock_metrics = {}
    raw_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()

        for index, screen in enumerate(SCREENS, start=1):
            screener_name = screen["name"]
            page_url = screen["url"]
            numbered_name = f"[{index}/{len(SCREENS)}] {clean_name(screener_name)}"

            print(f"Scraping: {numbered_name}...")
            stocks = scrape_screener_page(page, screen, all_scraped_stocks, stock_metrics)
            
            raw_results.append({
                "screener_name": numbered_name,
                "url": page_url,
                "stocks": stocks
            })

            if callback_process_screener:
                callback_process_screener(numbered_name, stocks, page_url)

            time.sleep(2)

        browser.close()

    return dict(all_scraped_stocks), stock_metrics, raw_results
    
