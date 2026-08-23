import streamlit as st
import pandas as pd
import yfinance as yf
import sqlite3
import requests

st.set_page_config(page_title="GK Portfolio Tracker", layout="wide")

# Mobile-Optimized Large Font CSS (No zoom required)
st.markdown("""
<style>
/* Metric Cards */
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    word-break: break-word !important;
    white-space: normal !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}

/* Stock Card Box */
.stock-card {
    background-color: #1a1e29;
    border: 1px solid #3b4252;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 18px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}

/* Header Inside Card */
.stock-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #434c5e;
    padding-bottom: 10px;
    margin-bottom: 12px;
}
.stock-title {
    font-size: 1.4rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.5px;
}
.stock-status-badge {
    font-size: 1.05rem;
    font-weight: 700;
}

/* Data Rows */
.val-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 7px 0;
    font-size: 1.12rem;
}
.val-label {
    color: #d8dee9;
    font-weight: 500;
}
.val-data {
    font-weight: 700;
    color: #eceff4;
}
.green-txt { 
    color: #00e676 !important; 
    font-weight: 800 !important; 
    font-size: 1.18rem;
}
.red-txt { 
    color: #ff5252 !important; 
    font-weight: 800 !important; 
    font-size: 1.18rem;
}
</style>
""", unsafe_allow_html=True)

TELEGRAM_BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
TELEGRAM_CHAT_ID = "7475999824"

NSE_POPULAR_STOCKS = sorted(list(set([
    "TEGA", "GRAVITA", "HINDALCO", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN",
    "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HINDUNILVR", "AXISBANK", "BAJFINANCE",
    "MARUTI", "ASIANPAINT", "TITAN", "TATAMOTORS", "SUNPHARMA", "TATASTEEL",
    "NTPC", "POWERGRID", "M&M", "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV",
    "JSWSTEEL", "ONGC", "HCLTECH", "TECHM", "WIPRO", "NESTLEIND", "ULTRACEMCO",
    "HEROMOTOCO", "EICHERMOT", "DIVISLAB", "GRASIM", "CIPLA", "APOLLOHOSP",
    "DRREDDY", "BRITANNIA", "TATACONSUM", "BPCL", "INDUSINDBK",
    "BAJAJ-AUTO", "LTIM", "SBILIFE", "HDFCLIFE", "ZOMATO", "JIOFIN", "TRENT",
    "BEL", "HAL", "VEDL", "VBL", "BSE", "CDSL", "IREDA", "SUZLON", "IRFC", "RVNL",
    "MAZDOCK", "COCHINSHIP", "KPITTECH", "PERSISTENT", "COFORGE", "POLYCAB", "KEI",
    "DIXON", "KAYNES", "KPRMILL", "GOKEX", "ANGELONE", "MOTILALOFS", "PFC", "RECLTD"
])))

# --- Database Setup ---
conn = sqlite3.connect("portfolio_tracker.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    buy_date TEXT,
    buy_price REAL,
    quantity INTEGER,
    locked_atr REAL,
    atr_status TEXT,
    sl REAL,
    t1 REAL,
    t2 REAL,
    t3 REAL
)
""")
conn.commit()

# --- Technical Helpers ---
def get_atr(df, period=14):
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_supertrend(df, period=10, multiplier=3.0):
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    hl2 = (high + low) / 2
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    
    in_uptrend = True
    for i in range(1, len(df)):
        if close.iloc[i] > upperband.iloc[i-1]:
            in_uptrend = True
        elif close.iloc[i] < lowerband.iloc[i-1]:
            in_uptrend = False
            
    return "🟢 Bullish" if in_uptrend else "🔴 Bearish"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        st.error(f"Telegram error: {e}")

def get_snapshot(symbol, buy_date, buy_price):
    clean_sym = symbol.strip().upper()
    ticker = clean_sym if clean_sym.endswith((".NS", ".BO")) else f"{clean_sym}.NS"
    end_dt = pd.to_datetime(buy_date) + pd.Timedelta(days=5)
    
    df = yf.download(ticker, end=end_dt.strftime('%Y-%m-%d'), progress=False)
    if df.empty or len(df) < 15:
        return None
        
    df['ATR'] = get_atr(df)
    close_s = df['Close'].squeeze()
    df['EMA20'] = close_s.ewm(span=20, adjust=False).mean()
    
    atr_s = df['ATR'].dropna()
    if len(atr_s) == 0:
        return None
        
    locked_atr = round(float(atr_s.iloc[-1]), 2)
    locked_close = float(close_s.iloc[-1])
    locked_ema20 = float(df['EMA20'].iloc[-1])
    
    prev_atr = float(atr_s.iloc[-4]) if len(atr_s) >= 4 else locked_atr
    atr_chg = ((locked_atr - prev_atr) / prev_atr) * 100 if prev_atr > 0 else 0
    trend = "Expanding" if atr_chg > 2.0 else ("Contracting" if atr_chg < -2.0 else "Normal")
    
    status = "Bullish" if locked_close > locked_ema20 else "Bearish"
    atr_status = f"{'🟢' if status=='Bullish' else '🔴'} {status} + {trend}"
    
    sl = round(buy_price - (1.25 * locked_atr), 2)
    t1 = round(buy_price + (1.875 * locked_atr), 2)
    t2 = round(buy_price + (3.125 * locked_atr), 2)
    t3 = round(buy_price + (5.0 * locked_atr), 2)
    return locked_atr, atr_status, sl, t1, t2, t3

def send_card(row, ltp, pnl, pnl_pct, rsi, rvol, ema_stk, macd_st, supertrend_st, latr, l_atr_trend, trnd_clean, act_t, sl_dist, t1_dist, t1_st, t2_st, t3_st, sl_st):
    risk = round(row['buy_price'] - row['sl'], 2)
    risk_pct = round((risk / row['buy_price']) * 100, 2)
    t1_pct = round(((row['t1'] - row['buy_price']) / row['buy_price']) * 100, 2)
    t2_pct = round(((row['t2'] - row['buy_price']) / row['buy_price']) * 100, 2)
    t3_pct = round(((row['t3'] - row['buy_price']) / row['buy_price']) * 100, 2)
    
    vol_desc = "🔥 HIGH CLIMAX VOLUME" if rvol >= 2.0 else ("🟢 Good Volume" if rvol >= 1.0 else "🟡 Normal Volume")
    sl_state_reason = "SL Safe" if "SAFE" in sl_st else "SL Breached"
    macd_reason = "MACD Positive" if "POSITIVE" in macd_st or "Bullish" in macd_st else "MACD Negative"
    trend_reason = f"Trend {trnd_clean}"
    
    reason_line = f"{sl_state_reason} | {macd_reason} | {trend_reason}"

    msg = f"""🇮🇳 🇮🇳 *GK PORTFOLIO TRADE TRACKER* 🇮🇳 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ *{row['symbol']}*
NSE: {row['symbol']}

• BUY DATE: {row['buy_date']}

• BUY PRICE: ₹{row['buy_price']:,.2f}

• QUANTITY: {row['quantity']}

• INVESTMENT: ₹{(row['buy_price'] * row['quantity']):,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 *ORIGINAL TRADE PLAN — LOCKED*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• ATR (14) ON BUY DATE: ₹{row['locked_atr']:.2f}

• ATR STATUS: {row['atr_status']}
────────────────────────────

• 🛑 SL: ₹{row['sl']:,.2f} (Risk: ₹{risk:,.2f} | {risk_pct:.2f}%)

• 🎯 T1: ₹{row['t1']:,.2f} (+{t1_pct:.2f}% | RR 1:1.5)

• 🎯 T2: ₹{row['t2']:,.2f} (+{t2_pct:.2f}% | RR 1:2.5)

• 🚀 T3: ₹{row['t3']:,.2f} (+{t3_pct:.2f}% | RR 1:4.0)
────────────────────────────
_🔐 These levels are locked from original Buy Plan._

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *LIVE TRADE STATUS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 💰 CURRENT LTP: ₹{ltp:,.2f}

• 💸 P&L: ₹{pnl:,.2f} {'🟢' if pnl>=0 else '🔴'} ({pnl_pct:+.2f}%)

• 📏 SL DISTANCE:
  {sl_dist}

• 📏 NEXT TARGET:
  T1 ₹{row['t1']:,.2f}
  {t1_dist}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *TARGET STATUS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• T1 ₹{row['t1']:,.2f}  {t1_st}

• T2 ₹{row['t2']:,.2f}  {t2_st}

• T3 ₹{row['t3']:,.2f}  {t3_st}

• 🛑 SL ₹{row['sl']:,.2f}  {sl_st}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🇮🇳 *LIVE TECHNICAL LEVELS* 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• RSI: {rsi:.2f} | RVOL: {rvol:.2f}x ({vol_desc})

• ATR (14): ₹{latr:.2f} (Daily Volatility)
• ATR Trend: {l_atr_trend}

• Supertrend: {supertrend_st}

• MACD: {macd_st}

• EMA Stack: {ema_stk}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *RISK MANAGEMENT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Original Risk:
  ₹{risk:,.2f} / Share | {risk_pct:.2f}%

• Original R:R:
  T1 → 1:1.50
  T2 → 1:2.50
  T3 → 1:4.00

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚦 *CURRENT ACTION STATUS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*{act_t}*

*Reason:*
{reason_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *IMPORTANT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• 🔒 Original Buy Price & Levels remain unchanged.

• 📊 Current Technical Status updates on every run.

🇮🇳 *GK SWING TRADE TRACKER* 🇮🇳"""
    send_telegram(msg)

# --- Main Dashboard ---
st.title("🇮🇳 GK PORTFOLIO TRADE TRACKER")
st.caption("Automated ATR-Locked Swing Trade Dashboard")

with st.sidebar:
    st.header("➕ Add New Position")
    input_method = st.radio("Stock Input Mode", ["Select from Popular List", "Custom Type"], horizontal=True)
    if input_method == "Select from Popular List":
        sym_in = st.selectbox("Stock Symbol (Type to Search)", options=[""] + NSE_POPULAR_STOCKS)
    else:
        sym_in = st.text_input("Custom Stock Symbol (e.g. TATAELXSI)").strip().upper()
        
    date_in = st.date_input("Buy Date")
    price_in = st.number_input("Buy Price (₹)", min_value=0.0, step=0.5)
    qty_in = st.number_input("Quantity", min_value=1, step=1)
    
    if st.button("Lock Position & Save"):
        if sym_in and price_in > 0:
            with st.spinner("Locking levels..."):
                res = get_snapshot(sym_in, date_in.strftime('%Y-%m-%d'), price_in)
                if res:
                    latr, astat, sl, t1, t2, t3 = res
                    cursor.execute("INSERT INTO positions (symbol, buy_date, buy_price, quantity, locked_atr, atr_status, sl, t1, t2, t3) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (sym_in.strip().upper(), date_in.strftime('%Y-%m-%d'), price_in, qty_in, latr, astat, sl, t1, t2, t3))
                    conn.commit()
                    st.success(f"{sym_in.upper()} Saved & Levels Locked!")
                    st.rerun()
                else:
                    st.error("Historical data unavailable. Make sure the symbol is correct.")

df_pos = pd.read_sql("SELECT * FROM positions", conn)

if df_pos.empty:
    st.info("No active positions. Add a stock from the sidebar.")
else:
    cards, stock_render_data, tot_inv, tot_cur = [], [], 0.0, 0.0
    
    for _, row in df_pos.iterrows():
        tk = row['symbol'] if row['symbol'].endswith((".NS", ".BO")) else f"{row['symbol']}.NS"
        df_l = yf.download(tk, period="1y", progress=False)
        if df_l.empty:
            continue
            
        c_s, v_s = df_l['Close'].squeeze(), df_l['Volume'].squeeze()
        ltp = round(float(c_s.iloc[-1]), 2)
        inv = row['buy_price'] * row['quantity']
        c_val = ltp * row['quantity']
        pnl = c_val - inv
        pnl_pct = ((ltp - row['buy_price']) / row['buy_price']) * 100
        tot_inv += inv
        tot_cur += c_val
        
        rsi = round(float(get_rsi(c_s).iloc[-1]), 2)
        atr_series = get_atr(df_l).dropna()
        latr = round(float(atr_series.iloc[-1]), 2)
        rvol = round(float(v_s.iloc[-1] / v_s.rolling(20).mean().iloc[-1]), 2)
        
        prev_live_atr = float(atr_series.iloc[-4]) if len(atr_series) >= 4 else latr
        live_atr_chg = ((latr - prev_live_atr) / prev_live_atr) * 100 if prev_live_atr > 0 else 0
        live_trend = "Expanding" if live_atr_chg > 2.0 else ("Contracting" if live_atr_chg < -2.0 else "Normal")
        l_close = float(c_s.iloc[-1])
        l_e20 = float(c_s.ewm(span=20, adjust=False).mean().iloc[-1])
        l_stat = "Bullish" if l_close > l_e20 else "Bearish"
        
        l_atr_trend = f"{'🟢' if l_stat=='Bullish' else '🔴'} {live_trend} ({l_stat} + {live_trend})"
        supertrend_st = get_supertrend(df_l)
        
        e20 = float(c_s.ewm(span=20, adjust=False).mean().iloc[-1])
        e50 = float(c_s.ewm(span=50, adjust=False).mean().iloc[-1])
        e200 = float(c_s.ewm(span=200, adjust=False).mean().iloc[-1])
        
        rel1 = ">" if e20 > e50 else "<"
        rel2 = ">" if e50 > e200 else "<"
        
        if e20 > e50 > e200:
            ema_stk = f"20 {rel1} 50 {rel2} 200 EMA (🟢 BULLISH)"
            trnd_clean = "Bullish"
        elif e20 < e50 < e200:
            ema_stk = f"20 {rel1} 50 {rel2} 200 EMA (🔴 BEARISH)"
            trnd_clean = "Bearish"
        else:
            ema_stk = f"20 {rel1} 50 {rel2} 200 EMA (🟡 CONSOLIDATION)"
            trnd_clean = "Sideways"
        
        m_line = c_s.ewm(span=12, adjust=False).mean() - c_s.ewm(span=26, adjust=False).mean()
        s_line = m_line.ewm(span=9, adjust=False).mean()
        macd_st = "🟢 Bullish | MACD > Signal" if m_line.iloc[-1] > s_line.iloc[-1] else "🔴 Bearish | MACD < Signal"
        
        t1_st = "✅ ACHIEVED" if ltp >= row['t1'] else "⏳ NOT ACHIEVED"
        t2_st = "✅ ACHIEVED" if ltp >= row['t2'] else "⏳ NOT ACHIEVED"
        t3_st = "✅ ACHIEVED" if ltp >= row['t3'] else "⏳ NOT ACHIEVED"
        sl_st = "🚨 BREACHED" if ltp <= row['sl'] else "✅ SAFE"
        
        if ltp <= row['sl']:
            sl_dist = f"₹{abs(row['sl'] - ltp):,.2f} | {abs((row['sl'] - ltp)/row['sl'])*100:.2f}% BELOW SL 🚨"
            act_t, status = "🚨 EXIT / STOP LOSS HIT", "🚨 SL HIT"
        else:
            sl_dist = f"₹{abs(ltp - row['sl']):,.2f} | {((ltp - row['sl'])/row['sl'])*100:.2f}% above SL 🟢"
            if ltp >= row['t3']:
                act_t, status = "🚀 ALL TARGETS HIT", "🚀 T3 HIT"
            elif ltp >= row['t1']:
                act_t, status = "🎯 PARTIAL PROFIT / TRAIL SL", "🎯 T1 HIT"
            else:
                act_t, status = "🟢 HOLD", "🟢 HOLD"

        t1_dist = f"₹{abs(row['t1'] - ltp):,.2f} | {((row['t1'] - ltp)/ltp)*100:.2f}% away 🎯" if ltp < row['t1'] else "Achieved ✅"
        
        cards.append((row, ltp, pnl, pnl_pct, rsi, rvol, ema_stk, macd_st, supertrend_st, latr, l_atr_trend, trnd_clean, act_t, sl_dist, t1_dist, t1_st, t2_st, t3_st, sl_st))
        stock_render_data.append({
            "row": row, "ltp": ltp, "pnl": pnl, "pnl_pct": pnl_pct, "status": status, "inv": inv, "cur": c_val
        })

    # Summary Display: 2x2 Grid with large figures
    pnl_tot = tot_cur - tot_inv
    pnl_tot_pct = (pnl_tot / tot_inv * 100) if tot_inv > 0 else 0.0
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Total Holdings", f"{len(df_pos)} Stocks")
        st.metric("Total Invested", f"₹{tot_inv:,.2f}")
    with col_b:
        st.metric("Current Value", f"₹{tot_cur:,.2f}")
        st.metric("Total P&L", f"₹{pnl_tot:,.2f}", f"{pnl_tot_pct:+.2f}%")
        
    st.divider()
    
    # Action Header
    col1, col2 = st.columns([2, 2])
    col1.subheader("📊 Active Holdings")
    if col2.button("📲 Send All Alerts to Telegram", use_container_width=True):
        for c in cards:
            send_card(*c)
        st.success("All Alerts Sent to Telegram!")

    # --- LARGE FONT VERTICAL CARDS ---
    for item in stock_render_data:
        r = item["row"]
        ltp = item["ltp"]
        pnl = item["pnl"]
        pnl_pct = item["pnl_pct"]
        status = item["status"]
        pnl_class = "green-txt" if pnl >= 0 else "red-txt"
        
        with st.container():
            st.markdown(f"""
            <div class="stock-card">
                <div class="stock-header">
                    <span class="stock-title">⭐ {r['symbol']}</span>
                    <span class="stock-status-badge">{status}</span>
                </div>
                <div class="val-row"><span class="val-label">Buy Price:</span><span class="val-data">₹{r['buy_price']:,.2f} (Qty: {r['quantity']})</span></div>
                <div class="val-row"><span class="val-label">Current LTP:</span><span class="val-data">₹{ltp:,.2f}</span></div>
                <div class="val-row"><span class="val-label">P&L:</span><span class="{pnl_class}">₹{pnl:,.2f} ({pnl_pct:+.2f}%)</span></div>
                <div class="val-row"><span class="val-label">Locked SL:</span><span class="val-data">₹{r['sl']:,.2f}</span></div>
                <div class="val-row"><span class="val-label">Targets (T1/T2/T3):</span><span class="val-data">₹{r['t1']:,.2f} | ₹{r['t2']:,.2f} | ₹{r['t3']:,.2f}</span></div>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    with st.expander("⚙️ Remove Stock"):
        del_id = st.selectbox("Select Stock to Delete", options=df_pos['id'].tolist(), format_func=lambda x: df_pos[df_pos['id']==x]['symbol'].values[0])
        if st.button("Delete"):
            cursor.execute("DELETE FROM positions WHERE id = ?", (del_id,))
            conn.commit()
            st.success("Deleted!")
            st.rerun()
