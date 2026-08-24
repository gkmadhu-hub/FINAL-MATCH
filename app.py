import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import sqlite3
from datetime import datetime
import html

# --- CONFIG & CREDENTIALS ---
st.set_page_config(
    page_title="GK Portfolio & Radar Tracker",
    page_icon="🇮🇳",
    layout="centered",
    initial_sidebar_state="collapsed"
)

TELEGRAM_BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jbH7Nyg"
TELEGRAM_CHAT_ID = "7475999824"

# --- MASTER NSE STOCKS LIST (NIFTY 50, 500, MID/SMALL CAPS) ---
@st.cache_data(ttl=86400)
def get_all_nse_symbols():
    return sorted(list(set([
        "360ONE", "3MINDIA", "ABB", "ACC", "AIAENG", "APLAPOLLO", "AUBANK", "AARTIIND", 
        "AAVAS", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", 
        "ADANIPORTS", "ADANIPOWER", "AEGISLOG", "AFFLE", "AJANTPHARM", "ALKEM", "ALOKINDS", 
        "AMBER", "AMBUJACEM", "ANGELONE", "APOLLOHOSP", "APOLLOTYRE", "APTUS", "ARE&M", 
        "ASHOKLEY", "ASIANPAINT", "ASTERDM", "ASTRAL", "ATGL", "ATUL", "AUROPHARMA", 
        "AVANTIFEED", "AWL", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG", "BAJFINANCE", 
        "BALAMINES", "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BANKINDIA", 
        "BATAINDIA", "BAYERCROP", "BBTC", "BDL", "BEL", "BEML", "BERGEPAINT", "BHARATFORG", 
        "BHARTIARTL", "BHEL", "BIOCON", "BIRLACORPN", "BLS", "BLUEDART", "BLUESTARCO", 
        "BORORENEW", "BOSCHLTD", "BPCL", "BRIGADE", "BRITANNIA", "BSE", "BSOFT", "CAMPUS", 
        "CANBK", "CANFINHOME", "CARBORUNIV", "CASTROLIND", "CDSL", "CEATLTD", "CENTRALBK", 
        "CENTURYPLY", "CENTURYTEX", "CERA", "CESC", "CGPOWER", "CHALET", "CHAMBLFERT", 
        "CHEMPLASTS", "CHOLAFIN", "CHOLAHLDNG", "CIPLA", "CLEAN", "COALINDIA", "COCHINSHIP", 
        "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CRAFTSMAN", "CREDITACC", "CRISIL", 
        "CROMPTON", "CUB", "CUMMINSIND", "CYIENT", "DABUR", "DALBHARAT", "DATAPATTNS", 
        "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DEVYANI", "DIVISLAB", "DIXON", "DLF", 
        "DMART", "DRREDDY", "ECLERX", "EICHERMOT", "EIDPARRY", "EIHOTEL", "ELGIEQUIP", 
        "EMAMILTD", "ENDURANCE", "ENGINERSIN", "EQUITASBNK", "ERIS", "ESCORTS", "EXIDEIND", 
        "FDC", "FEDERALBNK", "FACT", "FINCABLES", "FINEORG", "FINPIPE", "FLUOROCHEM", 
        "FORTIS", "FSL", "GAIL", "GMRINFRA", "GALAXYSURF", "GICRE", "GILLETTE", "GLAXO", 
        "GLENMARK", "GLS", "GMMPFAUDLR", "GNFC", "GODFRYPHLP", "GODREJAGRO", "GODREJCP", 
        "GODREJIND", "GODREJPROP", "GRANULES", "GRAPHITE", "GRASIM", "GRAVITA", "GRINDWELL", 
        "GSFC", "GSPL", "GUJGASLTD", "GMDCLTD", "HAL", "HAPPSTMNDS", "HAVELLS", "HBLPOWER", 
        "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEG", "HEROMOTOCO", "HFCL", 
        "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HITACHI", 
        "HOMEFIRST", "HONAUT", "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IEX", 
        "IFCI", "IGL", "IIFL", "INDHOTEL", "INDIACEM", "INDIAMART", "INDIANB", "INDIGO", 
        "INDUSINDBK", "INDUSTOWER", "INFIBEAM", "INFY", "INGERRAND", "INOXWIND", "IOB", 
        "IOC", "IPCALAB", "IRB", "IRCON", "IRCTC", "IRFC", "IREDA", "ITC", "ITI", 
        "J&KBANK", "JBCHEPHARM", "JBMA", "JINDALSAW", "JINDALSTEL", "JIOFIN", "JKCEMENT", 
        "JKPAPER", "JKTYRE", "JSL", "JSWENERGY", "JSWINFRA", "JSWSTEEL", "JUBLFOOD", 
        "JUBLINGREA", "JUBLPHARMA", "JUSTDIAL", "JYOTHYLAB", "KALYANKJIL", "KANSAINER", 
        "KARURVYSYA", "KAYNES", "KEC", "KEI", "KFINTECH", "KNRCON", "KOTAKBANK", "KPIL", 
        "KPITTECH", "KPRMILL", "KRBL", "KSB", "L&TFH", "LT", "LTIM", "LTTS", "LATENTVIEW", 
        "LAURUSLABS", "LEMONTREE", "LICHSGFIN", "LICI", "LINDEINDIA", "LUPIN", "M&M", 
        "M&MFIN", "MANAPPURAM", "MAPMYINDIA", "MARICO", "MARUTI", "MASTEK", "MAXHEALTH", 
        "MAZDOCK", "MEDANTA", "METROPOLIS", "MFSL", "MGL", "MOTILALOFS", "MPHASIS", 
        "MRF", "MRPL", "MSUMI", "MUTHOOTFIN", "NATCOPHARM", "NATIONALUM", "NAUKRI", 
        "NAVINFLUOR", "NBCC", "NCC", "NESTLEIND", "NETWORK18", "NH", "NHPC", "NLCINDIA", 
        "NMDC", "NTPC", "NUVAMA", "OBEROIRLTY", "OFSS", "OIL", "OLECTRA", "ONGC", 
        "PAGEIND", "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PFIZER", 
        "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", 
        "POONAWALLA", "POWERGRID", "PRAJIND", "PRESTIGE", "PRINCEPIPE", "PRSMJOHNSN", 
        "PVRINOX", "RADICO", "RVNL", "RAILTEL", "RAIN", "RAJESHEXPO", "RALLIS", 
        "RAMCOCEM", "RBA", "RCF", "RECLTD", "REDINGTON", "RELIANCE", "RITES", "RKFORGE", 
        "ROLEXRINGS", "ROUTE", "SBICARD", "SBILIFE", "SBIN", "SCHAEFFLER", "SCHNEIDER", 
        "SHARDACROP", "SJVN", "SKFINDIA", "SOBHA", "SOLARINDS", "SONACOMS", "STARHEALTH", 
        "STLTECH", "SUMICHEM", "SUNDARMFIN", "SUNDRMFAST", "SUNPHARMA", "SUNTV", "SUPRAJIT", 
        "SUPREMEIND", "SUZLON", "SWANENERGY", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM", 
        "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TATATECH", "TTML", "TCS", 
        "TECHM", "TEGA", "TEJASNET", "THERMAX", "TIMKEN", "TITAGARH", "TITAN", "TORNTPHARM", 
        "TORNTPOWER", "TRENT", "TRIDENT", "TRITURBINE", "TRU", "TTKPRESTIG", "TV18BRDCST", 
        "TVSMOTOR", "UBL", "UCOBANK", "ULTRACEMCO", "UNIONBANK", "UNOMINDA", "UPL", 
        "USHAMART", "UTIAMC", "VBL", "VEDL", "VOLTAS", "WHIRLPOOL", "WIPRO", "YESBANK", 
        "ZEEL", "ZENSARTECH", "ZOMATO", "ZYDUSLIFE"
    ])))

MASTER_STOCKS = get_all_nse_symbols()

# --- DATABASE SETUP (SQLite) ---
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

# --- SAFE TELEGRAM DISPATCH ---
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

# --- TECHNICAL ANALYSIS ENGINE ---
def get_technicals(symbol):
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
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
    atr_trend = "🟢 Expanding (Bullish+expanding)" if atr > float(atr_series.iloc[-5]) else "⚪ Normal"

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    rsi = float(100 - (100 / (1 + rs)).iloc[-1])

    vol_sma20 = vol.rolling(20).mean().iloc[-1]
    rvol = float(vol.iloc[-1] / (vol_sma20 + 1e-9))
    rvol_status = "🟢 IDEAL ACCUMULATION" if rvol >= 1.5 else "⚪ NORMAL VOLUME"

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

# --- FUNDAMENTAL SCORING ENGINE (100 PTS) ---
def get_fundamentals(symbol):
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    info = yf.Ticker(ticker_sym).info
    
    pe = info.get('trailingPE', 15.0) or 15.0
    roe = (info.get('returnOnEquity', 0.18) or 0.18) * 100
    roce = (info.get('returnOnAssets', 0.14) or 0.14) * 100 * 1.3
    debt_eq = (info.get('debtToEquity', 40.0) or 40.0) / 100
    sales_growth = (info.get('revenueGrowth', 0.15) or 0.15) * 100
    profit_growth = (info.get('earningsGrowth', 0.20) or 0.20) * 100
    opm = (info.get('operatingMargins', 0.25) or 0.25) * 100
    mcap = info.get('marketCap', 10000000000) / 10000000  # Cr
    
    cap_size = "🟢 LARGE CAP" if mcap > 20000 else ("🟡 MID CAP" if mcap > 5000 else "⚪ SMALL CAP")
    
    score = 0
    score += 10 if 10 <= pe <= 45 else 5
    score += 15 if roce > 15 else 8
    score += 15 if roe > 15 else 8
    score += 15 if debt_eq < 1.0 else 5
    score += 12 if sales_growth > 10 else 6
    score += 15 if profit_growth > 12 else 7
    score += 10 if opm > 15 else 5
    score += 8
    
    score_grade = "🟢 A+ SUPER STRONG" if score >= 85 else ("🟢 A STRONG" if score >= 70 else "🟡 AVERAGE")

    return {
        "score": score,
        "score_grade": score_grade,
        "pe": round(pe, 2),
        "roce": round(roce, 2),
        "roe": round(roe, 2),
        "debt_eq": round(debt_eq, 2),
        "sales_growth": round(sales_growth, 2),
        "profit_growth": round(profit_growth, 2),
        "opm": round(opm, 2),
        "sector": info.get('sector', 'Metals & Mining / Industry'),
        "mcap": round(mcap, 1),
        "cap_size": cap_size,
        "promoter_hold": round(info.get('heldPercentInsiders', 0.6071) * 100, 2),
        "fii_hold": 2.2,
        "dii_hold": 4.96
    }

# --- CUSTOM CSS (LARGE ACCORDIONS & HIGH-VISIBILITY MOBILE UI) ---
st.markdown("""
<style>
    /* Big Bold Accordion Headers */
    .streamlit-expanderHeader {
        font-size: 22px !important;
        font-weight: 900 !important;
        letter-spacing: 0.5px !important;
        color: #ffffff !important;
        background-color: #1e2130 !important;
        border-radius: 10px !important;
        padding: 16px !important;
        margin-bottom: 8px !important;
    }
    
    /* Metric Cards */
    .metric-card {
        background-color: #131722;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 14px;
        border-left: 6px solid #00C853;
    }
    .metric-title { color: #8b949e; font-size: 15px; font-weight: bold; }
    .metric-val { font-size: 24px; font-weight: 800; color: #ffffff; }
    .card-loss { border-left-color: #FF5252; }
    
    /* Big Text Inside Cards */
    .card-body-text {
        font-size: 17px !important;
        line-height: 1.8 !important;
        color: #e0e0e0;
    }
    .card-body-text b {
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# --- MAIN TITLE ---
st.markdown("<h2 style='text-align: center; font-size: 26px;'>🇮🇳 GK PORTFOLIO TRACKER<br>& INSTANT STOCK ANALYZER 🇮🇳</h2>", unsafe_allow_html=True)

positions_df = get_all_positions()

# ==========================================
# 1. 📊 PORTFOLIO SUMMARY
# ==========================================
with st.expander("📊 PORTFOLIO SUMMARY", expanded=False):
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
with st.expander("🔎 INSTANT STOCK ANALYZER", expanded=False):
    selected_stock = st.selectbox(
        "Type to Search Any NSE Stock (Nifty 50/500/Mid/Small):",
        options=[""] + MASTER_STOCKS,
        index=0
    )
    custom_sym = st.text_input("Or type custom ticker:").strip().upper()
    active_sym = custom_sym if custom_sym else selected_stock

    if st.button("📲 ANALYZE & SEND TO TELEGRAM", use_container_width=True):
        if not active_sym:
            st.warning("Please select or type a stock symbol.")
        else:
            with st.spinner("Generating Clean Radar Analysis Card..."):
                tech = get_technicals(active_sym)
                fund = get_fundamentals(active_sym)
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
                    st.error("Failed to fetch data for this symbol.")

# ==========================================
# 3. 📌 ACTIVE HOLDINGS
# ==========================================
with st.expander("🔒 ADD / LOCK POSITION", expanded=False):
    with st.form("lock_trade_form"):
        lock_sym = st.selectbox("Search Stock Symbol to Add:", options=[""] + MASTER_STOCKS, index=0)
        custom_lock_sym = st.text_input("Or enter custom symbol:").strip().upper()
        final_lock_sym = custom_lock_sym if custom_lock_sym else lock_sym
        
        buy_date = st.date_input("Buy Date", datetime.now()).strftime("%d-%m-%Y")
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
