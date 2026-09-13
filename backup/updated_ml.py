import os
import re
import time
from datetime import datetime
from collections import defaultdict
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import cricket_fundamental

# -------------------------------------------------------------
# TELEGRAM CONFIGURATION
# -------------------------------------------------------------
BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
CHAT_ID = "7475999824"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code != 200:
            payload["parse_mode"] = None
            requests.post(url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

# -------------------------------------------------------------
# 1. CHARTINK SCREENERS LIST (ALL 11 SCANNERS)
# -------------------------------------------------------------
SCREENS = [
    {
        "name": "MONTHLY BREAKOUT SCANS WITH VOLUME UPDATED",
        "url": "https://chartink.com/screener/copy-monthly-breakout-scans-with-volume-2220",
    },
    {
        "name": "MONTHLY CPR BREAK UPDATE 1",
        "url": "https://chartink.com/screener/copy-monthly-cpr-break-4",
    },
    {
        "name": "CPR BY KGS R1/PDH BROKEN SWING TRADING",
        "url": "https://chartink.com/screener/copy-cpr-by-kgs-r1-pdh-broken-swing-trading-32",
    },
    {
        "name": "GK WEEKLY CPR BREAKOUT UPDATED",
        "url": "https://chartink.com/screener/copy-weekly-cpr-breakout-50",
    },
    {
        "name": "GK DYNAMIC DASHBOARD STOCKS UPDATED",
        "url": "https://chartink.com/screener/gk-dynamic-dashboard-stocks",
    },
    {
        "name": "GK FINAL QUALITY STOCKS 1",
        "url": "https://chartink.com/screener/gk-final-quality-stocks",
    },
    {
        "name": "THE MOMENTUM TRADER - CPR SWING SCAN(SWING/POSITIONAL) UPDATE",
        "url": "https://chartink.com/screener/copy-the-momentum-trader-cpr-swing-scan-swing-positional-698",
    },
    {
        "name": "DASHBOARD SETUP EARLY BREAKOUT GK PULL BACK UPDATED",
        "url": "https://chartink.com/screener/dashboard-setup-early-breakout-gk",
    },
    {
        "name": "TTM TREND POSITIONAL PICKS UPDATED",
        "url": "https://chartink.com/screener/copy-ttm-trend-positional-picks-30",
    },
    {
        "name": "GK POWERFUL PULLBACK / DIP BUY SCANNER UPDATED",
        "url": "https://chartink.com/screener/gk-powerful-pullback-dip-buy-scanner-updated",
    },
    {
        "name": "INSTITUTIONS CANDLESTICK CONFIRMATION AI",
        "url": "https://chartink.com/screener/institutions-candlestick-confirmation-ai",
    },
]

def clean_name(name):
    return name.replace("Copy - ", "").replace("Copy", "").strip()

def format_volume(vol_str):
    if not vol_str or vol_str == "N/A":
        return "N/A"
    try:
        clean_vol = str(vol_str).replace(",", "").replace("%", "").strip()
        vol = float(clean_vol)
        if vol >= 10000000: return f"{vol / 10000000:.1f}Cr"
        elif vol >= 100000: return f"{vol / 100000:.1f}L"
        elif vol >= 1000: return f"{vol / 1000:.1f}k"
        else: return str(int(vol))
    except Exception:
        return str(vol_str)

def to_scalar(val, default=0.0):
    try:
        if isinstance(val, (pd.Series, pd.DataFrame, np.ndarray, list)):
            val = np.asarray(val).squeeze()
            if hasattr(val, '__len__') and len(val) > 0:
                val = val[-1]
        return float(val) if pd.notna(val) else default
    except Exception:
        return default

def calculate_supertrend(df, period=10, multiplier=3):
    try:
        hl2 = (df['High'] + df['Low']) / 2
        tr = pd.concat([
            df['High'] - df['Low'],
            (df['High'] - df['Close'].shift()).abs(),
            (df['Low'] - df['Close'].shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        upperband = hl2 + (multiplier * atr)
        lowerband = hl2 - (multiplier * atr)

        in_uptrend = True
        for i in range(1, len(df)):
            c_val = to_scalar(df['Close'].iloc[i])
            up_val = to_scalar(upperband.iloc[i - 1])
            low_val = to_scalar(lowerband.iloc[i - 1])

            if c_val > up_val:
                in_uptrend = True
            elif c_val < low_val:
                in_uptrend = False

            if in_uptrend and to_scalar(lowerband.iloc[i]) < low_val:
                lowerband.iloc[i] = low_val
            if not in_uptrend and to_scalar(upperband.iloc[i]) > up_val:
                upperband.iloc[i] = up_val

        return in_uptrend
    except Exception:
        return True

# -------------------------------------------------------------
# 2. SCRAPING CHARTINK
# -------------------------------------------------------------
def scrape_screener_page(page, screen, all_scraped_stocks, stock_metrics, is_first=False):
    page_url = screen["url"]
    screener_name = clean_name(screen["name"])
    stocks = []

    try:
        page.goto(page_url, timeout=60000, wait_until="networkidle")
        wait_ms = 5000 if is_first else 3000
        page.wait_for_timeout(wait_ms)

        try:
            run_btn = page.locator("button:has-text('RUN SCAN'), button.btn-primary:has-text('Run'), button:has-text('Run Scan')").first
            if run_btn.is_visible():
                run_btn.click()
                page.wait_for_timeout(4000 if is_first else 2500)
        except Exception:
            pass

        try:
            page.wait_for_selector("table.dataTable tbody tr, table.table-striped tbody tr", timeout=15000)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        soup = BeautifulSoup(page.content(), "html.parser")
        table = soup.find("table", {"class": lambda x: x and ("table" in x or "dataTable" in x or "DataTable" in x)})

        if table:
            headers = [th.text.strip().lower() for th in table.find_all("th")]
            sym_idx, price_idx, chg_idx, vol_idx = 2, 4, 5, 6

            for i, h in enumerate(headers):
                if any(k in h for k in ["nse", "symbol", "stock"]): sym_idx = i
                elif any(k in h for k in ["price", "close"]): price_idx = i
                elif any(k in h for k in ["chg", "change"]): chg_idx = i
                elif any(k in h for k in ["volume", "vol"]): vol_idx = i

            rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")

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
                            stock_metrics[symbol] = {"price": price, "chg": chg, "vol": vol}

        print(f"-> Found {len(stocks)} stocks in {screener_name}")
    except Exception as e:
        print(f"❌ Error scraping {screener_name}: {e}")

    return stocks

# -------------------------------------------------------------
# 3. SINGLE STOCK DETAILED CARD GENERATOR
# -------------------------------------------------------------
def generate_stock_card(symbol, hits_count):
    try:
        clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
        sym = f"{clean_sym}.NS" if not clean_sym.endswith(".NS") else clean_sym

        df = yf.download(sym, period="2y", interval="1d", progress=False)
        if df is None or df.empty or len(df) < 30:
            time.sleep(1)
            df = yf.download(sym, period="2y", interval="1d", progress=False)

        if df is None or df.empty or len(df) < 30:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.columns = [str(c).capitalize() for c in df.columns]

        close_vals = pd.to_numeric(df['Close'].values.flatten(), errors='coerce')
        close_vals = close_vals[~np.isnan(close_vals)]
        if len(close_vals) == 0:
            return None

        price = round(float(close_vals[-1]), 2)

        close_series = pd.Series(df['Close'].values.flatten(), index=df.index)
        volume_series = pd.Series(df['Volume'].values.flatten(), index=df.index)
        high_series = pd.Series(df['High'].values.flatten(), index=df.index)
        low_series = pd.Series(df['Low'].values.flatten(), index=df.index)

        prev_close = to_scalar(close_series.iloc[-2], price)
        change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
        change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"

        volume = int(to_scalar(volume_series.iloc[-1]))
        vol_str = f"{volume / 10000000:.1f}Cr" if volume >= 10000000 else f"{volume / 100000:.1f}L"

        h52 = round(to_scalar(high_series.tail(252).max()), 2)
        l52 = round(to_scalar(low_series.tail(252).min()), 2)
        from_high_pct = round(((price - h52) / h52) * 100, 1) if h52 > 0 else 0.0
        h52_str = f"₹{h52} ({from_high_pct}%) / ₹{l52}"

        # Technical Indicators
        delta = close_series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = round(to_scalar(rsi_series.iloc[-1]), 1)

        avg_vol = to_scalar(volume_series.shift(1).rolling(20).mean().iloc[-1])
        rvol = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0

        if 1.5 <= rvol <= 3.0:
            rvol_tag = "🟢 IDEAL ACCUMULATION"
        elif 3.0 < rvol <= 5.0:
            rvol_tag = "⚡ STRONG MOMENTUM"
        elif rvol > 5.0:
            rvol_tag = "🔥 HIGH CLIMAX VOLUME"
        else:
            rvol_tag = "🟡 NORMAL"

        tr = pd.concat([
            high_series - low_series,
            (high_series - close_series.shift()).abs(),
            (low_series - close_series.shift()).abs()
        ], axis=1).max(axis=1)
        
        atr_series = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        atr_ma = atr_series.rolling(20).mean()
        atr = round(to_scalar(atr_series.iloc[-1]), 2)

        ema20 = close_series.ewm(span=20, adjust=False).mean()
        ema50 = close_series.ewm(span=50, adjust=False).mean()
        ema200 = close_series.ewm(span=200, adjust=False).mean()

        v20 = to_scalar(ema20.iloc[-1])
        v50 = to_scalar(ema50.iloc[-1])
        v200 = to_scalar(ema200.iloc[-1])

        cur_atr = to_scalar(atr_series.iloc[-1], atr)
        prev_atr = to_scalar(atr_series.iloc[-2], cur_atr)
        mean_atr = to_scalar(atr_ma.iloc[-1], cur_atr)
        bias = "Bullish" if price >= v20 else "Bearish"

        if cur_atr > prev_atr and cur_atr > mean_atr:
            atr_trend_display = f"🟢 Expanding ({bias}+expanding)"
        elif cur_atr < prev_atr:
            atr_trend_display = f"🔴 Contracting ({bias}+contracting)"
        else:
            atr_trend_display = f"🟡 Normal ({bias}+normal)"

        s1 = "&gt;" if v20 > v50 else "&lt;"
        s2 = "&gt;" if v50 > v200 else "&lt;"
        if v20 > v50 > v200:
            ema_str = f"20 {s1} 50 {s2} 200 EMA (🟢 BULLISH)"
        elif v20 < v50 < v200:
            ema_str = f"20 {s1} 50 {s2} 200 EMA (🔴 BEARISH)"
        else:
            ema_str = f"20 {s1} 50 {s2} 200 EMA (🟡 NEUTRAL)"

        ema12 = close_series.ewm(span=12, adjust=False).mean()
        ema26 = close_series.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        m_val = to_scalar(macd.iloc[-1])
        s_val = to_scalar(signal.iloc[-1])
        macd_str = "🟢 Bullish | MACD &gt; Signal" if m_val >= s_val else "🟡 Neutral | MACD &lt; Signal"

        clean_df = pd.DataFrame({'High': high_series, 'Low': low_series, 'Close': close_series})
        supertrend_bullish = calculate_supertrend(clean_df)
        supertrend_str = "🟢 Bullish" if supertrend_bullish else "🔴 Bearish"

        risk = round(1.25 * atr, 2)
        sl = round(price - risk, 2)
        sl_pct = round((risk / price) * 100, 1) if price > 0 else 0.0
        t1 = round(price + (1.5 * risk), 2)
        t1_pct = round(((t1 - price) / price) * 100, 1) if price > 0 else 0.0
        t2 = round(price + (2.5 * risk), 2)
        t2_pct = round(((t2 - price) / price) * 100, 1) if price > 0 else 0.0
        t3 = round(price + (4.0 * risk), 2)
        t3_pct = round(((t3 - price) / price) * 100, 1) if price > 0 else 0.0

        buy_zone_low = round(price - (0.15 * atr), 2)
        buy_zone_high = round(price + (0.15 * atr), 2)

        # Fundamentals Integration
        f_data = cricket_fundamental.get_fundamental_analysis(clean_sym)
        f_metrics = f_data.get('metrics', {}) if f_data else {}
        marks = f_data.get('marks', {}) if f_data else {}
        f_score = f_data.get('score', 0) if f_data else 0
        f_quality = f_data.get('quality', '⚪ DATA UNAVAILABLE') if f_data else '⚪ DATA UNAVAILABLE'

        def mark_icon(k):
            m = marks.get(k, None)
            if m is True: return "✅"
            if m is False: return "❌"
            return "⚪"

        pio_score = f_metrics.get('piotroski')
        if pio_score is not None and str(pio_score) != "N/A":
            try:
                pio_num = int(round(float(pio_score)))
                if pio_num >= 8: pio_line = f"• Piotroski F-Score: {pio_num}/9 (🟢 Strong Health) ✅"
                elif pio_num >= 5: pio_line = f"• Piotroski F-Score: {pio_num}/9 (🟡 Stable Health) ⚠️"
                else: pio_line = f"• Piotroski F-Score: {pio_num}/9 (🔴 Weak Health) ❌"
            except Exception:
                pio_line = f"• Piotroski F-Score: {pio_score}"
        else:
            pio_line = "• Piotroski F-Score: N/A"

        pe_val = f"{f_metrics.get('pe')}" if f_metrics.get('pe') is not None else "N/A"
        roce_val = f"{f_metrics.get('roce')}%" if f_metrics.get('roce') is not None else "N/A"
        roe_val = f"{f_metrics.get('roe')}%" if f_metrics.get('roe') is not None else "N/A"
        de_val = f"{f_metrics.get('debt_to_equity')}" if f_metrics.get('debt_to_equity') is not None else "0.00"
        sg_ttm = f"{f_metrics.get('sales_growth_ttm')}%" if f_metrics.get('sales_growth_ttm') is not None else "N/A"
        sg_3y = f"{f_metrics.get('sales_growth_3y')}%" if f_metrics.get('sales_growth_3y') is not None else "N/A"
        pg_ttm = f"{f_metrics.get('profit_growth_ttm')}%" if f_metrics.get('profit_growth_ttm') is not None else "N/A"
        pg_3y = f"{f_metrics.get('profit_growth_3y')}%" if f_metrics.get('profit_growth_3y') is not None else "N/A"
        opm_val = f"{f_metrics.get('opm')}%" if f_metrics.get('opm') is not None else "N/A"
        ic_ttm = f"{f_metrics.get('interest_coverage_ttm')}" if f_metrics.get('interest_coverage_ttm') is not None else "N/A"
        ic_fy = f"{f_metrics.get('interest_coverage_fy')}" if f_metrics.get('interest_coverage_fy') is not None else "N/A"
        
        pledge_raw = f_metrics.get('pledged_percentage', 0.0)
        p_pledge = f"{pledge_raw}%"
        
        p_hold = f"{f_metrics.get('promoter_holding')}%" if f_metrics.get('promoter_holding') is not None else "N/A"
        fii_hold = f"{f_metrics.get('fii_holding')}%" if f_metrics.get('fii_holding') is not None else "N/A"
        dii_hold = f"{f_metrics.get('dii_holding')}%" if f_metrics.get('dii_holding') is not None else "N/A"
        cagr_1y = f"{f_metrics.get('price_cagr_1y')}%" if f_metrics.get('price_cagr_1y') is not None else "N/A"
        cagr_3y = f"{f_metrics.get('price_cagr_3y')}%" if f_metrics.get('price_cagr_3y') is not None else "N/A"
        mcap = f"₹{f_metrics.get('market_cap', 0):,} Cr" if f_metrics.get('market_cap') else "N/A"

        ticker = yf.Ticker(sym)
        try:
            info = ticker.info or {}
            live_sector = info.get("industry") or info.get("sector") or f_metrics.get('sector', 'Diversified')
            raw_mc = to_scalar(info.get('marketCap', 0))
        except Exception:
            live_sector = f_metrics.get('sector', 'Diversified')
            raw_mc = 0

        if raw_mc >= 200000000000: cap_cat = "🟢 LARGE CAP"
        elif raw_mc >= 50000000000: cap_cat = "🟡 MID CAP"
        else: cap_cat = "🔵 SMALL CAP"

        tv_link = f"<a href='https://in.tradingview.com/chart/?symbol=NSE:{clean_sym}'>TV 📈</a>"
        screener_link = f"<a href='https://www.screener.in/company/{clean_sym}/consolidated/'>Fundamental 🏛️</a>"

        card_body = f"""• {tv_link}   |   {screener_link}

• Price: ₹{price:.2f} | {change_str} | Vol: {vol_str}

• 🔥 Scanner Hits: {hits_count} Scanners

• 🚀 52W High / Low: {h52_str}
_______________________________

• BUY ZONE: ₹{buy_zone_low:.2f} - ₹{buy_zone_high:.2f}

• 🛑 SL: ₹{sl:.2f} (Risk: ₹{risk:.2f} | {sl_pct}%)

• 🎯 T1: ₹{t1:.2f} (+{t1_pct}% | RR 1:1.5)

• 🎯 T2: ₹{t2:.2f} (+{t2_pct}% | RR 1:2.5)

• 🚀 T3: ₹{t3:.2f} (+{t3_pct}% | RR 1:4.0)
_______________________________

<blockquote expandable><b>▼ 🇮🇳 TECHNICALS & LEVELS</b>
_______________________________

• RSI: {rsi} | RVOL: {rvol}x ({rvol_tag})

• ATR (14): ₹{atr} (Daily Volatility)

• ATR Trend: {atr_trend_display}

• Supertrend: {supertrend_str}

• MACD: {macd_str}

• EMA Stack: {ema_str}
</blockquote>

<blockquote expandable><b>▼ 🇮🇳 FUNDAMENTAL HEALTH: {f_score}/100 ({f_quality})</b>
_______________________________

{pio_line}

• Market Cap: {mcap}

• P/E: {pe_val} [Target: 10 to 45] {mark_icon('pe')}

• ROCE: {roce_val} [Target: &gt; 15%] {mark_icon('roce')}

• ROE: {roe_val} [Target: &gt; 15%] {mark_icon('roe')}

• Debt/Equity: {de_val} [Target: &lt; 1.0] {mark_icon('debt_to_equity')}

• Sales Growth (TTM / 3Y): {sg_ttm} / {sg_3y} [Target: &gt; 10%] {mark_icon('sales_growth')}

• Profit Growth (TTM / 3Y): {pg_ttm} / {pg_3y} [Target: &gt; 12%] {mark_icon('profit_growth')}

• OPM: {opm_val} [Target: &gt; 15%] {mark_icon('opm')}

• Interest Coverage (TTM / FY): {ic_ttm} / {ic_fy} [Target: &gt; 3.5] {mark_icon('interest_coverage')}
</blockquote>

<blockquote expandable><b>▼ 🇮🇳 MOMENTUM & SHAREHOLDING</b>
_______________________________

• Price CAGR (1Y / 3Y): {cagr_1y} / {cagr_3y}

• Promoter Holding: {p_hold}

• Pledged percentage: {p_pledge} [Target: &lt; 5.0%] {mark_icon('promoter_pledge')}

• FII Holding: {fii_hold}

• DII Holding: {dii_hold}
</blockquote>"""

        return {
            "symbol": clean_sym,
            "price": price,
            "v200": v200,
            "change_pct": change_pct,
            "rsi": rsi,
            "rvol": rvol,
            "cap_cat": cap_cat,
            "industry": live_sector,
            "card_body": card_body
        }
    except Exception as e:
        print(f"Card error for {symbol}: {e}")
        return None

# -------------------------------------------------------------
# 4. ZONE CARDS DISPATCHER
# -------------------------------------------------------------
def dispatch_zone_cards(zone_name, min_pct, max_pct, zone_stocks):
    if not zone_stocks:
        send_telegram_message(
            "_______________________________\n"
            f"🎯🎯 <b>{zone_name} ({min_pct}% – {max_pct}%)</b> 🎯🎯\n"
            "⚪ <b>0 Stocks Found</b> (No setups matching criteria today)\n"
            "_______________________________"
        )
        return

    header_msg = (
        f"🎯 <b>{zone_name} ({min_pct}% – {max_pct}%)</b>\n\n"
        f"Total Stocks: {len(zone_stocks)}\n"
        "_______________________________"
    )
    send_telegram_message(header_msg)
    time.sleep(1)

    total_stocks = len(zone_stocks)
    for idx, st in enumerate(zone_stocks, 1):
        msg = (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 <b>{st['symbol']}</b> [{idx}/{total_stocks}] {st['cap_cat']} • {st['industry']}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{st['card_body']}"
        )
        send_telegram_message(msg)
        time.sleep(1.2)

    wl_str = ",".join([f"NSE:{s['symbol']}" for s in zone_stocks])
    send_telegram_message(
        f"_______________________________\n"
        f"📋 <b>{zone_name} WATCHLIST</b>\n"
        f"<code>{wl_str}</code>\n"
        f"_______________________________"
    )
    time.sleep(1)

# -------------------------------------------------------------
# 5. MAIN EXECUTOR
# -------------------------------------------------------------
def run_full_stock_radar():
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%d-%b-%Y %I:%M %p")

    init_msg = (
        "<b>MY STOCK RADAR:</b>\n"
        f"🕒 <b>Scan: {now_ist}</b>\n"
        "=============================="
    )
    send_telegram_message(init_msg)
    time.sleep(1)

    all_scraped_stocks = defaultdict(list)
    stock_metrics = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()

        for index, screen in enumerate(SCREENS, start=1):
            screener_name = clean_name(screen["name"])
            page_url = screen["url"]

            stocks = scrape_screener_page(page, screen, all_scraped_stocks, stock_metrics, is_first=(index == 1))
            
            if not stocks:
                block_text = f"<blockquote>🔬 <b>[{index}/11] {screener_name}</b> | <a href='{page_url}'>[📊 Screener]</a>\n⚪ <b>0 Stocks Found</b></blockquote>"
            else:
                block_text = f"<blockquote expandable>🔬 <b>[{index}/11] {screener_name}</b> | <a href='{page_url}'>[📊 Screener]</a>\nTotal Stocks: {len(stocks)}\n\n"
                for i, st in enumerate(stocks, 1):
                    sym = st['symbol']
                    tv_link = f"https://in.tradingview.com/chart/?symbol=NSE:{sym}"
                    screener_link = f"https://www.screener.in/company/{sym}/consolidated/"
                    chg_display = f"+{st['chg']}%" if not str(st['chg']).startswith('-') and not str(st['chg']).startswith('+') else f"{st['chg']}%"
                    block_text += f"{i}. <b>{sym}</b> (<a href='{tv_link}'>TV</a> | <a href='{screener_link}'>Fundamentals</a>) | ₹{st['price']} | {chg_display} | Vol: {format_volume(st['vol'])}\n"
                block_text += "</blockquote>"

            send_telegram_message(block_text)
            time.sleep(0.8)

        browser.close()

    unique_symbols = list(all_scraped_stocks.keys())
    total_unique_count = len(unique_symbols)
    print(f"Total Unique Stocks Found: {total_unique_count}")

    analyzed_stocks = []
    for sym in unique_symbols:
        hits_count = len(all_scraped_stocks[sym])
        res = generate_stock_card(sym, hits_count)
        if res:
            analyzed_stocks.append(res)
        time.sleep(0.4)

    filtered_stocks = []
    for s in analyzed_stocks:
        sym = s.get('symbol')
        rsi = s.get('rsi', 0)
        rvol = s.get('rvol', 0)
        price = s.get('price', 0)
        v200 = s.get('v200', 0)

        pass_rsi = (55.0 <= rsi <= 68.0)
        pass_rvol = (rvol >= 1.5)
        pass_ema = (price > v200)

        if pass_rsi and pass_rvol and pass_ema:
            filtered_stocks.append(s)
            print(f"✅ PASSED MASTER FILTER: {sym}")
        else:
            print(f"❌ REJECTED {sym}")

    print(f"Passed Master Filter: {len(filtered_stocks)}")

    sweet_spot = [s for s in filtered_stocks if 1.0 <= s['change_pct'] <= 4.99]
    fast_momentum = [s for s in filtered_stocks if 5.0 <= s['change_pct'] <= 7.99]
    high_breakout = [s for s in filtered_stocks if 8.0 <= s['change_pct'] <= 12.00]

    main_header = (
        f"📊 <b>TOTAL UNIQUE STOCKS SCANNED: {total_unique_count}</b>\n"
        "==============================\n"
        "🎯🎯 <b>HIGH CONFIDENCE TECHNICAL & FUNDAMENTAL PICKS</b> 🎯🎯\n"
        "=============================="
    )
    send_telegram_message(main_header)
    time.sleep(1)

    dispatch_zone_cards("SWEET SPOT ZONE", "1.0%", "4.99%", sweet_spot)
    dispatch_zone_cards("FAST MOMENTUM ZONE", "5.0%", "7.99%", fast_momentum)
    dispatch_zone_cards("HIGH MOMENTUM BREAKOUT ZONE", "8.0%", "12.0%", high_breakout)

    print("Full Radar cycle completed successfully!")

if __name__ == "__main__":
    run_full_stock_radar()
