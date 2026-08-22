import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import cricket_fundamental

# TELEGRAM CONFIGURATION
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
            # Fallback if HTML parsing fails
            payload["parse_mode"] = None
            requests.post(url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def to_scalar(val, default=0.0):
    try:
        if isinstance(val, (pd.Series, pd.DataFrame, np.ndarray)):
            val = val.values.squeeze()
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

def analyze_and_alert(symbol, scanner_hits_count=1):
    try:
        clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
        ticker = yf.Ticker(f"{clean_sym}.NS")
        df = ticker.history(period="1y", interval="1d")

        if df.empty or len(df) < 50:
            return

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price = round(to_scalar(df['Close'].iloc[-1]), 2)
        prev_close = to_scalar(df['Close'].iloc[-2], price)
        change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
        change_str = f"+{change_pct}%" if change_pct >= 0 else f"{change_pct}%"

        # Volume
        volume = int(to_scalar(df['Volume'].iloc[-1]))
        vol_str = f"{volume / 10000000:.1f}Cr" if volume >= 10000000 else f"{volume / 100000:.1f}L"

        # 52W High / Low
        h52 = round(to_scalar(df['High'].max()), 2)
        l52 = round(to_scalar(df['Low'].min()), 2)
        from_high_pct = round(((price - h52) / h52) * 100, 1) if h52 > 0 else 0.0
        h52_str = f"₹{h52} ({from_high_pct}%) / ₹{l52}"

        # Indicators
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = round(to_scalar(rsi_series.iloc[-1]), 2)

        # RVOL
        avg_vol = to_scalar(df['Volume'].rolling(20).mean().iloc[-1])
        rvol = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0
        rvol_passed = "🟢 PASSED" if rvol >= 1.0 else "🟡 NORMAL"

        # ATR (14) - Wilder
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs()
        ], axis=1).max(axis=1)

        atr_series = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
        atr_ma = atr_series.rolling(20).mean()
        atr = round(to_scalar(atr_series.iloc[-1]), 2)

        # EMAs
        ema20 = df['Close'].ewm(span=20, adjust=False).mean()
        ema50 = df['Close'].ewm(span=50, adjust=False).mean()
        ema200 = df['Close'].ewm(span=200, adjust=False).mean()

        # ATR Trend
        cur_atr = to_scalar(atr_series.iloc[-1], atr)
        prev_atr = to_scalar(atr_series.iloc[-2], cur_atr)
        mean_atr = to_scalar(atr_ma.iloc[-1], cur_atr)
        bias = "Bullish" if price >= to_scalar(ema20.iloc[-1]) else "Bearish"

        if cur_atr > prev_atr and cur_atr > mean_atr:
            atr_trend_display = f"🟢 Expanding ({bias}+expanding)"
        elif cur_atr < prev_atr:
            atr_trend_display = f"🔴 Contracting ({bias}+contracting)"
        else:
            atr_trend_display = f"🟡 Normal ({bias}+normal)"

        # EMA STATUS
        v20 = to_scalar(ema20.iloc[-1])
        v50 = to_scalar(ema50.iloc[-1])
        v200 = to_scalar(ema200.iloc[-1])

        if v20 > v50 > v200:
            ema_str = "20 &gt; 50 &gt; 200 EMA (🟢 SUPER BULLISH)"
        elif v20 < v50 < v200:
            ema_str = "20 &lt; 50 &lt; 200 EMA (🔴 Bearish)"
        elif v50 > v20 > v200:
            ema_str = "50 &gt; 20 &gt; 200 EMA (🟡 Pullback in Uptrend)"
        elif v20 > v200 > v50:
            ema_str = "20 &gt; 200 &gt; 50 EMA (🟡 Crossover / Reversal)"
        elif v20 < v200 < v50:
            ema_str = "20 &lt; 200 &lt; 50 EMA (🟠 Breakdown Warning)"
        else:
            ema_str = "EMA STACK WEAK (🔴 Bearish)"

        # MACD
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        m_val = to_scalar(macd.iloc[-1])
        s_val = to_scalar(signal.iloc[-1])
        if m_val >= s_val:
            macd_str = "🟢 Bullish | MACD &gt; Signal"
        else:
            macd_str = "Neutral | MACD &lt; Signal"

        # Supertrend
        supertrend_bullish = calculate_supertrend(df)
        supertrend_str = "🟢 Bullish" if supertrend_bullish else "🔴 Bearish"

        # Risk & Targets
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
        f_metrics = f_data.get('metrics', {})
        marks = f_data.get('marks', {})
        f_score = f_data.get('score', 'N/A')
        f_quality = f_data.get('quality', '⚪ DATA UNAVAILABLE')

        def mark_icon(k):
            m = marks.get(k, None)
            if m is True: return "✅"
            if m is False: return "❌"
            return "⚪"

        pe_val = f"{f_metrics.get('pe')}" if f_metrics.get('pe') is not None else "N/A"
        roce_val = f"{f_metrics.get('roce')}%" if f_metrics.get('roce') is not None else "N/A"
        roe_val = f"{f_metrics.get('roe')}%" if f_metrics.get('roe') is not None else "N/A"
        de_val = f"{f_metrics.get('debt_to_equity')}" if f_metrics.get('debt_to_equity') is not None else "N/A"
        
        sg_ttm = f"{f_metrics.get('sales_growth_ttm')}%" if f_metrics.get('sales_growth_ttm') is not None else "N/A"
        sg_3y = f"{f_metrics.get('sales_growth_3y')}%" if f_metrics.get('sales_growth_3y') is not None else "N/A"
        
        pg_ttm = f"{f_metrics.get('profit_growth_ttm')}%" if f_metrics.get('profit_growth_ttm') is not None else "N/A"
        pg_3y = f"{f_metrics.get('profit_growth_3y')}%" if f_metrics.get('profit_growth_3y') is not None else "N/A"

        opm_val = f"{f_metrics.get('opm')}%" if f_metrics.get('opm') is not None else "N/A"
        
        ic_ttm = f"{f_metrics.get('interest_coverage_ttm')}" if f_metrics.get('interest_coverage_ttm') is not None else "N/A"
        ic_fy = f"{f_metrics.get('interest_coverage_fy')}" if f_metrics.get('interest_coverage_fy') is not None else "N/A"

        p_pledge = f"{f_metrics.get('promoter_pledge')}%" if f_metrics.get('promoter_pledge') is not None else "N/A"
        p_hold = f"{f_metrics.get('promoter_holding')}%" if f_metrics.get('promoter_holding') is not None else "N/A"
        fii_hold = f"{f_metrics.get('fii_holding')}%" if f_metrics.get('fii_holding') is not None else "N/A"
        dii_hold = f"{f_metrics.get('dii_holding')}%" if f_metrics.get('dii_holding') is not None else "N/A"

        cagr_1y = f"{f_metrics.get('price_cagr_1y')}%" if f_metrics.get('price_cagr_1y') is not None else "N/A"
        cagr_3y = f"{f_metrics.get('price_cagr_3y')}%" if f_metrics.get('price_cagr_3y') is not None else "N/A"

        mcap = f"₹{f_metrics.get('market_cap', 0):,} Cr" if f_metrics.get('market_cap') else "N/A"
        
        # Exact Live Industry / Sector
        try:
            info = ticker.info
            live_sector = info.get("industry") or info.get("sector") or f_metrics.get('sector', 'Diversified')
        except Exception:
            live_sector = f_metrics.get('sector', 'Diversified')

        # Live Market Cap Category
        raw_mc = to_scalar(ticker.info.get('marketCap', 0)) if hasattr(ticker, 'info') else 0
        if raw_mc >= 200000000000:
            cap_cat = "🟢 LARGE CAP"
        elif raw_mc >= 50000000000:
            cap_cat = "🟡 MID CAP"
        else:
            cap_cat = "🔵 SMALL CAP"

        tv_link = f"https://in.tradingview.com/chart/?symbol=NSE:{clean_sym}"
        screener_link = f"https://www.screener.in/company/{clean_sym}/consolidated/"

        # Telegram Message Construction
        msg = f"""<b>1. {clean_sym} {cap_cat} • {live_sector}</b>

<a href="{tv_link}">📺 TV</a>   |   <a href="{screener_link}">🏛️ Fundamental</a>

• Price: ₹{price} | {change_str} | Vol: {vol_str}
• 🔥 Scanner Hits: {scanner_hits_count} Scanners
• 🚀 52W High / Low: {h52_str}
_______________________________

🇮🇳 <b>TECHNICALS & LEVELS</b> 🇮🇳
_______________________________

• RSI: {rsi} | RVOL: {rvol}x ({rvol_passed})
• ATR (14): ₹{atr} (Daily Volatility)
• ATR Trend: {atr_trend_display}
• Supertrend: {supertrend_str}
• MACD: {macd_str}
• EMA Stack: {ema_str}
• BUY ZONE: ₹{buy_zone_low} - ₹{buy_zone_high}
_______________________________

• 🛑 SL: ₹{sl} (Risk: ₹{risk} | {sl_pct}%)
• 🎯 T1: ₹{t1} (+{t1_pct}% | RR 1:1.5)
• 🎯 T2: ₹{t2} (+{t2_pct}% | RR 1:2.5)
• 🚀 T3: ₹{t3} (+{t3_pct}% | RR 1:4.0)
_______________________________

🇮🇳 <b>FUNDAMENTAL HEALTH: {f_score}/100 ({f_quality})</b> 🇮🇳
_______________________________

• Market Cap: {mcap}
• P/E: {pe_val} [Target: 10 to 45] {mark_icon('pe')}
• ROCE: {roce_val} [Target: &gt; 15%] {mark_icon('roce')}
• ROE: {roe_val} [Target: &gt; 15%] {mark_icon('roe')}
• Debt/Equity: {de_val} [Target: &lt; 1.0] {mark_icon('debt_to_equity')}
• Sales Growth (TTM / 3Y): {sg_ttm} / {sg_3y} [Target: &gt; 10%] {mark_icon('sales_growth')}
• Profit Growth (TTM / 3Y): {pg_ttm} / {pg_3y} [Target: &gt; 12%] {mark_icon('profit_growth')}
• OPM: {opm_val} [Target: &gt; 15%] {mark_icon('opm')}
• Interest Coverage (TTM / FY): {ic_ttm} / {ic_fy} [Target: &gt; 3.5] {mark_icon('interest_coverage')}
_______________________________

🇮🇳 <b>MOMENTUM & SHAREHOLDING</b> 🇮🇳
_______________________________

• Price CAGR (1Y / 3Y): {cagr_1y} / {cagr_3y}
• Promoter Holding: {p_hold}
• Promoter Pledge: {p_pledge} [Target: &lt; 5.0%] {mark_icon('promoter_pledge')}
• FII Holding: {fii_hold}
• DII Holding: {dii_hold}
"""
        send_telegram_message(msg)
        print(f"Alert sent successfully for {clean_sym}")

    except Exception as e:
        print(f"Error processing {symbol}: {e}")

if __name__ == "__main__":
    analyze_and_alert("HINDZINC", scanner_hits_count=4)
        
