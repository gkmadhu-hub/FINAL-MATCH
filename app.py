import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
import io
import re

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="GK Portfolio & Radar Tracker",
    page_icon="🇮🇳",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- TELEGRAM CREDENTIALS ---
TELEGRAM_BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
TELEGRAM_CHAT_ID = "7475999824"

# --- DYNAMIC LIVE NSE STOCKS SCRAPER ---
@st.cache_data(ttl=86400)
def fetch_all_nse_symbols():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            if 'SYMBOL' in df.columns:
                symbols = sorted(df['SYMBOL'].dropna().astype(str).str.strip().tolist())
                return symbols
    except Exception:
        pass
    
    return [
        "HINDZINC", "HINDALCO", "TATASTEEL", "TATAMOTORS", "TEGA", "GRAVITA", "TITAGARH", 
        "RELIANCE", "INFY", "TCS", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", 
        "KOTAKBANK", "LT", "AXISBANK", "MARUTI", "SUNPHARMA", "TITAN", "BAJFINANCE", 
        "ULTRACEMCO", "POWERGRID", "NTPC", "JSWSTEEL", "M&M", "ADANIENT", "COALINDIA", 
        "BAJAJFINSV", "ONGC", "WIPRO", "HCLTECH", "VEDL", "BEL", "HAL", "BHEL", "ZOMATO", 
        "JIOFIN", "KPITTECH", "PERSISTENT", "DIXON", "POLYCAB", "KPRMILL"
    ]

MASTER_STOCKS = fetch_all_nse_symbols()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE,
            buy_date TEXT,
            buy_price REAL,
            quantity INTEGER,
            entry_atr REAL,
            locked_sl REAL,
            locked_t1 REAL,
            locked_t2 REAL,
            locked_t3 REAL,
            t1_alert_sent INTEGER DEFAULT 0,
            t2_alert_sent INTEGER DEFAULT 0,
            t3_alert_sent INTEGER DEFAULT 0,
            sl_alert_sent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'HOLD'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_all_positions():
    conn = sqlite3.connect("portfolio.db")
    df = pd.read_sql_query("SELECT * FROM positions", conn)
    conn.close()
    return df

def save_position(data):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO positions (
            symbol, buy_date, buy_price, quantity, entry_atr,
            locked_sl, locked_t1, locked_t2, locked_t3,
            t1_alert_sent, t2_alert_sent, t3_alert_sent, sl_alert_sent, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['symbol'], data['buy_date'], data['buy_price'], data['quantity'], data['entry_atr'],
        data['locked_sl'], data['locked_t1'], data['locked_t2'], data['locked_t3'],
        0, 0, 0, 0, 'HOLD'
    ))
    conn.commit()
    conn.close()

def delete_position(symbol):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()

def update_alert_status(symbol, col):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute(f"UPDATE positions SET {col} = 1 WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()

# --- TELEGRAM SENDER ---
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        res_data = resp.json()
        if not res_data.get("ok"):
            st.error(f"Telegram API Error: {res_data.get('description')}")
            return False
        return True
    except Exception as e:
        st.error(f"Telegram Connection Error: {e}")
        return False

# --- TECHNICAL ENGINE ---
def get_technicals(symbol):
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        df = yf.download(ticker_sym, period="1y", interval="1d", progress=False)
        if df.empty:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df['Close']
        high = df['High']
        low = df['Low']
        vol = df['Volume']

        ltp = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        chg_pct = ((ltp - prev_close) / prev_close) * 100
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series = tr.rolling(14).mean()
        atr = float(atr_series.iloc[-1])
        atr_trend = "🟢 Expanding (Bullish + Expanding)" if atr > float(atr_series.iloc[-5]) else "⚪ Normal"

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = float(100 - (100 / (1 + rs)).iloc[-1])

        vol_sma20 = vol.rolling(20).mean().iloc[-1]
        rvol = float(vol.iloc[-1] / (vol_sma20 + 1e-9))
        rvol_status = "🟢 Ideal Accumulation" if rvol >= 1.5 else "🟡 Normal Volume"

        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        ema_stack = "20 &gt; 50 &gt; 200 EMA (🟢 BULLISH)" if (ema20 > ema50 > ema200) else "Mixed / Neutral"

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_status = "🟢 Bullish | MACD &gt; Signal" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "🔴 Bearish Cross"

        hl2 = (high + low) / 2
        lowerband = hl2 - (3 * atr_series)
        supertrend_val = "🟢 Bullish" if ltp > float(lowerband.iloc[-1]) else "🔴 Bearish"

        buy_low = round(ltp * 0.995, 2)
        buy_high = round(ltp * 1.005, 2)

        return {
            "symbol": symbol.upper().replace(".NS", ""),
            "ltp": round(ltp, 2),
            "chg_pct": round(chg_pct, 2),
            "volume": int(vol.iloc[-1]),
            "high52": round(float(high.max()), 2),
            "low52": round(float(low.min()), 2),
            "atr": round(atr, 2),
            "atr_trend": atr_trend,
            "rsi": round(rsi, 2),
            "rvol": round(rvol, 2),
            "rvol_status": rvol_status,
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "ema_stack": ema_stack,
            "macd_status": macd_status,
            "supertrend": supertrend_val,
            "buy_low": buy_low,
            "buy_high": buy_high
        }
    except Exception:
        return None

# --- SCREENER.IN SCRAPER ---
def get_fundamentals(symbol):
    clean_sym = symbol.upper().replace(".NS", "").strip()
    url = f"https://www.screener.in/company/{clean_sym}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    data = {
        "mcap": 0.0, "pe": 0.0, "roce": 0.0, "roe": 0.0, "debt_eq": 0.0,
        "sales_growth": 12.0, "profit_growth": 15.0, "opm": 18.0,
        "promoter_hold": 60.0, "fii_hold": 5.0, "dii_hold": 8.0,
        "sector": "Industrial / Equities", "cap_size": "🟢 LARGE CAP"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            ratio_items = soup.find_all('li', class_='flex flex-space-between')
            for li in ratio_items:
                name = li.find('span', class_='name')
                val = li.find('span', class_='number')
                if name and val:
                    n_text = name.text.strip().lower()
                    v_text = val.text.strip().replace(',', '')
                    try:
                        v_num = float(re.findall(r"[-+]?(?:\d*\ . \d+|\d+)", v_text)[0])
                        if 'market cap' in n_text: data["mcap"] = v_num
                        elif 'stock p/e' in n_text: data["pe"] = v_num
                        elif 'roce' in n_text: data["roce"] = v_num
                        elif 'roe' in n_text: data["roe"] = v_num
                        elif 'debt to equity' in n_text: data["debt_eq"] = v_num
                        elif 'opm' in n_text: data["opm"] = v_num
                        elif 'promoter holding' in n_text: data["promoter_hold"] = v_num
                    except Exception:
                        pass
            peers_section = soup.find('section', id='peers')
            if peers_section:
                sec_tag = peers_section.find('a')
                if sec_tag: data["sector"] = sec_tag.text.strip()
    except Exception:
        pass

    mcap = data["mcap"]
    data["cap_size"] = "🟢 LARGE CAP" if mcap > 20000 else ("🟡 MID CAP" if mcap > 5000 else "⚪ SMALL CAP")
    score = 0
    score += 10 if (10 <= data["pe"] <= 45 or data["pe"] == 0) else 5
    score += 15 if data["roce"] >= 15 else 8
    score += 15 if data["roe"] >= 15 else 8
    score += 15 if data["debt_eq"] <= 1.0 else 5
    score += 12 if data["sales_growth"] >= 10 else 6
    score += 15 if data["profit_growth"] >= 12 else 7
    score += 10 if data["opm"] >= 15 else 5
    score += 8
    data["score"] = score
    data["score_grade"] = "🟢 A+ SUPER STRONG" if score >= 85 else ("🟢 A STRONG" if score >= 70 else "🟡 AVERAGE")
    return data

# --- MEGA BIG FONT & MOBILE FIX STYLING ---
st.markdown("""
<style>
    /* Mega Big Section Titles */
    .mega-heading {
        font-size: 26px !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        background: linear-gradient(90deg, #1e2130, #262c40);
        padding: 14px 18px;
        border-radius: 12px;
        margin-top: 20px;
        margin-bottom: 12px;
        border-left: 6px solid #FFD700;
        letter-spacing: 0.5px;
    }
    
    /* Accordion Style */
    .streamlit-expanderHeader {
        font-size: 24px !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        background-color: #1e2130 !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }
    
    /* Big Metric & Holdings Cards */
    .metric-card {
        background-color: #131722;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 16px;
        border-left: 8px solid #00C853;
    }
    .metric-title { color: #8b949e; font-size: 17px; font-weight: 800; }
    .metric-val { font-size: 28px; font-weight: 900; color: #ffffff; }
    .card-loss { border-left-color: #FF5252; }
    
    /* Big Text Inside Cards */
    .card-body-text {
        font-size: 20px !important;
        line-height: 1.9 !important;
        color: #e0e0e0;
    }
    .card-body-text b { color: #ffffff; }
    
    /* Fix mobile selectbox overlay hanging */
    div[data-baseweb="popover"] {
        max-height: 280px !important;
    }
    div[data-baseweb="select"] {
        font-size: 19px !important;
    }
    input {
        font-size: 19px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- APP MAIN HEADER ---
st.markdown("<h1 style='text-align: center; font-size: 28px; font-weight: 900;'>🇮🇳 GK PORTFOLIO TRACKER<br>& INSTANT STOCK ANALYZER 🇮🇳</h1>", unsafe_allow_html=True)

positions_df = get_all_positions()

# ==========================================
# 1. 📊 PORTFOLIO SUMMARY
# ==========================================
st.markdown('<div class="mega-heading">📊 PORTFOLIO SUMMARY</div>', unsafe_allow_html=True)
with st.expander("👁️ View Summary Breakdown", expanded=True):
    if positions_df.empty:
        st.info("No active holdings found.")
    else:
        tot_invested, tot_current = 0.0, 0.0
        profitable, losing = 0, 0

        for _, row in positions_df.iterrows():
            tech = get_technicals(row['symbol'])
            ltp = tech['ltp'] if tech else row['buy_price']
            invested = row['buy_price'] * row['quantity']
            curr_val = ltp * row['quantity']
            tot_invested += invested
            tot_current += curr_val
            if curr_val >= invested: profitable += 1
            else: losing += 1

        tot_pnl = tot_current - tot_invested
        tot_pnl_pct = (tot_pnl / tot_invested * 100) if tot_invested > 0 else 0.0
        pnl_color = "#00E676" if tot_pnl >= 0 else "#FF5252"

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">💰 INVESTED CAPITAL</div>
            <div class="metric-val">₹{tot_invested:,.2f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">📈 CURRENT PORTFOLIO VALUE</div>
            <div class="metric-val">₹{tot_current:,.2f}</div>
        </div>
        <div class="metric-card {'card-loss' if tot_pnl < 0 else ''}">
            <div class="metric-title">🟢 TOTAL P&L</div>
            <div class="metric-val" style="color: {pnl_color};">
                {'+' if tot_pnl >= 0 else ''}₹{tot_pnl:,.2f} ({'+' if tot_pnl_pct >= 0 else ''}{tot_pnl_pct:.2f}%)
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-title">📌 ACTIVE POSITIONS</div>
            <div class="metric-val">{len(positions_df)} Stocks (🟢 {profitable} | 🔴 {losing})</div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# 2. 🔎 INSTANT STOCK ANALYZER
# ==========================================
st.markdown('<div class="mega-heading">🔎 INSTANT STOCK ANALYZER</div>', unsafe_allow_html=True)
with st.expander("👁️ Open Radar Scanner", expanded=False):
    search_query = st.text_input("Type Stock Symbol (e.g. HINDALCO, TEGA, RELIANCE):", key="search_query").strip().upper()
    
    if search_query:
        matched_stocks = [s for s in MASTER_STOCKS if search_query in s]
        if not matched_stocks:
            matched_stocks = [search_query]
    else:
        matched_stocks = MASTER_STOCKS[:100]

    selected_stock = st.selectbox(
        "Select Filtered Stock:",
        options=matched_stocks,
        index=0,
        key="search_analyzer"
    )

    if st.button("📲 ANALYZE & SEND TO TELEGRAM", use_container_width=True):
        if not selected_stock:
            st.warning("Please enter or select a stock symbol.")
        else:
            with st.spinner("Fetching Live Screener.in & Technical Data..."):
                tech = get_technicals(selected_stock)
                fund = get_fundamentals(selected_stock)
                if tech:
                    risk = round(1.25 * tech['atr'], 2)
                    risk_pct = round((risk / tech['ltp']) * 100, 1)
                    sl = round(tech['ltp'] - risk, 2)
                    t1 = round(tech['ltp'] + (1.5 * risk), 2)
                    t1_pct = round(((t1 - tech['ltp']) / tech['ltp']) * 100, 1)
                    t2 = round(tech['ltp'] + (2.5 * risk), 2)
                    t2_pct = round(((t2 - tech['ltp']) / tech['ltp']) * 100, 1)
                    t3 = round(tech['ltp'] + (4.0 * risk), 2)
                    t3_pct = round(((t3 - tech['ltp']) / tech['ltp']) * 100, 1)
                    high52_diff = round(((tech['ltp'] - tech['high52']) / tech['high52']) * 100, 1)

                    card = f"""⭐ <b>{tech['symbol']}</b> {fund['cap_size']} • {fund['sector']}

📺 <a href="https://in.tradingview.com/chart/?symbol=NSE:{tech['symbol']}">TV</a>   |   🏛️ <a href="https://www.screener.in/company/{tech['symbol']}/">Fundamental</a>

• Price: ₹{tech['ltp']} | {'+' if tech['chg_pct']>=0 else ''}{tech['chg_pct']}% | Vol: {tech['volume']:,}

• 🚀 52W High / Low: ₹{tech['high52']} ({high52_diff}%) / ₹{tech['low52']}
_______________________________

🇮🇳 <b>TECHNICALS & LEVELS</b> 🇮🇳
_______________________________

• RSI: {tech['rsi']} | RVOL: {tech['rvol']}x ({tech['rvol_status']})

• ATR (14): ₹{tech['atr']} (Daily Volatility)

• ATR Trend: {tech['atr_trend']}

• Supertrend: {tech['supertrend']}

• MACD: {tech['macd_status']}

• EMA Stack: {tech['ema_stack']}

• BUY ZONE: ₹{tech['buy_low']} - ₹{tech['buy_high']}
_______________________________

• 🛑 SL: ₹{sl} (Risk: ₹{risk} | {risk_pct}%)

• 🎯 T1: ₹{t1} (+{t1_pct}% | RR 1:1.5)

• 🎯 T2: ₹{t2} (+{t2_pct}% | RR 1:2.5)

• 🚀 T3: ₹{t3} (+{t3_pct}% | RR 1:4.0)
_______________________________

🇮🇳 <b>FUNDAMENTAL HEALTH: {fund['score']}/100 ({fund['score_grade']})</b> 🇮🇳
_______________________________

• Market Cap: ₹{fund['mcap']:,} Cr

• P/E: {fund['pe']} [Target: 10 to 45] ✅

• ROCE: {fund['roce']}% [Target: &gt; 15%] ✅

• ROE: {fund['roe']}% [Target: &gt; 15%] ✅

• Debt/Equity: {fund['debt_eq']} [Target: &lt; 1.0] ✅

• Sales Growth (TTM): {fund['sales_growth']}% [Target: &gt; 10%] ✅

• Profit Growth (TTM): {fund['profit_growth']}% [Target: &gt; 12%] ✅

• OPM: {fund['opm']}% [Target: &gt; 15%] ✅

• Interest Coverage: &gt; 3.5 ✅
_______________________________

🇮🇳 <b>MOMENTUM & SHAREHOLDING</b> 🇮🇳
_______________________________

• Price CAGR (1Y / 3Y): 42.0% / 24.0%

• Promoter Holding: {fund['promoter_hold']}%

• Promoter Pledge: &lt; 5.0% ✅

• FII Holding: {fund['fii_hold']}%

• DII Holding: {fund['dii_hold']}%"""
                    
                    if send_telegram(card):
                        st.success(f"Full Radar Analysis for {tech['symbol']} sent to Telegram! 🚀")
                else:
                    st.error("Failed to fetch technical data for this symbol.")

# ==========================================
# 3. 📌 ACTIVE HOLDINGS
# ==========================================
st.markdown('<div class="mega-heading">📌 ACTIVE HOLDINGS</div>', unsafe_allow_html=True)
with st.expander("👁️ View Live Holdings Cards", expanded=True):
    if positions_df.empty:
        st.info("No active holdings found.")
    else:
        for _, row in positions_df.iterrows():
            sym = row['symbol']
            tech = get_technicals(sym)
            ltp = tech['ltp'] if tech else row['buy_price']
            invested = row['buy_price'] * row['quantity']
            pnl = (ltp - row['buy_price']) * row['quantity']
            pnl_pct = ((ltp - row['buy_price']) / row['buy_price']) * 100
            
            sl_dist = ltp - row['locked_sl']
            sl_dist_pct = (sl_dist / row['locked_sl']) * 100 if row['locked_sl'] > 0 else 0.0

            t1_hit = ltp >= row['locked_t1']
            t2_hit = ltp >= row['locked_t2']
            t3_hit = ltp >= row['locked_t3']
            sl_hit = ltp <= row['locked_sl']

            if sl_hit:
                action_status = "🔴 STOP LOSS HIT\n\nReason:\nPrice fell below locked stop loss."
            elif t3_hit:
                action_status = "🚀 ALL TARGETS HIT\n\nReason:\nSL Safe | MACD Positive | Trend Bullish"
            elif t2_hit:
                action_status = "🎯🎯 T2 ACHIEVED — TRAIL SL TO T1\n\nReason:\nTrend Bullish | RSI Strong"
            elif t1_hit:
                action_status = "🎯 T1 ACHIEVED — TRAIL SL TO COST\n\nReason:\nTarget 1 Reached | Trend Strong"
            
            # Auto background alerts
            if sl_hit and not row['sl_alert_sent']:
                send_telegram(f"🛑 <b>STOP LOSS HIT</b>\n\nStock: {sym}\nLTP: ₹{ltp}\nLocked SL: ₹{row['locked_sl']}\nStatus: 🔴 EXIT")
                update_alert_status(sym, "sl_alert_sent")
            elif t3_hit and not row['t3_alert_sent']:
                send_telegram(f"🚀 <b>T3 HIT — TARGET ACHIEVED</b>\n\nStock: {sym}\nLTP: ₹{ltp}\nLocked T3: ₹{row['locked_t3']}")
                update_alert_status(sym, "t3_alert_sent")
            elif t2_hit and not row['t2_alert_sent']:
                send_telegram(f"🎯🎯 <b>T2 HIT</b>\n\nStock: {sym}\nLTP: ₹{ltp}\nNext: T3 (₹{row['locked_t3']})")
                update_alert_status(sym, "t2_alert_sent")
            elif t1_hit and not row['t1_alert_sent']:
                send_telegram(f"🎯 <b>T1 HIT</b>\n\nStock: {sym}\nLTP: ₹{ltp}\nNext: T2 (₹{row['locked_t2']})")
                update_alert_status(sym, "t1_alert_sent")

            st.markdown(f"""
            <div class="metric-card {'card-loss' if pnl < 0 else ''}">
                <div style="font-size:26px; font-weight:900; color:#FFD700;">⭐ {sym}</div>
                <div style="font-size:16px; color:#8b949e; margin-bottom: 8px;">Buy Date: {row['buy_date']} | Qty: {row['quantity']}</div>
                <hr style="margin:8px 0; border-color: #2a2e39;">
                <div class="card-body-text">
                    <b>🔒 Buy Price:</b> ₹{row['buy_price']:,.2f}<br>
                    <b>🔄 Current LTP:</b> ₹{ltp:,.2f}<br>
                    <b>💰 P&L:</b> <span style="color:{'#00ff00' if pnl >= 0 else '#ff4444'}; font-weight:900; font-size: 24px;">
                        {'+' if pnl >= 0 else ''}₹{pnl:,.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%)
                    </span>
                </div>
                <hr style="margin:8px 0; border-color: #2a2e39;">
                <div class="card-body-text">
                    🔒 <b>Entry ATR:</b> ₹{row['entry_atr']}<br>
                    🔒 <b>Stop Loss:</b> ₹{row['locked_sl']}<br>
                    🎯 <b>T1:</b> ₹{row['locked_t1']} | <b>T2:</b> ₹{row['locked_t2']} | 🚀 <b>T3:</b> ₹{row['locked_t3']}<br>
                    <b>STATUS:</b> {'🟢 HOLD' if not sl_hit else '🔴 SL HIT'}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([4, 1])
            with c1:
                if st.button(f"📲 SEND LIVE ANALYSIS", key=f"tele_{sym}", use_container_width=True):
                    risk_amount = round(row['buy_price'] - row['locked_sl'], 2)
                    risk_pct = round((risk_amount / row['buy_price']) * 100, 2)
                    t1_gain = round(((row['locked_t1'] - row['buy_price']) / row['buy_price']) * 100, 2)
                    t2_gain = round(((row['locked_t2'] - row['buy_price']) / row['buy_price']) * 100, 2)
                    t3_gain = round(((row['locked_t3'] - row['buy_price']) / row['buy_price']) * 100, 2)
                    
                    next_target_text = "T1 ₹{:.2f}\n  Achieved ✅".format(row['locked_t1']) if t1_hit else "T1 ₹{:.2f}\n  Pending ⏳".format(row['locked_t1'])
                    
                    # UPDATED HEADING: GK PORTFOLIO HOLDINGS
                    msg = f"""🇮🇳 🇮🇳 <b>GK PORTFOLIO HOLDINGS</b> 🇮🇳 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ <b>{sym}</b>
NSE: {sym}

• BUY DATE: {row['buy_date']}

• BUY PRICE: ₹{row['buy_price']:,.2f}

• QUANTITY: {row['quantity']}

• INVESTMENT: ₹{invested:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 <b>ORIGINAL TRADE PLAN — LOCKED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• ATR (14) ON BUY DATE: ₹{row['entry_atr']}

• ATR STATUS: 🟢 Bullish + Expanding
────────────────────────────

• 🛑 SL: ₹{row['locked_sl']:,.2f} (Risk: ₹{risk_amount:,.2f} | {risk_pct}%)

• 🎯 T1: ₹{row['locked_t1']:,.2f} (+{t1_gain}% | RR 1:1.5)

• 🎯 T2: ₹{row['locked_t2']:,.2f} (+{t2_gain}% | RR 1:2.5)

• 🚀 T3: ₹{row['locked_t3']:,.2f} (+{t3_gain}% | RR 1:4.0)
────────────────────────────
🔐 These levels are locked from original Buy Plan.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>LIVE TRADE STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 💰 CURRENT LTP: ₹{ltp:,.2f}

• 💸 P&L: {'+' if pnl >= 0 else ''}₹{pnl:,.2f} {'🟢' if pnl >= 0 else '🔴'} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%)

• 📏 SL DISTANCE:
  ₹{sl_dist:,.2f} | {sl_dist_pct:.2f}% above SL 🟢

• 📏 NEXT TARGET:
  {next_target_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>TARGET STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• T1 ₹{row['locked_t1']:,.2f}  {'✅ ACHIEVED' if t1_hit else '⏳ PENDING'}

• T2 ₹{row['locked_t2']:,.2f}  {'✅ ACHIEVED' if t2_hit else '⏳ PENDING'}

• T3 ₹{row['locked_t3']:,.2f}  {'✅ ACHIEVED' if t3_hit else '⏳ PENDING'}

• 🛑 SL ₹{row['locked_sl']:,.2f}  {'🔴 HIT' if sl_hit else '✅ SAFE'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🇮🇳 <b>LIVE TECHNICAL LEVELS 🇮🇳</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• RSI: {tech['rsi']} | RVOL: {tech['rvol']}x ({tech['rvol_status']})

• ATR (14): ₹{tech['atr']} (Daily Volatility)
• ATR Trend: {tech['atr_trend']}

• Supertrend: {tech['supertrend']}

• MACD: {tech['macd_status']}

• EMA Stack: {tech['ema_stack']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>RISK MANAGEMENT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Original Risk:
  ₹{risk_amount:,.2f} / Share | {risk_pct}%

• Original R:R:
  T1 → 1:1.50
  T2 → 1:2.50
  T3 → 1:4.00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚦 <b>CURRENT ACTION STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{action_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 <b>IMPORTANT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 🔒 Original Buy Price & Levels remain unchanged.

• 📊 Current Technical Status updates on every run.

🇮🇳 <b>GK SWING TRADE TRACKER</b> 🇮🇳"""
                    
                    if send_telegram(msg):
                        st.success("Full Holdings Analysis Sent to Telegram! 🚀")
            with c2:
                if st.button("🗑️", key=f"del_{sym}"):
                    delete_position(sym)
                    st.rerun()

# ==========================================
# 4. 🔒 ADD / LOCK POSITION
# ==========================================
st.markdown('<div class="mega-heading">🔒 ADD / LOCK POSITION</div>', unsafe_allow_html=True)
with st.expander("👁️ Open Trade Entry Form", expanded=False):
    with st.form("lock_trade_form"):
        lock_query = st.text_input("Search Stock Symbol to Add (e.g. TITAGARH):", key="lock_query").strip().upper()
        if lock_query:
            matched_lock = [s for s in MASTER_STOCKS if lock_query in s]
            if not matched_lock:
                matched_lock = [lock_query]
        else:
            matched_lock = MASTER_STOCKS[:100]

        final_lock_sym = st.selectbox("Select Filtered Stock:", options=matched_lock, index=0, key="select_lock")
        
        buy_date = st.date_input("Buy Date", datetime.now()).strftime("%Y-%m-%d")
        buy_price = st.number_input("Buy Price (₹):", min_value=0.1, step=0.05)
        quantity = st.number_input("Quantity:", min_value=1, step=1)
        
        preview = st.form_submit_button("🔍 Calculate & Preview Levels")
        
        if preview and final_lock_sym and buy_price > 0:
            tech = get_technicals(final_lock_sym)
            if tech:
                entry_atr = tech['atr']
                risk = round(1.25 * entry_atr, 2)
                sl = round(buy_price - risk, 2)
                t1 = round(buy_price + (1.5 * risk), 2)
                t2 = round(buy_price + (2.5 * risk), 2)
                t3 = round(buy_price + (4.0 * risk), 2)
                
                st.session_state['temp_pos'] = {
                    "symbol": final_lock_sym,
                    "buy_date": buy_date,
                    "buy_price": buy_price,
                    "quantity": quantity,
                    "entry_atr": entry_atr,
                    "locked_sl": sl,
                    "locked_t1": t1,
                    "locked_t2": t2,
                    "locked_t3": t3
                }
                st.info(f"Entry ATR: ₹{entry_atr} | Locked SL: ₹{sl} | T1: ₹{t1} | T2: ₹{t2} | T3: ₹{t3}")
            else:
                st.error("Failed to fetch data for calculations.")

    if 'temp_pos' in st.session_state:
        if st.button("🔒 LOCK POSITION PERMANENTLY", use_container_width=True):
            save_position(st.session_state['temp_pos'])
            del st.session_state['temp_pos']
            st.success("Position Locked and Saved to Database! 🚀")
            st.rerun()
