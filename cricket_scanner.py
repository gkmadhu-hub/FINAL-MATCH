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

def fetch_scanner(name, url, page, max_retries=3):
    print(f"🔍 Scraping: {name}...")

    for attempt in range(1, max_retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # Click Run Scan if button exists
            try:
                run_btn = page.locator("button:has-text('Run Scan'), input[value*='Run Scan'], button:has-text('Scan')").first
                if run_btn.is_visible():
                    run_btn.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            # Wait for data table rows to show up
            selectors = [
                "table.DataTable tbody tr",
                "table.dataTable tbody tr",
                "table.table-striped tbody tr",
                "#DataTables_Table_0 tbody tr"
            ]

            for sel in selectors:
                try:
                    page.wait_for_selector(sel, timeout=5000)
                    break
                except Exception:
                    continue

            page.wait_for_timeout(2000)

            # Direct Playwright Evaluation to extract live rendered DOM data
            rows = page.evaluate('''() => {
                const results = [];
                const table = document.querySelector("table.DataTable, table.dataTable, table.table-striped, #DataTables_Table_0");
                if (!table) return results;

                const trs = table.querySelectorAll("tbody tr");
                trs.forEach(tr => {
                    const tds = tr.querySelectorAll("td");
                    if (tds.length >= 3) {
                        let sym = "";
                        const links = tr.querySelectorAll("a");
                        for (let a of links) {
                            const href = a.getAttribute("href") || "";
                            if (href.includes("stocks") || href.includes("chart") || href.includes("nse")) {
                                sym = a.innerText.trim().toUpperCase();
                                break;
                            }
                        }
                        if (!sym && tds.length > 2) {
                            sym = tds[2].innerText.trim().toUpperCase();
                        }

                        if (sym && !["SYMBOL", "NAME", "NO DATA AVAILABLE IN TABLE", "LOADING..."].includes(sym)) {
                            let price = tds.length > 3 ? tds[3].innerText.trim().replace(/,/g, "") : "0";
                            let chg = tds.length > 4 ? tds[4].innerText.trim() : (tds.length > 3 ? tds[3].innerText.trim() : "0%");
                            let vol = tds.length > 5 ? tds[5].innerText.trim() : "N/A";

                            results.append ? results.push({symbol: sym, price: price, chg: chg, vol: vol}) : results.push({symbol: sym, price: price, chg: chg, vol: vol});
                        }
                    }
                });
                return results;
            }''')

            if rows:
                unique_rows = []
                seen = set()
                for r in rows:
                    sym = r["symbol"].replace("NSE:", "").strip()
                    if sym not in seen:
                        seen.add(sym)
                        r["symbol"] = sym
                        unique_rows.append(r)

                print(f"✅ {name}: {len(unique_rows)} stocks found")
                return unique_rows

            print(f"⚠️ {name}: Result table not detected (attempt {attempt}/{max_retries})")
            if attempt < max_retries:
                page.reload(wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)

        except Exception as e:
            print(f"⚠️ Chartink error [{name}] (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                page.wait_for_timeout(2000)

    print(f"❌ Failed to scrape: {name}")
    return []

def fetch_all_scanners(callback_process_screener=None):
    all_scraped_stocks = defaultdict(list)
    stock_metrics = {}
    raw_results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for name, url in SCREENS.items():
            stocks = fetch_scanner(name, url, page)
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
                
