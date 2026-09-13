import yfinance as yf
import sys
import requests

BOT_TOKEN = "8911471339:AAGgdmk4QSh32FFHV_bt6S_hLYs7jBH7Nyg"
CHAT_ID = "7475999824"

def send_telegram_message(message):
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(tg_url, data=payload, timeout=15)
    except Exception as e:
        print(f"Telegram Send Error: {e}", file=sys.stderr)

def get_fundamental_analysis(symbol):
    symbol = symbol.strip().upper()
    ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    metrics = {}
    marks = {}
    
    try:
        t = yf.Ticker(ticker_sym)
        info = t.info

        # Extract metrics safely from yfinance info
        mcap = info.get('marketCap')
        metrics['market_cap'] = round(mcap / 1e7, 2) if mcap else None  # In Crores
        metrics['pe'] = info.get('trailingPE')
        metrics['roce'] = round(info.get('returnOnCapitalEmployed', 0) * 100, 2) if info.get('returnOnCapitalEmployed') else None
        metrics['roe'] = round(info.get('returnOnEquity', 0) * 100, 2) if info.get('returnOnEquity') else None
        
        debt_to_eq = info.get('debtToEquity')
        metrics['debt_to_equity'] = round(debt_to_eq / 100, 2) if debt_to_eq else None
        
        opm = info.get('operatingMargins')
        metrics['opm'] = round(opm * 100, 2) if opm else None
        
        metrics['piotroski_score'] = None  # yfinance doesn't provide piotroski directly
        metrics['promoter_holding'] = None
        metrics['pledged_percentage'] = 0.0
        metrics['fii_holding'] = None
        metrics['dii_holding'] = None
        metrics['sales_growth_ttm'] = round(info.get('revenueGrowth', 0) * 100, 2) if info.get('revenueGrowth') else None
        metrics['profit_growth_ttm'] = round(info.get('earningsGrowth', 0) * 100, 2) if info.get('earningsGrowth') else None
        metrics['interest_coverage_ttm'] = info.get('interestCoverage')

        pe_val = metrics.get('pe')
        marks['pe'] = (10 <= pe_val <= 45) if pe_val is not None else None
        roce_val = metrics.get('roce')
        marks['roce'] = (roce_val > 15) if roce_val is not None else None
        roe_val = metrics.get('roe')
        marks['roe'] = (roe_val > 15) if roe_val is not None else None
        de_val = metrics.get('debt_to_equity')
        marks['debt_to_equity'] = (de_val < 1.0) if de_val is not None else None
        opm_val = metrics.get('opm')
        marks['opm'] = (opm_val > 15) if opm_val is not None else None

        score_pts = 50
        if marks.get('roce'): score_pts += 15
        if marks.get('roe'): score_pts += 15
        if marks.get('debt_to_equity'): score_pts += 10
        if marks.get('pe'): score_pts += 10
        score = min(100, score_pts)
        quality = "🟢 STRONG" if score >= 70 else ("🔴 WEAK" if score < 45 else "🟡 MODERATE")

        return {
            "available": True,
            "score": score,
            "quality": quality,
            "marks": marks,
            "metrics": metrics
        }
    except Exception as e:
        print(f"YFINANCE_FUNDAMENTAL_ERROR: {str(e)}", file=sys.stderr)
        return {"available": False, "score": "N/A", "quality": "⚪ DATA UNAVAILABLE", "marks": {}, "metrics": {}}
        
