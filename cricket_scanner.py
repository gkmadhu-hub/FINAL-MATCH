import os
import re
import time
import requests
from collections import defaultdict
from bs4 import BeautifulSoup

# ============================================================
# GK FINAL QUALITY STOCKS — 11 CHARTINK SCANNERS (DIRECT API ENGINE)
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://chartink.com",
    "Referer": "https://chartink.com/"
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

def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        r = session.get("https://chartink.com/screener", timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta and meta.get("content"):
            session.headers.update({"X-CSRF-TOKEN": meta["content"]})
    except Exception as e:
        print(f"Session init note: {e}")
    return session

def fetch_scanner(session, name, url):
    print(f"Scraping: {name}...")
    try:
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta and meta.get("content"):
            session.headers.update({"X-CSRF-TOKEN": meta["content"]})

        scan_clause = None
        # Extract the scan_clause from input or script
        clause_input = soup.find("input", {"id": "scan_clause"}) or soup.find("input", {"name": "scan_clause"})
        if clause_input and clause_input.get("value"):
            scan_clause = clause_input["value"]
        else:
            match = re.search(r'scan_clause["\']?\s*:\s*["\']([^"\']+)["\']', r.text)
            if match:
                scan_clause = match.group(1)

        if not scan_clause:
            print(f"⚠️ Scan clause not found for [{name}]")
            return []

        process_url = "https://chartink.com/screener/process"
        payload = {"scan_clause": scan_clause}
        
        resp = session.post(process_url, data=payload, timeout=20)
        data = resp.json()
        
        stocks_data = data.get("data", [])
        rows = []
        for s in stocks_data:
            rows.append({
                "symbol": str(s.get("nsecode", s.get("stock_name", ""))).upper().strip(),
                "price": str(s.get("close", "0")),
                "chg": f"{s.get('per_chg', 0):+.2f}%",
                "vol": str(s.get("volume", "N/A"))
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

    session = get_session()

    for name, url in SCREENS.items():
        stocks = fetch_scanner(session, name, url)
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
        time.sleep(1)

    return dict(all_scraped_stocks), stock_metrics, raw_results
