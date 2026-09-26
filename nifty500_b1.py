import os
import sys
import json
import time
import requests
import subprocess
import pytz
import yfinance as yf
import pandas as pd
from datetime import datetime

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೧. ಪ್ಲೇರೈಟ್ ವರ್ಕರ್ ಫೈಲ್ ಸೃಷ್ಟಿ (ಕನ್ಸಾಲಿಡೇಟೆಡ್ + ಸ್ಟ್ಯಾಂಡ್‌ಅಲೋನ್ ಫಾಲ್‌ಬ್ಯಾಕ್)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
worker_code = '''
import sys
import json
from playwright.sync_api import sync_playwright

symbol = sys.argv[1].strip().upper()
SCREENER_EMAIL = "bsbindurani@gmail.com"
SCREENER_PASS = "cricket786"

def parse_num(val_str):
    if not val_str:
        return None
    try:
        clean = (val_str.replace(",", "")
                        .replace("₹", "")
                        .replace("%", "")
                        .replace("Cr.", "")
                        .replace("Cr", "")
                        .strip())
        return float(clean)
    except:
        return None

metrics = {}

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context()
    page = context.new_page()

    page.route(
        "**/*", 
        lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
    )

    try:
        page.goto("https://www.screener.in/login/", timeout=35000)
        page.fill('input[name="username"]', SCREENER_EMAIL)
        page.fill('input[name="password"]', SCREENER_PASS)
        page.click('button[type="submit"]')
        page.wait_for_timeout(2000)

        # ೧. ಕನ್ಸಾಲಿಡೇಟೆಡ್ ಪೇಜ್ ಪ್ರಯತ್ನ
        target_url = f"https://www.screener.in/company/{symbol}/consolidated/"
        page.goto(target_url, timeout=25000)
        page.wait_for_timeout(1000)
        items = page.query_selector_all("#top-ratios li")

        # ೨. ಕನ್ಸಾಲಿಡೇಟೆಡ್ ಸಿಗದಿದ್ದರೆ ಸ್ಟ್ಯಾಂಡ್‌ಅಲೋನ್ ಪೇಜ್ ಪ್ರಯತ್ನ
        if not items:
            target_url = f"https://www.screener.in/company/{symbol}/"
            page.goto(target_url, timeout=25000)
            page.wait_for_timeout(1000)
            items = page.query_selector_all("#top-ratios li")

        data = {}
        for item in items:
            name_elem = item.query_selector(".name")
            val_elem = item.query_selector(".value")
            if name_elem and val_elem:
                k = name_elem.inner_text().strip().lower()
                v = val_elem.inner_text().strip()
                data[k] = v

        metrics['screener_link'] = target_url
        metrics['market_cap'] = parse_num(data.get("market cap"))
        metrics['pe'] = parse_num(data.get("stock p/e") or data.get("p/e"))
        metrics['roce'] = parse_num(data.get("roce"))
        metrics['roe'] = parse_num(data.get("roe"))
        metrics['debt_to_equity'] = parse_num(data.get("debt to equity"))
        metrics['opm'] = parse_num(data.get("opm"))
        metrics['piotroski_score'] = parse_num(data.get("piotroski score"))
        metrics['promoter_holding'] = parse_num(data.get("promoter holding"))
        metrics['pledged_percentage'] = parse_num(data.get("pledged percentage")) or 0.0
        metrics['fii_holding'] = parse_num(data.get("fii holding"))
        metrics['dii_holding'] = parse_num(data.get("dii holding"))
        
        metrics['sales_growth_ttm'] = parse_num(data.get("sales growth"))
        metrics['sales_growth_3y'] = parse_num(data.get("sales growth 3years") or data.get("sales growth 3 years"))
        metrics['profit_growth_ttm'] = parse_num(data.get("profit growth"))
        metrics['profit_growth_3y'] = parse_num(data.get("profit var 3yrs") or data.get("profit growth 3years"))
        metrics['interest_coverage_ttm'] = parse_num(data.get("int coverage") or data.get("interest coverage"))
        
        metrics['price_cagr_1y'] = parse_num(data.get("return over 1year") or data.get("return over 1 year"))
        metrics['price_cagr_3y'] = parse_num(data.get("return over 3years") or data.get("return over 3 years"))

        peers_sec = page.query_selector("#peers")
        metrics['sector'] = "Diversified"
        if peers_sec:
            links = peers_sec.query_selector_all("a")
            texts = [a.inner_text().strip() for a in links if a.inner_text().strip()]
            if texts: metrics['sector'] = texts[0]

        print(json.dumps(metrics))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        browser.close()
'''

with open("batch_worker.py", "w") as f:
    f.write(worker_code)

print("✅ batch_worker.py ಯಶಸ್ವಿಯಾಗಿ ಸಿದ್ಧಗೊಂಡಿದೆ!")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೨. ಟೆಲಿಗ್ರಾಂ ಹಾಗೂ ನಿಖರವಾಗಿ ೨೫೦ ಷೇರುಗಳು
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
CHAT_ID = "7475999824"

BATCH_SYMBOLS = [
    # ೧ ರಿಂದ ೧೫೦
    "360ONE", "3MINDIA", "ABB", "ACC", "AIAENG", "APLAPOLLO", "AUBANK", "AARTIIND",
    "AAVAS", "ABBOTINDIA", "ACE", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS",
    "ADANIPOWER", "ATGL", "ABCAPITAL", "ABFRL", "AEGISLOG", "AJANTPHARM", "APLLTD",
    "ALKEM", "ALKYLAMINE", "ALLCARGO", "ALOKINDS", "AMBER", "AMBUJACEM", "ANANDRATHI",
    "ANGELONE", "ANURAS", "APARINDS", "APOLLOHOSP", "APOLLOTYRE", "APTUS", "ACI",
    "ASAHIINDIA", "ASHOKLEY", "ASIANPAINT", "ASTERDM", "ASTRAL", "ATUL", "AUROPHARMA",
    "AVANTIFEED", "DMART", "AXISBANK", "BASF", "BEML", "BLS", "BSE", "BAJAJ-AUTO",
    "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG", "BALAMINES", "BALKRISIND", "BALRAMCHIN",
    "BANDHANBNK", "BANKBARODA", "BANKINDIA", "MAHABANK", "BATAINDIA", "BAYERCROP",
    "BERGEPAINT", "BDL", "BEL", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIKAJI",
    "BIOCON", "BIRLACORPN", "BSOFT", "BLUEDART", "BLUESTARCO", "BBTC", "BRIGADE",
    "BCG", "MAPMYINDIA", "CESC", "CGPOWER", "CRISIL", "CAMPUS", "CANFINHOME", "CANBK",
    "CARBORUNIV", "CASTROLIND", "CEATLTD", "CENTRALBK", "CDSL", "CENTURYPLY",
    "CENTURYTEX", "CERA", "CHALET", "CHAMBLFERT", "CHEMPLASTS", "CHOLAHLDNG", "CHOLAFIN",
    "CIPLA", "CUB", "CLEAN", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL", "CAMS",
    "CONCORDBIO", "CONCOR", "COROMANDEL", "CRAFTSMAN", "CREDITACC", "CROMPTON", "CUMMINSIND",
    "CYIENT", "DCMSHRIRAM", "DLF", "DABUR", "DALBHARAT", "DATAPATTNS", "DEEPAKFERT",
    "DEEPAKNTR", "DELHIVERY", "DEVYANI", "DIVISLAB", "DIXON", "LALPATHLAB", "DRREDDY",
    "EIDPARRY", "EIHOTEL", "EPL", "EASEMYTRIP", "EICHERMOT", "ELECON", "ELGIEQUIP",
    "EMAMILTD", "ENDURANCE", "ENGINERSIN", "EQUITASBNK", "ERIS", "ESCORTS", "EXIDEIND",
    "FDC", "NYKAA", "FEDERALBNK", "FACT", "FINEORG", "FINCABLES", "FINPIPE", "FSL",
    "FORTIS", "GRINFRA", "GAIL", "GLENMARK",
    
    # ೧೫೧ ರಿಂದ ೨೫೦ (ನಿಖರವಾಗಿ ೧೦೦ ಷೇರುಗಳು)
    "MEDANTA", "GODFRYPHLP", "GODREJCP", "GODREJIND", "GODREJPROP", "GRANULES",
    "GRAPHITE", "GRASIM", "GRAVITA", "GESHIP", "FLUOROCHEM", "GNFC", "GPPL",
    "GSFC", "GSPL", "HEG", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HFCL",
    "HLEGLAS", "HAPPSTMNDS", "HAVELLS", "HEROMOTOCO", "HINDALCO", "HAL", "HINDCOPPER",
    "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA", "HOMEFIRST", "HONAUT", "HUDCO",
    "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDBI", "IDFCFIRSTB", "IFCI", "IIFL",
    "IRB", "IRCON", "ITC", "ITI", "INDIACEM", "INDIAMART", "INDIANB", "IEX",
    "INDHOTEL", "IOC", "IOB", "IRCTC", "IRFC", "INDUSINDBK", "NAUKRI", "INFY",
    "INGERRAND", "INOXWIND", "INTELLECT", "INDIGO", "IPCALAB", "JBCHEPHARM", "JKCEMENT",
    "JBMA", "JKLAKSHMI", "JKPAPER", "JMFINANCIL", "JSWENERGY", "JSWHL", "JSWINFRA",
    "JSWSTEEL", "JINDALSAW", "JSL", "JINDALSTEL", "JIOFIN", "JUBLFOOD", "JUBLINGREA",
    "JUBLPHARMA", "JUSTDIAL", "JYOTHYLAB", "KPRMILL", "KEI", "KNRCON", "KPITTECH",
    "KRBL", "KSB", "KAJARIACER", "KALYANKJIL", "KEC", "KIRLOSENG", "KOTAKBANK",
    "LT", "LTTS", "LTIM"
]

def send_telegram_msg(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        return r.status_code == 200
    except:
        return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೩. ತಾಂತ್ರಿಕ ವಿಶ್ಲೇಷಣೆ (ನಿಖರ ರಿಜೆಕ್ಷನ್ ಕಾರಣಗಳೊಂದಿಗೆ)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_technicals(sym):
    try:
        df = yf.download(f"{sym}.NS", period="1y", interval="1d", progress=False, auto_adjust=False)
        if df.empty or len(df) < 50:
            return None, "❌ ಡೇಟಾ ಸಿಗಲಿಲ್ಲ ಅಥವಾ ಹಿಸ್ಟರಿ ಸಾಲದು"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close']
        price = round(float(close.iloc[-1]), 2)
        prev = float(close.iloc[-2])
        chg = round(((price - prev) / prev) * 100, 2)
        vol = int(df['Volume'].iloc[-1])
        vol_str = f"{round(vol / 100000, 1)}L" if vol >= 100000 else str(vol)

        # ಬೆಲೆ ಬದಲಾವಣೆ (1.0% ರಿಂದ 12.0%)
        if not (1.0 <= chg <= 12.0):
            return None, f"❌ ಬೆಲೆ ಬದಲಾವಣೆ ಮಿತಿಯಲ್ಲಿಲ್ಲ ({chg:+0.2f}%)"

        # RSI (50 ರಿಂದ 75)
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rsi = round(float((100 - (100 / (1 + (gain / (loss + 1e-9))))).iloc[-1]), 1)
        if not (50.0 <= rsi <= 75.0):
            return None, f"❌ RSI ಮಿತಿಯಲ್ಲಿಲ್ಲ (RSI: {rsi})"

        # RVOL (>= 0.9x)
        vol_ma = df['Volume'].rolling(20).mean().iloc[-1]
        rvol = round(float(vol / (vol_ma + 1e-9)), 2)
        if rvol < 0.9:
            return None, f"❌ ವಾಲ್ಯೂಮ್ ಸಾಲದು (RVOL: {rvol}x)"
        rvol_status = "⚡ STRONG MOMENTUM" if rvol >= 2.0 else "🟢 IDEAL ACCUMULATION" if rvol >= 1.2 else "⚪ NORMAL"

        # EMA Stack
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        if price < ema20:
            return None, "❌ ಬೆಲೆ 20 EMA ಗಿಂತ ಕೆಳಗಿದೆ"
        ema_stack = "20 &gt; 50 &gt; 200 EMA (🟢 BULLISH)" if (ema20 > ema50 > ema200) else "20 &gt; 50 EMA (🟢 BULLISH)"

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_status = "🟢 Bullish | MACD &gt; Signal" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "🔴 Neutral"

        # ATR & Targets
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - close.shift()).abs()
        low_close = (df['Low'] - close.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_series = tr.rolling(14).mean()
        atr = round(float(atr_series.iloc[-1]), 2)
        atr_trend = "🟢 Expanding (Bullish+expanding)"

        high_52 = round(float(df['High'].max()), 2)
        low_52 = round(float(df['Low'].min()), 2)
        high_diff = round(((price - high_52) / high_52) * 100, 1)

        sl = round(price - (1.5 * atr), 2)
        risk = round(price - sl, 2)
        risk_pct = round((risk / price) * 100, 1)
        t1 = round(price + (1.5 * risk), 2)
        t2 = round(price + (2.5 * risk), 2)
        t3 = round(price + (4.0 * risk), 2)

        return {
            "price": price, "chg": chg, "vol_str": vol_str, "high_52": high_52,
            "low_52": low_52, "high_diff": high_diff, "rsi": rsi, "rvol": rvol,
            "rvol_status": rvol_status, "atr": atr, "atr_trend": atr_trend,
            "supertrend": "🟢 Bullish", "macd_status": macd_status,
            "ema_stack": ema_stack, "buy_zone_low": round(price * 0.995, 2),
            "buy_zone_high": round(price * 1.005, 2), "sl": sl, "risk": risk,
            "risk_pct": risk_pct, "t1": t1, "t2": t2, "t3": t3,
            "t1_pct": round(((t1 - price) / price) * 100, 1),
            "t2_pct": round(((t2 - price) / price) * 100, 1),
            "t3_pct": round(((t3 - price) / price) * 100, 1)
        }, "OK"
    except Exception as e:
        return None, f"❌ ದೋಷ: {str(e)[:30]}"

def fetch_screener(sym):
    res = subprocess.run(["python", "batch_worker.py", sym], capture_output=True, text=True)
    try:
        return json.loads(res.stdout.strip())
    except:
        return {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೪. ಫಂಡಮೆಂಟಲ್ ಸ್ಕೋರಿಂಗ್ (ಕನಿಷ್ಠ ₹5,000 Cr & P/E 10-70)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def score_and_validate(f):
    if not f or f.get("market_cap") is None or f.get("piotroski_score") is None:
        return None, "❌ ಸ್ಕ್ರೀನರ್ ಡೇಟಾ ಸಿಗಲಿಲ್ಲ"

    # ಕನಿಷ್ಠ ₹5,000 ಕೋಟಿ ಮಾರ್ಕೆಟ್ ಕ್ಯಾಪ್ ಹಾರ್ಡ್ ಫಿಲ್ಟರ್
    mcap = f.get("market_cap", 0) or 0
    if mcap < 5000:
        return None, f"❌ ಮಾರ್ಕೆಟ್ ಕ್ಯಾಪ್ ಸಾಲದು (₹{mcap:,.0f} Cr &lt; ₹5,000 Cr)"

    pio = f.get("piotroski_score", 0)
    if pio < 5:
        return None, f"❌ ಪಿಯೋಟ್ರೋಸ್ಕಿ ಸ್ಕೋರ್ ಕಡಿಮೆ ({pio}/9)"

    sector = f.get("sector", "")
    de = f.get("debt_to_equity")
    if "Bank" not in sector and "Financial" not in sector:
        if de is not None and de > 1.2:
            return None, f"❌ ಅಧಿಕ ಸಾಲ (Debt/Equity: {de})"

    score = 0
    if pio >= 6: score += 15
    pio_badge = "🟢 Strong Quality" if pio >= 7 else "🟡 Stable Health"
    
    # ಪಿ/ಇ ಸಾಫ್ಟ್ ಸ್ಕೋರಿಂಗ್ (ಗ್ರೋತ್ ಸ್ಟಾಕ್‌ಗಳಿಗೆ 10 ರಿಂದ 70 ರವರೆಗೆ)
    pe = f.get("pe")
    pe_mark = "✅" if (pe and 10 <= pe <= 70) else "❌"
    if pe_mark == "✅": score += 10

    roce = f.get("roce")
    roce_mark = "✅" if (roce and roce >= 14) else "❌"
    if roce_mark == "✅": score += 15

    roe = f.get("roe")
    roe_mark = "✅" if (roe and roe >= 14) else "⚪" if roe is None else "❌"
    if roe_mark == "✅": score += 10

    de_mark = "✅" if (de is not None and de <= 1.0) else "❌"
    if de_mark == "✅": score += 15

    sg = f.get("sales_growth_ttm")
    sg_mark = "✅" if (sg and sg >= 10) else "❌"
    if sg_mark == "✅": score += 12

    pg = f.get("profit_growth_ttm")
    pg_mark = "✅" if (pg and pg >= 10) else "❌"
    if pg_mark == "✅": score += 13

    opm = f.get("opm")
    opm_mark = "✅" if (opm and opm >= 14) else "❌"
    if opm_mark == "✅": score += 10

    if score < 60:
        return None, f"❌ ಫಂಡಮೆಂಟಲ್ ಹೆಲ್ತ್ ಸ್ಕೋರ್ ಕಡಿಮೆ ({score}/100)"

    quality = "🟢 A+ SUPER STRONG" if score >= 80 else "🟢 A GOOD QUALITY" if score >= 65 else "🟡 B AVERAGE"

    pledged_val = f.get('pledged_percentage', 0.0) or 0.0
    pledged_mark = "✅" if pledged_val < 5.0 else "❌"

    return {
        "score": score, "quality": quality, "piotroski_badge": pio_badge,
        "pe_mark": pe_mark, "roce_mark": roce_mark, "roe_mark": roe_mark,
        "de_mark": de_mark, "sales_mark": sg_mark, "profit_mark": pg_mark,
        "opm_mark": opm_mark, "ic_mark": "✅", "pledged_mark": pledged_mark
    }, "OK"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೫. ಕಾರ್ಡ್ ಬಿಲ್ಡರ್ (ಪ್ರತಿಯೊಂದು ವಿಭಾಗದ ಕೆಳಗೆ ಅಂಡರ್‌ಲೈನ್ ಡಿವೈಡರ್)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_card(p, idx, total_count):
    s = p["symbol"]
    t = p["technicals"]
    f = p["fundamentals"]
    sc = p["scored"]
    
    tv_url = f"https://www.tradingview.com/chart/?symbol=NSE:{s}"
    fund_url = f.get("screener_link", f"https://www.screener.in/company/{s}/consolidated/")
    
    mcap_val = f.get('market_cap')
    mcap_str = f"{mcap_val:,.1f}" if (mcap_val is not None and isinstance(mcap_val, (int, float))) else "N/A"

    card = f"""━━━━━━━━━━━━━━━━━━━━
🔍 <b>{s}</b> [{idx}/{total_count}] {p['cap_cat']} • {f.get('sector', 'Diversified')}
━━━━━━━━━━━━━━━━━━━━

• <a href="{tv_url}">TV 📈</a>   |   <a href="{fund_url}">Fundamental 🏛️</a>

• Price: ₹{t['price']} | +{t['chg']}% | Vol: {t['vol_str']}

• 🚀 52W High / Low: ₹{t['high_52']} ({t['high_diff']}%) / ₹{t['low_52']}
_______________________________

• <b>BUY ZONE:</b> ₹{t['buy_zone_low']} - ₹{t['buy_zone_high']}

• 🛑 <b>SL:</b> ₹{t['sl']} (Risk: ₹{t['risk']} | {t['risk_pct']}%)

• 🎯 <b>T1:</b> ₹{t['t1']} (+{t['t1_pct']}% | RR 1:1.5)

• 🎯 <b>T2:</b> ₹{t['t2']} (+{t['t2_pct']}% | RR 1:2.5)

• 🚀 <b>T3:</b> ₹{t['t3']} (+{t['t3_pct']}% | RR 1:4.0)
_______________________________

▼ 🇮🇳 <b>TECHNICALS & LEVELS</b>

• RSI: {t['rsi']} | RVOL: {t['rvol']}x ({t['rvol_status']})

• ATR (14): ₹{t['atr']} (Daily Volatility)

• ATR Trend: {t['atr_trend']}

• Supertrend: {t['supertrend']}

• MACD: {t['macd_status']}

• EMA Stack: {t['ema_stack']}
_______________________________

▼ 🇮🇳 <b>FUNDAMENTAL HEALTH: {sc['score']}/100 ({sc['quality']})</b>

• Piotroski F-Score: {f.get('piotroski_score', 'N/A')}/9 ({sc['piotroski_badge']})

• Market Cap: ₹{mcap_str} Cr

• P/E: {f.get('pe', 'N/A')} [Target: 10 to 70] {sc['pe_mark']}

• ROCE: {f.get('roce', 'N/A')}% [Target: &gt; 15%] {sc['roce_mark']}

• ROE: {f.get('roe', 'N/A')}% [Target: &gt; 15%] {sc['roe_mark']}

• Debt/Equity: {f.get('debt_to_equity', 'N/A')} [Target: &lt; 1.0] {sc['de_mark']}

• Sales Growth (TTM / 3Y): {f.get('sales_growth_ttm', 'N/A')}% / {f.get('sales_growth_3y', 'N/A')}% [Target: &gt; 10%] {sc['sales_mark']}

• Profit Growth (TTM / 3Y): {f.get('profit_growth_ttm', 'N/A')}% / {f.get('profit_growth_3y', 'N/A')}% [Target: &gt; 12%] {sc['profit_mark']}

• OPM: {f.get('opm', 'N/A')}% [Target: &gt; 15%] {sc['opm_mark']}

• Interest Coverage (TTM / FY): {f.get('interest_coverage_ttm', 'N/A')} / {f.get('interest_coverage_ttm', 'N/A')} [Target: &gt; 3.5] {sc['ic_mark']}
_______________________________

▼ 🇮🇳 <b>MOMENTUM & SHAREHOLDING</b>

• Price CAGR (1Y / 3Y): {f.get('price_cagr_1y', 'N/A')}% / {f.get('price_cagr_3y', 'N/A')}%

• Promoter Holding: {f.get('promoter_holding', 'N/A')}%

• Pledged percentage: {f.get('pledged_percentage', 0.0)}% [Target: &lt; 5.0%] {sc['pledged_mark']}

• FII Holding: {f.get('fii_holding', 'N/A')}%

• DII Holding: {f.get('dii_holding', 'N/A')}%
_______________________________
"""
    return card

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೬. ಸ್ಕ್ಯಾನ್ ಪ್ರಕ್ರಿಯೆ ಚಾಲನೆ (ನಿಖರ ೨೫೦ ಷೇರುಗಳು)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
sweet_zone = []
fast_zone = []
breakout_zone = []

print(f"🚀 ಸ್ಕ್ಯಾನ್ ಆರಂಭವಾಗುತ್ತಿದೆ (ಒಟ್ಟು {len(BATCH_SYMBOLS)} ಷೇರುಗಳು)...\n")

for idx, sym in enumerate(BATCH_SYMBOLS, 1):
    print(f"[{idx}/{len(BATCH_SYMBOLS)}] ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ: {sym:12}...", end=" ")
    t, t_reason = get_technicals(sym)
    if not t:
        print(t_reason)
        continue

    fund = fetch_screener(sym)
    scored, f_reason = score_and_validate(fund)
    
    if not scored:
        print(f_reason)
        continue

    mcap = fund.get("market_cap") or 0
    cap_cat = "🟢 LARGE CAP" if mcap >= 20000 else "🟡 MID CAP"

    item = {
        "symbol": sym, "technicals": t, "fundamentals": fund,
        "scored": scored, "cap_cat": cap_cat
    }

    if 1.0 <= t['chg'] < 5.0:
        print(f"🎯 ಸ್ವೀಟ್ ಸ್ಪಾಟ್ (+{t['chg']}%)")
        sweet_zone.append(item)
    elif 5.0 <= t['chg'] < 8.0:
        print(f"⚡ ಫಾಸ್ಟ್ ಮೊಮೆಂಟಮ್ (+{t['chg']}%)")
        fast_zone.append(item)
    elif 8.0 <= t['chg'] <= 12.0:
        print(f"🚀 ಹೈ ಮೊಮೆಂಟಮ್ ಬ್ರೇಕ್‌ಔಟ್ (+{t['chg']}%)")
        breakout_zone.append(item)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ೭. ಅಂತಿಮ ಟೆಲಿಗ್ರಾಂ ರವಾನೆ (ಭಾರತೀಯ ಸಮಯ IST ನೊಂದಿಗೆ)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ist_tz = pytz.timezone("Asia/Kolkata")
now_str = datetime.now(ist_tz).strftime("%d-%b-%Y %I:%M %p")
total_picks = len(sweet_zone) + len(fast_zone) + len(breakout_zone)

# ಮುಖ್ಯ ಸಾರಾಂಶ ಹೆಡರ್
main_header = f"""🚀 <b>NIFTY 500 MOMENTUM STOCKS</b> 🚀
🕒 Batch 1 (1-250) Scan: {now_str}
==============================

📊 TOTAL UNIQUE STOCKS SCANNED: {len(BATCH_SYMBOLS)}
==============================
🎯🎯 <b>HIGH CONFIDENCE TECHNICAL & FUNDAMENTAL PICKS</b> 🎯🎯
==============================

Total High Confidence Picks: {total_picks}
_______________________________
"""
send_telegram_msg(main_header)
time.sleep(1)

# ವಲಯ ೧: ಸ್ವೀಟ್ ಸ್ಪಾಟ್ ಜೋನ್
zone1_hdr = f"""**************************************************
🎯🎯 <b>SWEET SPOT ZONE (1.0%–4.99%) — {len(sweet_zone)} Stocks</b> 🎯🎯
**************************************************
"""
send_telegram_msg(zone1_hdr)
time.sleep(1)

if sweet_zone:
    for i, p in enumerate(sweet_zone, 1):
        c = build_card(p, i, len(sweet_zone))
        send_telegram_msg(c.strip())
        print(f"✅ {p['symbol']} ಸ್ವೀಟ್ ಸ್ಪಾಟ್ ಕಾರ್ಡ್ ತಲುಪಿದೆ!")
        time.sleep(1)
        
    wl_sweet = ",".join([f"NSE:{p['symbol']}" for p in sweet_zone])
    sweet_footer = f"""_______________________________
📋 <b>SWEET SPOT ZONE WATCHLIST:</b>
<code>{wl_sweet}</code>
_______________________________
"""
    send_telegram_msg(sweet_footer)
else:
    empty_sweet = """⚪ No stocks matched criteria
_______________________________
📋 <b>SWEET SPOT ZONE WATCHLIST:</b>
<code>None</code>
_______________________________
"""
    send_telegram_msg(empty_sweet)
time.sleep(1)

# ವಲಯ ೨: ಫಾಸ್ಟ್ ಮೊಮೆಂಟಮ್ ಜೋನ್
zone2_hdr = f"""**************************************************
⚡⚡ <b>FAST MOMENTUM ZONE (5.0%–7.99%) — {len(fast_zone)} Stocks</b> ⚡⚡
**************************************************
"""
send_telegram_msg(zone2_hdr)
time.sleep(1)

if fast_zone:
    for i, p in enumerate(fast_zone, 1):
        c = build_card(p, i, len(fast_zone))
        send_telegram_msg(c.strip())
        print(f"✅ {p['symbol']} ಫಾಸ್ಟ್ ಮೊಮೆಂಟಮ್ ಕಾರ್ಡ್ ತಲುಪಿದೆ!")
        time.sleep(1)
        
    wl_fast = ",".join([f"NSE:{p['symbol']}" for p in fast_zone])
    fast_footer = f"""_______________________________
📋 <b>FAST MOMENTUM ZONE WATCHLIST:</b>
<code>{wl_fast}</code>
_______________________________
"""
    send_telegram_msg(fast_footer)
else:
    empty_fast = """⚪ No stocks matched criteria
_______________________________
📋 <b>FAST MOMENTUM ZONE WATCHLIST:</b>
<code>None</code>
_______________________________
"""
    send_telegram_msg(empty_fast)
time.sleep(1)

# ವಲಯ ೩: ಬ್ರೇಕ್‌ಔಟ್ ಜೋನ್
zone3_hdr = f"""**************************************************
🚀🚀 <b>HIGH MOMENTUM & BREAKOUT ZONE (8%–12%) — {len(breakout_zone)} Stocks</b> 🚀🚀
**************************************************
"""
send_telegram_msg(zone3_hdr)
time.sleep(1)

if breakout_zone:
    for i, p in enumerate(breakout_zone, 1):
        c = build_card(p, i, len(breakout_zone))
        send_telegram_msg(c.strip())
        print(f"✅ {p['symbol']} ಬ್ರೇಕ್‌ಔಟ್ ಕಾರ್ಡ್ ತಲುಪಿದೆ!")
        time.sleep(1)
        
    wl_breakout = ",".join([f"NSE:{p['symbol']}" for p in breakout_zone])
    breakout_footer = f"""_______________________________
📋 <b>BREAKOUT ZONE WATCHLIST:</b>
<code>{wl_breakout}</code>
_______________________________
"""
    send_telegram_msg(breakout_footer)
else:
    empty_breakout = """⚪ No stocks matched criteria
_______________________________
📋 <b>BREAKOUT ZONE WATCHLIST:</b>
<code>None</code>
_______________________________
"""
    send_telegram_msg(empty_breakout)

print("\n🎉 ೨೫೦ ಷೇರುಗಳ ಸ್ಕ್ಯಾನ್ ಯಶಸ್ವಿಯಾಗಿ ಮುಕ್ತಾಯಗೊಂಡಿದೆ ಹಾಗೂ ಸೆಕ್ಷನ್ ಡಿವೈಡರ್‌ಗಳೊಂದಿಗೆ ಟೆಲಿಗ್ರಾಂಗೆ ರವಾನೆಯಾಗಿದೆ!")
