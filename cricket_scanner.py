import os
import re
import time
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# GK FINAL QUALITY STOCKS — 11 CHARTINK SCANNERS
# ============================================================

SCREENS = {
    "MONTHLY BREAKOUT SCANS WITH VOLUME UPDATED": "https://chartink.com/screener/monthly-breakout-scans-with-volume-updated",
    "MONTHLY CPR BREAK UPDATE 1": "https://chartink.com/screener/monthly-cpr-break-update-1",
    "CPR BY KGS R1/PDH BROKEN SWING TRADING": "https://chartink.com/screener/cpr-by-kgs-r1-pdh-broken-swing-trading",
    "GK WEEKLY CPR BREAKOUT UPDATED": "https://chartink.com/screener/gk-weekly-cpr-breakout-updated",
    "GK DYNAMIC DASHBOARD STOCKS UPDATED": "https://chartink.com/screener/gk-dynamic-dashboard-stocks-updated",
    "GK FINAL QUALITY STOCKS 1": "https://chartink.com/screener/gk-final-quality-stocks",
    "THE MOMENTUM TRADER - CPR SWING SCAN(SWING/POSITIONAL) UPDATE": "https://chartink.com/screener/the-momentum-trader-cpr-swing-scanswingpositional-update",
    "DASHBOARD SETUP EARLY BREAKOUT GK PULL BACK UPDATED": "https://chartink.com/screener/dashboard-setup-early-breakout-gk-pull-back-updated",
    "TTM TREND POSITIONAL PICKS UPDATED": "https://chartink.com/screener/ttm-trend-positional-picks-updated",
    "GK POWERFUL PULLBACK / DIP BUY SCANNER UPDATED": "https://chartink.com/screener/gk-powerful-pullback-dip-buy-scanner-updated",
    "INSTITUTIONS CANDLESTICK CONFIRMATION AI": "https://chartink.com/screener/institutions-candlestick-confirmation-ai"
}

def format_volume(val):
    if val is None or val == "N/A":
        return "N/A"
    try:
        val_str = str(val).replace(",", "").replace("%", "").strip()
        num = float(val_str)
        if num >= 10000000:
            return f"{num / 10000000:.2f}Cr"
        elif num >= 100000:
            return f"{num / 100000:.2f}L"
        elif num >= 1000:
            return f"{num / 1000:.1f}k"
        return f"{num:.0f}"
    except Exception:
        return str(val)

def fetch_scanner(name, url, page):
    print(f"Scraping: {name}...")
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Click Run Scan if available to trigger results
        try:
            btn = page.query_selector("button:has-text('Run Scan')")
            if btn:
                btn.click()
                page.wait_for_timeout(2500)
        except Exception:
            pass

        # Wait for data rows to render
        try:
            page.wait_for_selector("table.DataTable tbody tr td", timeout=12000)
        except Exception:
            time.sleep(3)

        soup = BeautifulSoup(page.content(), "html.parser")
        table = soup.find("table", class_=re.compile(r"DataTable|table-striped"))
        
        if not table or not table.find("tbody"):
            return []

        rows = []
        for tr in table.find("tbody").find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 4:
                sym_text = ""
                # Search for symbol cell
                for td in tds:
                    links = td.find_all("a")
                    for a in links:
                        href = a.get("href", "")
                        if "stocks" in href or "chart" in href:
                            sym_text = a.get_text(strip=True).upper()
                            break
                    if sym_text:
                        break
                
                if not sym_text and len(tds) >= 3:
                    sym_text = tds[2].get_text(strip=True).upper()

                if not sym_text or sym_text in ["", "SYMBOL", "NAME", "NO DATA AVAILABLE IN TABLE", "LOADING..."]:
                    continue

                chg = tds[4].get_text(strip=True) if len(tds) > 4 else tds[3].get_text(strip=True)
                price = tds[3].get_text(strip=True).replace(",", "") if len(tds) > 4 else tds[2].get_text(strip=True).replace(",", "")
                vol = tds[5].get_text(strip=True) if len(tds) > 5 else "N/A"

                rows.append({
                    "symbol": sym_text,
                    "price": price,
                    "chg": chg,
                    "vol": vol
                })

        print(f"-> Found {len(rows)} stocks in {name}")
        return rows

    except Exception as e:
        print(f"Scanner error [{name}]: {e}")
        return []

def fetch_all_scanners(callback_process_screener=None):
    all_scraped_stocks = defaultdict(list)
    stock_metrics = {}
    raw_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        for name, url in SCREENS.items():
            stocks = fetch_scanner(name, url, page)
            raw_results[name] = stocks

            if callback_process_screener:
                callback_process_screener(name, stocks, url)

            for stock in stocks:
                symbol = str(stock["symbol"]).upper().strip()
                all_scraped_stocks[symbol].append(name)
                stock_metrics[symbol] = {
                    "price": stock.get("price", "0"),
                    "chg": stock.get("chg", "0"),
                    "vol": stock.get("vol", "N/A"),
                }

        browser.close()

    return dict(all_scraped_stocks), stock_metrics, raw_results
                    
