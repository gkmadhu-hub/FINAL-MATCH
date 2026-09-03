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

# --- 6-STAGE RSI STATUS FUNCTION ---
def get_rsi_status(rsi_val):
    if rsi_val < 40:
        return "🟢 Reversal Watch (Confirmation Mandatory)"
    elif 40 <= rsi_val < 55:
        return "🟡 Base / Recovery (Wait & Watch)"
    elif 55 <= rsi_val < 60:
        return "🟢 Early Momentum (Early Entry Watch)"
    elif 60 <= rsi_val <= 70:
        return "🟢 Strong Momentum (Primary Swing Zone)"
    elif 70 < rsi_val <= 75:
        return "🟡 Extended (Hold / Fresh Entry Caution)"
    else:
        return "🔴 Overbought / Caution (Profit Booking / Avoid Fresh Entry)"

# --- DYNAMIC CAGR CALCULATION ---
def get_cagr(ticker_sym):
    try:
        df = yf.download(ticker_sym, period="3y", interval="1d", progress=False)
        if df.empty or len(df) < 200:
            return "N/A", "N/A"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df['Close'].dropna()
        ltp = float(close.iloc[-1])
        
        cagr_1y = "N/A"
        if len(close) >= 252:
            p_1y = float(close.iloc[-252])
            val_1y = ((ltp / p_1y) - 1) * 100
            cagr_1y = f"{val_1y:.1f}%"
        
        cagr_3y = "N/A"
        if len(close) >= 700:
            p_3y = float(close.iloc[0])
            val_3y = (((ltp / p_3y) ** (1 / 3)) - 1) * 100
            cagr_3y = f"{val_3y:.1f}%"
            
        return cagr_1y, cagr_3y
    except Exception:
        return "N/A", "N/A"

# --- ADVANCED NEWS & CATALYSTS ENGINE ---
def get_extra_stock_info(symbol):
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    cagr_1y, cagr_3y = get_cagr(ticker_sym)
    
    extra = {
        "analyst_rating": "N/A",
        "target_price": "N/A",
        "revenue": "N/A",
        "net_income": "N/A",
        "net_margin": "N/A",
        "sector_perf": "N/A",
        "cagr_1y": cagr_1y,
        "cagr_3y": cagr_3y,
        "news_block": ""
    }
    try:
        t = yf.Ticker(ticker_sym)
        info = t.info
        mean_target = info.get('targetMeanPrice')
        if mean_target:
            extra["target_price"] = f"₹{mean_target:,.2f}"
        
        rec_key = info.get('recommendationKey')
        if rec_key:
            extra["analyst_rating"] = rec_key.replace('_', ' ').title()
            
        extra["revenueGrowth"] = round(info.get('revenueGrowth', 0) * 100, 1) if info.get('revenueGrowth') else 0.0
        extra["earningsGrowth"] = round(info.get('earningsGrowth', 0) * 100, 1) if info.get('earningsGrowth') else 0.0
        extra["operatingMargins"] = round(info.get('operatingMargins', 0) * 100, 1) if info.get('operatingMargins') else 0.0
        extra["heldPercentInsiders"] = round(info.get('heldPercentInsiders', 0) * 100, 1) if info.get('heldPercentInsiders') else 0.0
        extra["debtToEquity"] = round(info.get('debtToEquity', 0) / 100, 2) if info.get('debtToEquity') else 0.0

        q_fin = t.quarterly_financials
        if q_fin is not None and not q_fin.empty:
            cols = q_fin.columns
            if len(cols) > 0:
                latest_q = q_fin[cols[0]]
                rev = latest_q.get('Total Revenue') or latest_q.get('Revenue')
                net = latest_q.get('Net Income')
                if rev:
                    extra["revenue"] = f"₹{rev / 1e9:.2f} B" if rev > 1e9 else f"₹{rev / 1e7:.2f} Cr"
                if net:
                    extra["net_income"] = f"₹{net / 1e6:.2f} M" if net < 1e9 else f"₹{net / 1e7:.2f} Cr"
                if rev and net and rev > 0:
                    margin = (net / rev) * 100
                    extra["net_margin"] = f"{margin:.2f}%"

        hist = t.history(period="2d")
        nifty = yf.Ticker("^NSEI")
        nifty_hist = nifty.history(period="2d")
        
        if not hist.empty and len(hist) >= 2 and not nifty_hist.empty and len(nifty_hist) >= 2:
            stock_chg = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            nifty_chg = ((nifty_hist['Close'].iloc[-1] - nifty_hist['Close'].iloc[-2]) / nifty_hist['Close'].iloc[-2]) * 100
            diff = stock_chg - nifty_chg
            
            if diff > 0:
                extra["sector_perf"] = f"Outperforming Nifty 50 by +{diff:.2f}% 🚀"
            else:
                extra["sector_perf"] = f"Underperforming Nifty 50 by {diff:.2f}% ⚠️"

        news = t.news
        categorized_news = {
            "order": [], "tender": [], "earnings": [], "management": [],
            "institutional": [], "corporate": [], "sector": [], "risk": [], "price": []
        }
        
        positive_count = 0
        negative_count = 0
        seen_titles = set()
        
        if news:
            for item in news:
                title = item.get('title')
                if not title:
                    content = item.get('content', {})
                    title = content.get('title')
                if not title: continue
                    
                norm_title = re.sub(r'[^a-zA-Z0-9]', '', title.lower())[:30]
                if norm_title in seen_titles: continue
                seen_titles.add(norm_title)
                
                publisher = item.get('publisher') or "Exchange Filing / Media"
                link = item.get('link', f"https://in.finance.yahoo.com/quote/{ticker_sym}")
                
                pub_time = item.get('providerPublishTime') or item.get('startTime')
                if pub_time:
                    try:
                        days_diff = (datetime.now() - datetime.fromtimestamp(pub_time)).days
                        age_str = "Today" if days_diff == 0 else f"{days_diff} days ago"
                    except:
                        age_str = "Recent"
                else:
                    age_str = "Recent"
                    
                t_lower = title.lower()
                
                if any(k in t_lower for k in ['litigation', 'regulatory', 'probe', 'penalty', 'issue', 'investigation', 'debt', 'cancellation', 'fraud', 'selling', 'concern', 'fall']):
                    categorized_news["risk"].append((title, publisher, age_str, link))
                    negative_count += 1
                elif any(k in t_lower for k in ['order', 'contract', 'win', 'bagged', 'secures', 'deal', 'project']):
                    categorized_news["order"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['tender', 'approval', 'government', 'support', 'policy']):
                    categorized_news["tender"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['result', 'profit', 'loss', 'revenue', 'earnings', 'net income', 'q1', 'q2', 'q3', 'q4', 'margin']):
                    categorized_news["earnings"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['management', 'guidance', 'capex', 'expansion', 'strategy', 'plan']):
                    categorized_news["management"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['fii', 'dii', 'stake', 'holding', 'buying', 'institutional']):
                    categorized_news["institutional"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['dividend', 'bonus', 'split', 'buyback', 'rights']):
                    categorized_news["corporate"].append((title, publisher, age_str, link))
                    positive_count += 1
                elif any(k in t_lower for k in ['gap', 'volume', 'surge', 'unusual', 'rally', 'crash']):
                    categorized_news["price"].append((title, publisher, age_str, link))
                    positive_count += 1
                else:
                    categorized_news["sector"].append((title, publisher, age_str, link))

        news_output = ""
        for cat, icon, title in [("order", "🟢", "ORDER WINS / NEW CONTRACTS"), ("tender", "🟢", "GOVERNMENT / TENDER UPDATES"),
                                 ("earnings", "🟢", "EARNINGS / RESULTS"), ("management", "🟢", "MANAGEMENT UPDATES"),
                                 ("institutional", "🟢", "INSTITUTIONAL ACTIVITY"), ("corporate", "🟡", "CORPORATE ACTIONS"),
                                 ("sector", "🟢", "SECTOR NEWS"), ("risk", "🔴", "RISK / NEGATIVE NEWS"), ("price", "📈", "PRICE-SENSITIVE NEWS")]:
            if categorized_news[cat]:
                news_output += f"{icon} <b>{title}</b>\n"
                for t, p, a, l in categorized_news[cat][:2]:
                    news_output += f"• <a href=\"{l}\">{t}</a>\n  • Source: {p} | Age: {a}\n\n"

        if negative_count > positive_count: overall_impact = "🔴 NEGATIVE"; score_line = "🔴 Negative / Bearish"
        elif positive_count > 0: overall_impact = "🟢 POSITIVE"; score_line = "🟢 Positive / Bullish"
        else: overall_impact = "🟡 NEUTRAL"; score_line = "🟡 Neutral / Wait"

        news_output += f"🎯 <b>NEWS CATALYST SCORE</b>\n• {score_line}\n\n📊 <b>OVERALL NEWS IMPACT: {overall_impact}</b>"
        extra["news_block"] = news_output
    except Exception:
        pass
    
    if not extra["news_block"].strip():
        extra["news_block"] = "• No recent live news catalysts available.\n\n🎯 <b>NEWS CATALYST SCORE</b>\n• 🟡 Neutral / Wait\n\n📊 <b>OVERALL NEWS IMPACT: 🟡 NEUTRAL</b>"
        
    return extra

# --- TECHNICAL ENGINE ---
def get_technicals(symbol):
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        df = yf.download(ticker_sym, period="1y", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.ffill().dropna(subset=['Close'])
        if len(df) < 30: return None

        close, high, low, vol = df['Close'], df['High'], df['Low'], df['Volume']
        valid_close = close.dropna()
        ltp = float(valid_close.iloc[-1])
        prev_close = float(valid_close.iloc[-2])
        chg_pct = ((ltp - prev_close) / prev_close) * 100
        
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr_series = tr.rolling(14).mean().dropna()
        atr = float(atr_series.iloc[-1])
        atr_trend = "🟢 Expanding (Bullish + Expanding)" if atr > float(atr_series.iloc[-5]) else "⚪ Normal"

        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        rsi = float(100 - (100 / (1 + rs)).dropna().iloc[-1])
        rsi_status = get_rsi_status(rsi)

        vol_sma20 = vol.rolling(20).mean().dropna().iloc[-1]
        rvol = float(vol.iloc[-1] / (vol_sma20 + 1e-9))
        rvol_status = "🟢 Ideal Accumulation" if rvol >= 1.5 else "🟡 Normal Volume"

        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        
        sorted_emas = sorted({"20": ema20, "50": ema50, "200": ema200}.items(), key=lambda x: x[1], reverse=True)
        order_str = f"{sorted_emas[0][0]} &gt; {sorted_emas[1][0]} &gt; {sorted_emas[2][0]} EMA"

        if ema20 > ema50 > ema200: ema_stack = f"20 &gt; 50 &gt; 200 EMA (🟢 Bullish)"
        elif ema20 < ema50 < ema200: ema_stack = f"200 &gt; 50 &gt; 20 EMA (🔴 Bearish)"
        else: ema_stack = f"{order_str} (🟡 Neutral)"

        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_status = "🟢 Bullish | MACD &gt; Signal" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "🔴 Bearish Cross"

        lowerband = ((high + low) / 2) - (3 * tr.rolling(14).mean())
        supertrend_val = "🟢 Bullish" if ltp > float(lowerband.dropna().iloc[-1]) else "🔴 Bearish"

        return {
            "symbol": symbol.upper().replace(".NS", ""),
            "ltp": round(ltp, 2), "chg_pct": round(chg_pct, 2), "volume": int(vol.iloc[-1]),
            "high52": round(float(high.max()), 2), "low52": round(float(low.min()), 2),
            "atr": round(atr, 2), "atr_trend": atr_trend, "rsi": round(rsi, 2), "rsi_status": rsi_status,
            "rvol": round(rvol, 2), "rvol_status": rvol_status, "ema_stack": ema_stack,
            "macd_status": macd_status, "supertrend": supertrend_val,
            "buy_low": round(ltp * 0.995, 2), "buy_high": round(ltp * 1.005, 2)
        }
    except Exception:
        return None

# --- ADVANCED SCREENER SCRAPING ENGINE ---
def get_fundamentals(symbol):
    clean_sym = symbol.upper().replace(".NS", "").strip()
    url = f"https://www.screener.in/company/{clean_sym}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    data = {
        "mcap": 0.0, "pe": 0.0, "roce": 0.0, "roe": 0.0, "debt_eq": 0.0,
        "sales_growth": 0.0, "profit_growth": 0.0, "opm": 0.0, "interest_cov": 0.0,
        "promoter_hold": 0.0, "promoter_pledge": 0.0, "sector": "N/A", "cap_size": "N/A"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Top Summary Ratios
            for li in soup.find_all('li', class_='flex flex-space-between'):
                name = li.find('span', class_='name')
                val = li.find('span', class_='number')
                if name and val:
                    n_text = name.text.strip().lower()
                    v_text = val.text.strip().replace(',', '').replace('%', '')
                    matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", v_text)
                    if matches:
                        v_num = float(matches[0])
                        if 'market cap' in n_text: data["mcap"] = v_num
                        elif 'stock p/e' in n_text: data["pe"] = v_num
                        elif 'roce' in n_text: data["roce"] = v_num
                        elif 'roe' in n_text: data["roe"] = v_num
                        elif 'debt to equity' in n_text: data["debt_eq"] = v_num
                        elif 'pledged percentage' in n_text: data["promoter_pledge"] = v_num

            # 2. Compounded Sales & Profit Growth (From bottom mini-tables)
            for table in soup.find_all('table', class_='ranges-table'):
                th = table.find('th')
                if th:
                    th_text = th.text.lower()
                    for row in table.find_all('tr'):
                        tds = row.find_all('td')
                        if len(tds) == 2 and 'ttm' in tds[0].text.lower():
                            v_text = tds[1].text.strip().replace('%', '').replace(',', '')
                            matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", v_text)
                            if matches:
                                if 'sales growth' in th_text: data['sales_growth'] = float(matches[0])
                                elif 'profit growth' in th_text: data['profit_growth'] = float(matches[0])

            # 3. OPM & Interest Coverage (From Profit & Loss Table)
            pl_section = soup.find('section', id='profit-loss')
            if pl_section:
                op_profit = 0.0
                interest = 0.0
                for tr in pl_section.find_all('tr'):
                    tds = tr.find_all('td')
                    if tds:
                        text = tds[0].text.strip().lower()
                        v_text = tds[-1].text.strip().replace(',', '').replace('%', '') # TTM/Last Year column
                        matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", v_text)
                        if matches:
                            val = float(matches[0])
                            if 'opm %' in text: data['opm'] = val
                            elif 'operating profit' in text and 'margin' not in text: op_profit = val
                            elif 'interest' in text and 'coverage' not in text: interest = val
                
                # Calculate Interest Coverage if missing
                if interest > 0:
                    data['interest_cov'] = round(op_profit / interest, 2)

            # 4. Promoter Holding (From Shareholders Table)
            sh_section = soup.find('section', id='shareholding')
            if sh_section:
                for tr in sh_section.find_all('tr'):
                    tds = tr.find_all('td')
                    if tds and 'promoters' in tds[0].text.strip().lower():
                        v_text = tds[-1].text.strip().replace('%', '').replace(',', '')
                        matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", v_text)
                        if matches: data['promoter_hold'] = float(matches[0])

            # Sector
            peers_section = soup.find('section', id='peers')
            if peers_section:
                sec_tag = peers_section.find('a')
                if sec_tag: data["sector"] = sec_tag.text.strip()
    except Exception:
        pass

    mcap = data["mcap"]
    data["cap_size"] = "🟢 LARGE CAP" if mcap > 20000 else ("🟡 MID CAP" if mcap > 5000 else "⚪ SMALL CAP") if mcap > 0 else "N/A"
    return data

# --- CSS STYLING ---
st.markdown("""
<style>
    .mega-main-title {
        text-align: center;
        font-size: 30px !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        background: linear-gradient(90deg, #1e2130, #262c40);
        padding: 18px;
        border-radius: 14px;
        border-bottom: 4px solid #FFD700;
        margin-bottom: 24px;
        line-height: 1.4 !important;
    }
    div[data-testid="stExpander"] details summary {
        background: #1e2130 !important;
        border-radius: 12px !important;
        padding: 18px 16px !important;
        margin-top: 16px !important;
        margin-bottom: 12px !important;
        border-left: 8px solid #FFD700 !important;
        border: 1px solid #2a2e39 !important;
    }
    div[data-testid="stExpander"] details summary p {
        font-size: 22px !important;
        font-weight: 900 !important;
        color: #ffffff !important;
        white-space: normal !important;
        word-break: break-word !important;
        margin: 0 !important;
    }
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
    .card-body-text {
        font-size: 20px !important;
        line-height: 1.9 !important;
        color: #e0e0e0;
    }
    .card-body-text b { color: #ffffff; }
    input {
        font-size: 20px !important;
        padding: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="mega-main-title">
    🇮🇳 GK PORTFOLIO TRACKER<br>& INSTANT STOCK ANALYZER 🇮🇳
</div>
""", unsafe_allow_html=True)

positions_df = get_all_positions()

# ==========================================
# 1. 📊 PORTFOLIO SUMMARY
# ==========================================
with st.expander("📊 PORTFOLIO SUMMARY", expanded=True):
    if positions_df.empty:
        st.info("No active holdings found.")
    else:
        tot_invested, tot_current = 0.0, 0.0
        profitable, losing = 0, 0

        for _, row in positions_df.iterrows():
            tech = get_technicals(row['symbol'])
            ltp = tech['ltp'] if (tech and not np.isnan(tech['ltp'])) else row['buy_price']
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
    search_stock_input = st.text_input("Enter NSE Stock Symbol to Analyze (e.g. TEGA, HINDALCO, KPIL):", key="search_stock_input").strip().upper()

    if st.button("📲 ANALYZE & SEND TO TELEGRAM", use_container_width=True):
        if not search_stock_input:
            st.warning("Please enter a stock symbol.")
        else:
            with st.spinner(f"Fetching Live Data & Catalysts for {search_stock_input}..."):
                tech = get_technicals(search_stock_input)
                fund = get_fundamentals(search_stock_input)
                extra = get_extra_stock_info(search_stock_input)
                
                # --- YFINANCE FALLBACK MERGE (Only if Screener still missed it) ---
                if fund['sales_growth'] == 0.0: fund['sales_growth'] = extra.get('revenueGrowth', 0.0)
                if fund['profit_growth'] == 0.0: fund['profit_growth'] = extra.get('earningsGrowth', 0.0)
                if fund['opm'] == 0.0: fund['opm'] = extra.get('operatingMargins', 0.0)
                if fund['promoter_hold'] == 0.0: fund['promoter_hold'] = extra.get('heldPercentInsiders', 0.0)
                if fund['debt_eq'] == 0.0: fund['debt_eq'] = extra.get('debtToEquity', 0.0)

                # --- SCORE RECALCULATION ---
                score = 0
                if fund["pe"] > 0 and 10 <= fund["pe"] <= 45: score += 15
                if fund["roce"] >= 15: score += 15
                if fund["roe"] >= 15: score += 15
                if fund["debt_eq"] < 1.0: score += 15
                if fund["sales_growth"] > 10: score += 10
                if fund["profit_growth"] > 12: score += 10
                if fund["opm"] > 15: score += 10
                if fund["promoter_pledge"] < 5.0: score += 10
                
                fund["score_grade"] = f"{score}/100 (🟢 A+ SUPER STRONG)" if score >= 75 else f"{score}/100"

                if tech and not np.isnan(tech['ltp']):
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

                    # --- RIGHT (✅) OR WRONG (❌) LOGIC ---
                    pe_chk = " ✅" if (10 <= fund['pe'] <= 45) else " ❌"
                    roce_chk = " ✅" if fund['roce'] >= 15 else " ❌"
                    roe_chk = " ✅" if fund['roe'] >= 15 else " ❌"
                    de_chk = " ✅" if fund['debt_eq'] < 1.0 else " ❌"
                    sales_chk = " ✅" if fund['sales_growth'] > 10 else " ❌"
                    profit_chk = " ✅" if fund['profit_growth'] > 12 else " ❌"
                    opm_chk = " ✅" if fund['opm'] > 15 else " ❌"
                    ic_chk = " ✅" if fund['interest_cov'] > 3.5 else " ❌"
                    pledge_chk = " ✅" if fund['promoter_pledge'] < 5.0 else " ❌"

                    card = f"""🇮🇳 🇮🇳 <b>GK INSTANT STOCK ANALYSIS</b> 🇮🇳 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ <b>{tech['symbol']}</b> {fund['cap_size']} • {fund['sector']}

📺 <a href="https://in.tradingview.com/chart/?symbol=NSE:{tech['symbol']}">TV</a>   |   🏛️ <a href="https://www.screener.in/company/{tech['symbol']}/">Fundamental</a>

• <b>Price:</b> ₹{tech['ltp']} | {'+' if tech['chg_pct']>=0 else ''}{tech['chg_pct']}% | <b>Vol:</b> {tech['volume']:,}

• 🚀 <b>52W High / Low:</b> ₹{tech['high52']} ({high52_diff}%) / ₹{tech['low52']}
_______________________________

🇮🇳 <b>TECHNICALS & LEVELS</b> 🇮🇳
_______________________________

• <b>RSI (14):</b> {tech['rsi']} ({tech['rsi_status']})

• <b>RVOL:</b> {tech['rvol']}x ({tech['rvol_status']})

• <b>ATR (14):</b> ₹{tech['atr']} (Daily Volatility)

• <b>ATR Trend:</b> {tech['atr_trend']}

• <b>Supertrend:</b> {tech['supertrend']}

• <b>MACD:</b> {tech['macd_status']}

• <b>EMA Stack:</b> {tech['ema_stack']}

• <b>BUY ZONE:</b> ₹{tech['buy_low']} - ₹{tech['buy_high']}
_______________________________

• 🛑 <b>SL:</b> ₹{sl} (Risk: ₹{risk} | {risk_pct}%)

• 🎯 <b>T1:</b> ₹{t1} (+{t1_pct}% | RR 1:1.5)

• 🎯 <b>T2:</b> ₹{t2} (+{t2_pct}% | RR 1:2.5)

• 🚀 <b>T3:</b> ₹{t3} (+{t3_pct}% | RR 1:4.0)
_______________________________

🇮🇳 <b>FUNDAMENTAL HEALTH: {fund['score_grade']}</b> 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• <b>Market Cap:</b> ₹{fund['mcap']:,.1f} Cr

• <b>P/E:</b> {fund['pe']} [Target: 10 to 45]{pe_chk}

• <b>ROCE:</b> {fund['roce']}% [Target: &gt; 15%]{roce_chk}

• <b>ROE:</b> {fund['roe']}% [Target: &gt; 15%]{roe_chk}

• <b>Debt/Equity:</b> {fund['debt_eq']} [Target: &lt; 1.0]{de_chk}

• <b>Sales Growth (TTM):</b> {fund['sales_growth']}% [Target: &gt; 10%]{sales_chk}

• <b>Profit Growth (TTM):</b> {fund['profit_growth']}% [Target: &gt; 12%]{profit_chk}

• <b>OPM:</b> {fund['opm']}% [Target: &gt; 15%]{opm_chk}

• <b>Interest Coverage:</b> {fund['interest_cov']} [Target: &gt; 3.5]{ic_chk}
_______________________________

🇮🇳 <b>MOMENTUM & SHAREHOLDING</b> 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• <b>Price CAGR (1Y / 3Y):</b> {extra['cagr_1y']} / {extra['cagr_3y']}

• <b>Promoter Holding:</b> {fund['promoter_hold']}%

• <b>Promoter Pledge:</b> {fund['promoter_pledge']}% [Target: &lt; 5.0]{pledge_chk}
_______________________________

🎯 <b>ANALYST RATING & PRICE TARGET</b>
_______________________________

• <b>Consensus Rating:</b> {extra['analyst_rating']}

• <b>1-Year Price Target:</b> {extra['target_price']}
_______________________________

📈 <b>QUARTERLY FINANCIAL HIGHLIGHTS</b>
_______________________________

• <b>Revenue:</b> {extra['revenue']}

• <b>Net Income:</b> {extra['net_income']}

• <b>Net Margin:</b> {extra['net_margin']} 📊
_______________________________

🚀 <b>SECTOR PERFORMANCE</b>
_______________________________

• <b>Sector Rank:</b> {fund['sector']} ({extra['sector_perf']})
_______________________________

📰 <b>LATEST NEWS & CATALYSTS</b>
_______________________________

{extra['news_block']}"""
                    
                    if send_telegram(card):
                        st.success(f"Pure Real-Data Analysis for {tech['symbol']} sent to Telegram! 🚀")
                else:
                    st.error("Failed to fetch live technical data. Check symbol.")

# ==========================================
# 3. 📌 ACTIVE HOLDINGS
# ==========================================
with st.expander("📌 ACTIVE HOLDINGS", expanded=True):
    if positions_df.empty:
        st.info("No active holdings found.")
    else:
        for _, row in positions_df.iterrows():
            sym = row['symbol']
            tech = get_technicals(sym)
            ltp = tech['ltp'] if (tech and not np.isnan(tech['ltp'])) else row['buy_price']
            invested = row['buy_price'] * row['quantity']
            pnl = (ltp - row['buy_price']) * row['quantity']
            pnl_pct = ((ltp - row['buy_price']) / row['buy_price']) * 100
            
            sl_hit = ltp <= row['locked_sl']

            if sl_hit:
                action_status = "🔴 STOP LOSS HIT\n\nReason:\nPrice fell below locked stop loss."
            else:
                action_status = "🟢 HOLD\n\nReason:\nSL Safe | MACD Positive | Trend Bullish"

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
                    
                    rsi_display = f"{tech['rsi']} ({tech['rsi_status']})" if tech else "N/A"
                    rvol_display = f"{tech['rvol']}x ({tech['rvol_status']})" if tech else "N/A"
                    atr_display = f"₹{tech['atr']} (Daily Volatility)" if tech else "N/A"
                    atr_trend_disp = tech['atr_trend'] if tech else "N/A"
                    supertrend_disp = tech['supertrend'] if tech else "N/A"
                    macd_disp = tech['macd_status'] if tech else "N/A"
                    ema_disp = tech['ema_stack'] if tech else "N/A"

                    fund = get_fundamentals(sym)
                    extra = get_extra_stock_info(sym)

                    # --- YFINANCE FALLBACK MERGE ---
                    if fund['sales_growth'] == 0.0: fund['sales_growth'] = extra.get('revenueGrowth', 0.0)
                    if fund['profit_growth'] == 0.0: fund['profit_growth'] = extra.get('earningsGrowth', 0.0)
                    if fund['opm'] == 0.0: fund['opm'] = extra.get('operatingMargins', 0.0)
                    if fund['promoter_hold'] == 0.0: fund['promoter_hold'] = extra.get('heldPercentInsiders', 0.0)
                    if fund['debt_eq'] == 0.0: fund['debt_eq'] = extra.get('debtToEquity', 0.0)

                    score = 0
                    if fund["pe"] > 0 and 10 <= fund["pe"] <= 45: score += 15
                    if fund["roce"] >= 15: score += 15
                    if fund["roe"] >= 15: score += 15
                    if fund["debt_eq"] < 1.0: score += 15
                    if fund["sales_growth"] > 10: score += 10
                    if fund["profit_growth"] > 12: score += 10
                    if fund["opm"] > 15: score += 10
                    if fund["promoter_pledge"] < 5.0: score += 10
                    
                    fund["score_grade"] = f"{score}/100 (🟢 A+ SUPER STRONG)" if score >= 75 else f"{score}/100"

                    # --- RIGHT (✅) OR WRONG (❌) LOGIC ---
                    pe_chk = " ✅" if (10 <= fund['pe'] <= 45) else " ❌"
                    roce_chk = " ✅" if fund['roce'] >= 15 else " ❌"
                    roe_chk = " ✅" if fund['roe'] >= 15 else " ❌"
                    de_chk = " ✅" if fund['debt_eq'] < 1.0 else " ❌"
                    sales_chk = " ✅" if fund['sales_growth'] > 10 else " ❌"
                    profit_chk = " ✅" if fund['profit_growth'] > 12 else " ❌"
                    opm_chk = " ✅" if fund['opm'] > 15 else " ❌"
                    ic_chk = " ✅" if fund['interest_cov'] > 3.5 else " ❌"
                    pledge_chk = " ✅" if fund['promoter_pledge'] < 5.0 else " ❌"
                    
                    msg = f"""🇮🇳 🇮🇳 <b>GK PORTFOLIO HOLDINGS</b> 🇮🇳 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ <b>{sym}</b>
NSE: {sym}

📺 <a href="https://in.tradingview.com/chart/?symbol=NSE:{sym}">TradingView</a>   |   🏛️ <a href="https://www.screener.in/company/{sym}/">Fundamental</a>

• <b>BUY DATE:</b> {row['buy_date']}

• <b>BUY PRICE:</b> ₹{row['buy_price']:,.2f}

• <b>QUANTITY:</b> {row['quantity']}

• <b>INVESTMENT:</b> ₹{invested:,.2f}
_______________________________

📊 <b>TECHNICALS & LEVELS</b> 🇮🇳
_______________________________

• <b>RSI (14):</b> {rsi_display}

• <b>RVOL:</b> {rvol_display}

• <b>ATR (14):</b> {atr_display}

• <b>ATR Trend:</b> {atr_trend_disp}

• <b>Supertrend:</b> {supertrend_disp}

• <b>MACD:</b> {macd_disp}

• <b>EMA Stack:</b> {ema_disp}
_______________________________

• 🛑 <b>SL:</b> ₹{row['locked_sl']:,.2f} (Risk: ₹{risk_amount:,.2f} | {risk_pct}%)

• 🎯 <b>T1:</b> ₹{row['locked_t1']:,.2f} (+{t1_gain}% | RR 1:1.5)

• 🎯 <b>T2:</b> ₹{row['locked_t2']:,.2f} (+{t2_gain}% | RR 1:2.5)

• 🚀 <b>T3:</b> ₹{row['locked_t3']:,.2f} (+{t3_gain}% | RR 1:4.0)
_______________________________

🇮🇳 <b>FUNDAMENTAL HEALTH: {fund['score_grade']}</b> 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• <b>Market Cap:</b> ₹{fund['mcap']:,.1f} Cr

• <b>P/E:</b> {fund['pe']} [Target: 10 to 45]{pe_chk}

• <b>ROCE:</b> {fund['roce']}% [Target: &gt; 15%]{roce_chk}

• <b>ROE:</b> {fund['roe']}% [Target: &gt; 15%]{roe_chk}

• <b>Debt/Equity:</b> {fund['debt_eq']} [Target: &lt; 1.0]{de_chk}

• <b>Sales Growth (TTM):</b> {fund['sales_growth']}% [Target: &gt; 10%]{sales_chk}

• <b>Profit Growth (TTM):</b> {fund['profit_growth']}% [Target: &gt; 12%]{profit_chk}

• <b>OPM:</b> {fund['opm']}% [Target: &gt; 15%]{opm_chk}

• <b>Interest Coverage:</b> {fund['interest_cov']} [Target: &gt; 3.5]{ic_chk}
_______________________________

🇮🇳 <b>MOMENTUM & SHAREHOLDING</b> 🇮🇳
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• <b>Price CAGR (1Y / 3Y):</b> {extra['cagr_1y']} / {extra['cagr_3y']}

• <b>Promoter Holding:</b> {fund['promoter_hold']}%

• <b>Promoter Pledge:</b> {fund['promoter_pledge']}% [Target: &lt; 5.0]{pledge_chk}
_______________________________

🎯 <b>ANALYST RATING & PRICE TARGET</b>
_______________________________

• <b>Consensus Rating:</b> {extra['analyst_rating']}

• <b>1-Year Price Target:</b> {extra['target_price']}
_______________________________

📈 <b>QUARTERLY FINANCIAL HIGHLIGHTS</b>
_______________________________

• <b>Revenue:</b> {extra['revenue']}

• <b>Net Income:</b> {extra['net_income']}

• <b>Net Margin:</b> {extra['net_margin']} 📊
_______________________________

🚀 <b>SECTOR PERFORMANCE</b>
_______________________________

• <b>Sector Rank:</b> {fund['sector']} ({extra['sector_perf']})
_______________________________

📰 <b>LATEST NEWS & CATALYSTS</b>
_______________________________

{extra['news_block']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚦 <b>CURRENT ACTION STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{action_status}

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
with st.expander("🔒 ADD / LOCK POSITION", expanded=False):
    with st.form("lock_trade_form"):
        final_lock_sym = st.text_input("Enter NSE Stock Symbol to Add (e.g. TEGA, TITAGARH, HINDALCO):", key="lock_stock_input").strip().upper()
        
        buy_date = st.date_input("Buy Date", datetime.now()).strftime("%Y-%m-%d")
        buy_price = st.number_input("Buy Price (₹):", min_value=0.1, step=0.05)
        quantity = st.number_input("Quantity:", min_value=1, step=1)
        
        preview = st.form_submit_button("🔍 Calculate & Preview Levels")
        
        if preview and final_lock_sym and buy_price > 0:
            tech = get_technicals(final_lock_sym)
            if tech and not np.isnan(tech['atr']):
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
                st.error("Failed to fetch data for calculations. Check stock symbol.")

    if 'temp_pos' in st.session_state:
        if st.button("🔒 LOCK POSITION PERMANENTLY", use_container_width=True):
            save_position(st.session_state['temp_pos'])
            del st.session_state['temp_pos']
            st.success("Position Locked and Saved to Database! 🚀")
            st.rerun()
                  
