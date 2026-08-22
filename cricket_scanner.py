import os
import re
import time
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# GK FINAL QUALITY STOCKS — 11 CHARTINK SCANNERS
# DUAL-ENGINE: API INTERCEPT + DOM FALLBACK + RETRY
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

def _parse_dom_table(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_=re.compile(r"DataTable|table-striped"))
    if not table or not table.find("tbody"):
        return []

    rows = []
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        
        sym_text = ""
        for td in tds:
            links = td.find_all("a")
            for a in links:
                href = a.get("href", "")
                if "stocks" in href or "chart" in href:
                    sym_text = a.get_text(strip=True).upper()
                    break
            if sym_text:
                break
        
        if not sym_text:
            sym_text = tds[2].get_text(strip=True).upper() if len(tds) > 2 else tds[1].get_text(strip=True).upper()

        if not sym_text or sym_text in ["", "SYMBOL", "NAME", "NO DATA AVAILABLE IN TABLE", "LOADING..."]:
            continue

        chg = tds[4].get_text(strip=True) if len(tds) > 4 else (tds[3].get_text(strip=True) if len(tds) > 3 else "0.0%")
        price = tds[3].get_text(strip=True).replace(",", "") if len(tds) > 4 else (tds[2].get_text(strip=True).replace(",", "") if len(tds) > 2 else "0.0")
        vol = tds[5].get_text(strip=True) if len(tds) > 5 else "N/A"

        rows.append({
            "symbol": sym_text,
            "price": price,
            "chg": chg,
            "vol": vol
        })
    return rows

def fetch_scanner_with_retry(name, url, context, max_retries=2):
    print(f"Scraping: {name}...")
    
    for attempt in range(1, max_retries + 1):
        intercepted_data = []
        page = context.new_page()

        def handle_response(response):
            if "screener/process" in response.url and response.status == 200:
                try:
                    res_json = response.json()
                    if "data" in res_json and isinstance(res_json["data"], list):
                        intercepted_data.extend(res_json["data"])
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Step 1: Check Intercepted API data (Wait up to 4s)
            for _ in range(8):
                if intercepted_data:
                    break
                time.sleep(0.5)

            if intercepted_data:
                rows = []
                for s in intercepted_data:
                    sym = str(s.get("nsecode", s.get("name", s.get("stock_name", "")))).upper().strip()
                    if not sym or sym in ["", "SYMBOL", "NAME"]:
                        continue
                    rows.append({
                        "symbol": sym,
                        "price": str(s.get("close", "0")),
                        "chg": f"{float(s.get('per_chg', s.get('pchange', 0))):+.2f}%",
                        "vol": str(s.get("volume", "N/A"))
                    })
                print(f"-> [API Engine] Found {len(rows)} stocks in {name}")
                page.close()
                return rows

            # Step 2: Fallback to DOM Rendered Content
            try:
                page.wait_for_selector("table.DataTable tbody tr td", timeout=4000)
            except Exception:
                # Trigger Run Scan button if results are stalled
                try:
                    btn = page.query_selector("button:has-text('Run Scan')")
                    if btn:
                        btn.click()
                        time.sleep(2.5)
                except Exception:
                    pass

            dom_rows = _parse_dom_table(page.content())
            if dom_rows:
                print(f"-> [DOM Fallback] Found {len(dom_rows)} stocks in {name}")
                page.close()
                return dom_rows

            page.close()
            if attempt < max_retries:
                time.sleep(1.5)

        except Exception as e:
            print(f"⚠️ Retry {attempt}/{max_retries} error on [{name}]: {e}")
            try:
                page.close()
            except Exception:
                pass
            time.sleep(1)

    print(f"-> Found 0 stocks in {name}")
    return []

def fetch_all_scanners(callback_process_screener=None):
    all_scraped_stocks = defaultdict(list)
    stock_metrics = {}
    raw_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        for name, url in SCREENS.items():
            stocks = fetch_scanner_with_retry(name, url, context)
            raw_results[name] = stocks

            if callback_process_screener:
                callback_process_screener(name, stocks, url)

            for stock in stocks:
                symbol = str(stock["symbol"]).upper().strip()
                if not symbol:
                    continue
                all_scraped_stocks[symbol].append(name)
                stock_metrics[symbol] = {
                    "price": stock.get("price", "0"),
                    "chg": stock.get("chg", "0"),
                    "vol": stock.get("vol", "N/A"),
                }

        browser.close()

    return dict(all_scraped_stocks), stock_metrics, raw_results
