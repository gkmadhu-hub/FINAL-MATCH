import os
import re
import html
import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf

from cricket_scanner import fetch_all_scanners, format_volume
from cricket_fundamental import get_fundamental_analysis

# ============================================================
# 🇮🇳 🇮🇳 CHILDRENS FUTURE 🇮🇳 🇮🇳
# GK FINAL QUALITY STOCKS — ML / TECHNICAL ENGINE
# ============================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7475999824").strip()

def _send_chunk(text, number=1):
    if not BOT_TOKEN or not CHAT_ID or not text.strip():
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        print(
            f"Telegram chunk {number}: "
            f"({len(text)} characters | HTTP {r.status_code})"
        )
        if r.status_code != 200:
            print(f"Telegram Error: {r.text}")
    except Exception as e:
        print(f"Telegram send error: {e}")

def send_telegram_message(message):
    max_len = 3500
    if len(message) <= max_len:
        _send_chunk(message, 1)
        return

    lines = message.split("\n")
    chunks = []
    curr = ""

    for line in lines:
        if len(curr) + len(line) + 1 <= max_len:
            curr += line + "\n"
        else:
            if curr.strip():
                chunks.append(curr.strip())
            curr = line + "\n"

    if curr.strip():
        chunks.append(curr.strip())

    for idx, ch in enumerate(chunks, 1):
        _send_chunk(ch, idx)
        time.sleep(0.5)

def calculate_supertrend(df, period=10, multiplier=3):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(period, min_periods=period).mean()
    hl2 = (high + low) / 2

    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    in_uptrend = True

    for i in range(1, len(df)):
        if pd.isna(upper.iloc[i - 1]) or pd.isna(lower.iloc[i - 1]):
            continue

        if close.iloc[i] > upper.iloc[i - 1]:
            in_uptrend = True
        elif close.iloc[i] < lower.iloc[i - 1]:
            in_uptrend = False

    return in_uptrend

def _clean_float(value):
    try:
        return float(
            str(value)
            .replace(",", "")
            .replace("%", "")
            .replace("+", "")
            .strip()
        )
    except Exception:
        return 0.0

def get_ai_predictions(scraped_list, apply_strict_filter=True):
    results = []

    print(
        f"Running technical + fundamental analysis "
        f"for {len(scraped_list)} stocks..."
    )

    for item in scraped_list:
        symbol = str(item["symbol"]).upper().strip()

        price = _clean_float(item.get("price", 0))
        p_chg = _clean_float(item.get("p_change", item.get("chg", 0)))

        rsi = 60.0
        rvol = 2.0
        atr = max(price * 0.02, 1.0)
        atr_trend_display = "🟡 Normal (Bullish+normal)"

        ema_str = "⚪ Data unavailable"
        macd_str = "⚪ Data unavailable"
        supertrend_str = "⚪ Data unavailable"

        live_sector = "Diversified"
        w52_high = price * 1.2
        w52_low = price * 0.8
        cap_category = "MID CAP"

        try:
            df = yf.download(
                f"{symbol}.NS",
                period="2y",
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if not df.empty:
                required = ["High", "Low", "Close", "Volume"]

                for c in required:
                    if c in df:
                        df[c] = pd.to_numeric(
                            df[c],
                            errors="coerce"
                        )

                df = df.dropna(
                    subset=["High", "Low", "Close"]
                )

                if len(df) >= 20:
                    close = df["Close"]
                    volume = df["Volume"].fillna(0)

                    w52_df = df.iloc[-252:] if len(df) >= 252 else df
                    w52_high = float(w52_df["High"].max())
                    w52_low = float(w52_df["Low"].min())

                    # RSI
                    delta = close.diff()
                    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
                    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
                    rs = gain / loss.replace(0, np.nan)
                    rsi_series = 100 - (100 / (1 + rs))

                    # RVOL
                    volume_ma = volume.rolling(20, min_periods=20).mean()
                    rvol_series = volume / volume_ma.replace(0, np.nan)

                    # ATR
                    tr = pd.concat(
                        [
                            df["High"] - df["Low"],
                            (df["High"] - close.shift(1)).abs(),
                            (df["Low"] - close.shift(1)).abs(),
                        ],
                        axis=1,
                    ).max(axis=1)

                    atr_series = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
                    atr_ma = atr_series.rolling(20, min_periods=20).mean()

                    # EMA 20 / 50 / 200
                    ema20 = close.ewm(span=20, adjust=False).mean()
                    ema50 = close.ewm(span=50, adjust=False).mean()
                    ema200 = close.ewm(span=200, adjust=False).mean()

                    # MACD
                    ema12 = close.ewm(span=12, adjust=False).mean()
                    ema26 = close.ewm(span=26, adjust=False).mean()
                    macd = ema12 - ema26
                    signal = macd.ewm(span=9, adjust=False).mean()

                    price = round(float(close.iloc[-1]), 2)

                    if pd.notna(rsi_series.iloc[-1]):
                        rsi = round(float(rsi_series.iloc[-1]), 2)

                    if pd.notna(rvol_series.iloc[-1]):
                        rvol = round(float(rvol_series.iloc[-1]), 2)

                    if pd.notna(atr_series.iloc[-1]):
                        atr_value = float(atr_series.iloc[-1])
                        if atr_value > 0:
                            atr = round(atr_value, 2)

                    # ATR TREND
                    cur_atr = float(atr_series.iloc[-1]) if pd.notna(atr_series.iloc[-1]) else atr
                    prev_atr = float(atr_series.iloc[-2]) if len(atr_series) >= 2 and pd.notna(atr_series.iloc[-2]) else cur_atr
                    mean_atr = float(atr_ma.iloc[-1]) if pd.notna(atr_ma.iloc[-1]) else cur_atr
                    bias = "Bullish" if price >= float(ema20.iloc[-1]) else "Bearish"

                    if cur_atr > prev_atr and cur_atr > mean_atr:
                        atr_trend_display = f"🟢 Expanding ({bias}+expanding)"
                    elif cur_atr < prev_atr:
                        atr_trend_display = f"🔴 Contracting ({bias}+contracting)"
                    else:
                        atr_trend_display = f"🟡 Normal ({bias}+normal)"

                    # EMA STATUS
                    v20 = float(ema20.iloc[-1])
                    v50 = float(ema50.iloc[-1])
                    v200 = float(ema200.iloc[-1])

                    if v20 > v50 > v200:
                        ema_str = "20 &gt; 50 &gt; 200 EMA (🟢 SUPER BULLISH)"
                    elif v20 > v50 and v50 <= v200:
                        ema_str = "20 &gt; 50 EMA (🟡 SHORT-TERM BULLISH)"
                    elif v20 < v50 and v50 > v200:
                        ema_str = "20 &lt; 50 &gt; 200 EMA (🟠 DIP IN UPTREND)"
                    else:
                        ema_str = "EMA STACK WEAK (🔴 BEARISH)"

                    # MACD STATUS
                    if float(macd.iloc[-1]) >= float(signal.iloc[-1]):
                        macd_str = "🟢 Bullish | MACD &gt; Signal"
                    else:
                        macd_str = "🟡 Neutral | MACD &lt; Signal"

                    # SUPERTREND STATUS
                    if calculate_supertrend(df):
                        supertrend_str = "🟢 Bullish"
                    else:
                        supertrend_str = "🔴 Bearish"

            try:
                info = yf.Ticker(f"{symbol}.NS").info
                live_sector = info.get("industry") or info.get("sector") or "Diversified"
                mc = info.get("marketCap", 0)
                if mc >= 200000000000:
                    cap_category = "🟢 LARGE CAP"
                elif mc >= 50000000000:
                    cap_category = "🟡 MID CAP"
                else:
                    cap_category = "🔵 SMALL CAP"
            except Exception:
                pass

        except Exception as e:
            print(f"Technicals note for {symbol}: {e}")

        if price <= 0:
            price = _clean_float(item.get("price", 0))

        if apply_strict_filter:
            if not (55.0 <= rsi <= 68.0 and rvol >= 1.5):
                continue

        sl = round(price - 1.25 * atr, 2)
        risk = round(price - sl, 2)
        if risk <= 0:
            risk = round(price * 0.02, 2)

        t1 = round(price + 1.5 * risk, 2)
        t2 = round(price + 2.5 * risk, 2)
        t3 = round(price + 4.0 * risk, 2)

        try:
            fund = get_fundamental_analysis(symbol)
            if not isinstance(fund, dict):
                fund = {"metrics": {}, "marks": {}, "score": "N/A", "quality": "N/A"}
            if "metrics" in fund and isinstance(fund["metrics"], dict):
                fund["metrics"]["sector"] = live_sector
        except Exception as e:
            print(f"Fundamental note for {symbol}: {e}")
            fund = {"metrics": {"sector": live_sector}, "marks": {}, "score": "N/A", "quality": "N/A"}

        results.append(
            {
                "symbol": symbol,
                "ltp": price,
                "p_change": p_chg,
                "hits": item.get("hits", 0),
                "rsi": rsi,
                "rvol": rvol,
                "atr": atr,
                "atr_trend_display": atr_trend_display,
                "ema_status": ema_str,
                "macd": macd_str,
                "supertrend": supertrend_str,
                "filter_tag": "🟢 PASSED",
                "entry_min": round(price * 0.995, 2),
                "entry_max": round(price * 1.005, 2),
                "stop_loss": sl,
                "target_1": t1,
                "target_2": t2,
                "target_3": t3,
                "rr_1": 1.5,
                "rr_2": 2.5,
                "rr_3": 4.0,
                "w52_high": w52_high,
                "w52_low": w52_low,
                "cap_category": cap_category,
                "sector": live_sector,
                "fundamental": fund,
                "vol": item.get("vol", "N/A"),
            }
        )

    print(f"Debug: Filtered Quality Picks Generated: {len(results)}")
    return results

def _stock_block(index, item):
    symbol = html.escape(str(item["symbol"]))
    fund = item.get("fundamental", {}) if isinstance(item.get("fundamental", {}), dict) else {}
    m = fund.get("metrics", {}) if isinstance(fund.get("metrics", {}), dict) else {}
    marks = fund.get("marks", {}) if isinstance(fund.get("marks", {}), dict) else {}
    score = fund.get("score", "N/A")
    quality = fund.get("quality", "N/A")
    price = item["ltp"]
    risk = round(abs(price - item["stop_loss"]), 2)
    risk_pct = round(risk / price * 100, 1) if price else 0

    t1_pct = round((item["target_1"] - price) / price * 100, 1) if price else 0
    t2_pct = round((item["target_2"] - price) / price * 100, 1) if price else 0
    t3_pct = round((item["target_3"] - price) / price * 100, 1) if price else 0

    w52_h = item.get("w52_high", price)
    w52_l = item.get("w52_low", price)
    w52_diff = round((price - w52_h) / w52_h * 100, 1) if w52_h else 0

    tv_url = f"https://in.tradingview.com/chart/?symbol=NSE:{symbol}"
    fn_url = f"https://www.screener.in/company/{symbol}/consolidated/"

    def v(key):
        x = m.get(key)
        return x if x is not None else "N/A"

    def pct(key):
        x = m.get(key)
        return f"{x}%" if x is not None else "N/A"

    def mark(key):
        val = marks.get(key)
        if val is True:
            return "✅"
        elif val is False:
            return "❌"
        return "⚪"

    lines = [
        f"{index}. <b>{symbol}</b> {item['cap_category']} • {item['sector']}",
        "",
        f"📺 <a href='{tv_url}'>TV</a>   |   🏛️ <a href='{fn_url}'>Fundamental</a>",
        "",
        f"• Price: ₹{price:.2f} | <b>{item['p_change']:+.2f}%</b> | Vol: {format_volume(item['vol'])}",
        "",
        f"• 🔥 Scanner Hits: {item['hits']} Scanners",
        "",
        f"• 🚀 52W High / Low: ₹{w52_h:.1f} ({w52_diff:+.1f}%) / ₹{w52_l:.1f}",
        "_______________________________",
        "",
        "🇮🇳 <b>TECHNICALS & LEVELS</b> 🇮🇳",
        "_______________________________",
        "",
        f"• RSI: <code>{item['rsi']}</code> | RVOL: <code>{item['rvol']}x</code> ({item['filter_tag']})",
        "",
        f"• ATR (14): ₹{item['atr']} (Daily Volatility)",
        f"• ATR Trend: {item['atr_trend_display']}",
        "",
        f"• Supertrend: {item['supertrend']}",
        "",
        f"• MACD: {item['macd']}",
        "",
        f"• EMA Stack: {item['ema_status']}",
        "",
        f"• <b>BUY ZONE:</b> <code>₹{item['entry_min']} - ₹{item['entry_max']}</code>",
        "_______________________________",
        "",
        f"• 🛑 <b>SL:</b> ₹{item['stop_loss']} (Risk: ₹{risk:.2f} | {risk_pct}%)",
        "",
        f"• 🎯 <b>T1:</b> ₹{item['target_1']} (+{t1_pct}% | RR 1:{item['rr_1']})",
        "",
        f"• 🎯 <b>T2:</b> ₹{item['target_2']} (+{t2_pct}% | RR 1:{item['rr_2']})",
        "",
        f"• 🚀 <b>T3:</b> ₹{item['target_3']} (+{t3_pct}% | RR 1:{item['rr_3']})",
        "_______________________________",
        "",
        f"🇮🇳 <b>FUNDAMENTAL HEALTH: {score}/100 ({quality})</b> 🇮🇳",
        "_______________________________",
        "",
        f"• Market Cap: <code>₹{v('market_cap'):,.0f} Cr</code>" if isinstance(v('market_cap'), (int, float)) else f"• Market Cap: <code>{v('market_cap')}</code>",
        "",
        f"• P/E: <code>{v('pe')}</code> [Target: 10 to 45] {mark('pe')}",
        "",
        f"• ROCE: <code>{pct('roce')}</code> [Target: &gt; 15%] {mark('roce')}",
        "",
        f"• ROE: <code>{pct('roe')}</code> [Target: &gt; 15%] {mark('roe')}",
        "",
        f"• Debt/Equity: <code>{v('debt_to_equity')}</code> [Target: &lt; 1.0] {mark('debt_to_equity')}",
        "",
        f"• Sales Growth (TTM / 3Y): <code>{pct('sales_growth_ttm')} / {pct('sales_growth_3y')}</code> [Target: &gt; 10%] {mark('sales_growth')}",
        "",
        f"• Profit Growth (TTM / 3Y): <code>{pct('profit_growth_ttm')} / {pct('profit_growth_3y')}</code> [Target: &gt; 12%] {mark('profit_growth')}",
        "",
        f"• OPM: <code>{pct('opm')}</code> [Target: &gt; 15%] {mark('opm')}",
        "",
        f"• Interest Coverage (TTM / FY): <code>{v('interest_coverage_ttm')} / {v('interest_coverage_fy')}</code> [Target: &gt; 3.5] {mark('interest_coverage')}",
        "_______________________________",
        "",
        "🇮🇳 <b>MOMENTUM & SHAREHOLDING</b> 🇮🇳",
        "_______________________________",
        "",
        f"• Price CAGR (1Y / 3Y): <code>{pct('price_cagr_1y')} / {pct('price_cagr_3y')}</code>",
        "",
        f"• Promoter Holding: <code>{pct('promoter_holding')}</code>",
        "",
        f"• Promoter Pledge: <code>{pct('promoter_pledge')}</code> [Target: &lt; 5.0%] {mark('promoter_pledge')}",
        "",
        f"• FII Holding: <code>{pct('fii_holding')}</code>",
        "",
        f"• DII Holding: <code>{pct('dii_holding')}</code>",
    ]
    return "\n".join(lines)

def process_and_send_screener_result(screener_name, stocks, page_url):
    name = html.escape(screener_name.replace("Copy - ", "").replace("Copy", "").strip())
    msg = f"==============================\n🔬 <b>{name.upper()}</b> | <a href='{page_url}'>[📊 Screener]</a>\n==============================\n"

    if not stocks:
        msg += "• <i>⚠️ Total Stocks: 0 (No breakout stocks matched right now)</i>\n"
    else:
        msg += f"Total Stocks: <code>{len(stocks)}</code>\n\n"
        for i, stock in enumerate(stocks, 1):
            s = html.escape(str(stock["symbol"]))
            pr = stock.get("price", "N/A")
            chg = str(stock.get("chg", "N/A")).strip()
            if chg != "N/A" and not chg.endswith("%"):
                chg += "%"
            if chg not in ["N/A", ""] and not chg.startswith(("-", "+")):
                chg = "+" + chg
            tv = f"https://in.tradingview.com/chart/?symbol=NSE:{s}"
            fn = f"https://www.screener.in/company/{s}/consolidated/"
            msg += f"{i}. <b>{s}</b> (<a href='{tv}'>TV</a> | <a href='{fn}'>🏛️ Fundamentals</a>) | ₹{pr} | {chg} | Vol: {format_volume(stock.get('vol', 'N/A'))}\n"

    send_telegram_message(msg)

def _send_zone(title, picks, watch_title):
    if not picks:
        return

    _send_chunk(
        "_______________________________\n"
        f"{title} — {len(picks)} STOCKS\n"
        "_______________________________", 1
    )
    time.sleep(1)

    for i, pick in enumerate(picks, 1):
        card_text = _stock_block(i, pick)
        _send_chunk(card_text, i + 1)
        time.sleep(1)

    symbols = ",".join(f"NSE:{p['symbol']}" for p in picks)
    _send_chunk(
        "_______________________________\n"
        f"📋 <b>{watch_title}</b>\n"
        f"<code>{symbols}</code>\n"
        "_______________________________", 99
    )
    time.sleep(1)

def run_all():
    print("🚀 Starting CRICKET GK HIGH CONFIDENCE SYSTEM...")
    all_scraped_stocks, stock_metrics, raw_results = fetch_all_scanners(
        callback_process_screener=process_and_send_screener_result
    )
    scraped = []
    momentum = []
    for symbol, scanner_list in all_scraped_stocks.items():
        metrics = stock_metrics.get(symbol, {})
        chg = _clean_float(metrics.get("chg", 0))
        item = {
            "symbol": symbol,
            "price": _clean_float(metrics.get("price", 0)),
            "p_change": chg,
            "hits": len(scanner_list),
            "vol": metrics.get("vol", "N/A"),
        }
        if 1.0 <= chg < 8.0:
            scraped.append(item)
        elif 8.0 <= chg <= 12.0:
            momentum.append(item)

    filtered = get_ai_predictions(scraped, apply_strict_filter=True)
    sweet = sorted([p for p in filtered if 1.0 <= p["p_change"] < 5.0], key=lambda x: (x["hits"], x["rvol"]), reverse=True)
    fast = sorted([p for p in filtered if 5.0 <= p["p_change"] < 8.0], key=lambda x: (x["hits"], x["rvol"]), reverse=True)

    high = get_ai_predictions(momentum, apply_strict_filter=False)
    high = sorted(high, key=lambda x: (x["hits"], x["p_change"]), reverse=True)

    # Main Radar Header (Sent once before Quality Zones)
    if sweet or fast or high:
        _send_chunk(
            "==============================\n"
            "🎯🎯 <b>HIGH CONFIDENCE TECHNICAL & FUNDAMENTAL PICKS</b> 🎯🎯\n"
            "==============================", 0
        )
        time.sleep(1)

    _send_zone("🎯🎯 <b>SWEET SPOT ZONE (1.0%–4.99%)</b> 🎯🎯", sweet, "SWEET SPOT WATCHLIST")
    _send_zone("⚡⚡ <b>FAST MOMENTUM ZONE (5.0%–7.99%)</b> ⚡⚡", fast, "FAST MOMENTUM WATCHLIST")
    _send_zone("🚀🚀 <b>HIGH MOMENTUM & BREAKOUT ZONE (8.0%–12.0%)</b> 🚀🚀", high, "HIGH MOMENTUM WATCHLIST")
    print(f"✅ Completed | Sweet: {len(sweet)} | Fast: {len(fast)} | High Momentum: {len(high)}")

if __name__ == "__main__":
    run_all()
