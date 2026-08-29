import os
import re
import requests
import yfinance as yf
from bs4 import BeautifulSoup

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# Screener Login Credentials
SCREENER_USER = os.getenv("SCREENER_USERNAME", "bsbindurani@gmail.com")
SCREENER_PASS = os.getenv("SCREENER_PASSWORD", "cricket786")

def clean_val(val_str):
    if val_str is None:
        return None
    try:
        clean = str(val_str).replace('%', '').replace(',', '').replace('₹', '').replace('Cr', '').strip()
        return float(clean)
    except Exception:
        return None

def get_screener_session():
    if HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
    else:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        })
    
    # Official Screener Login Flow
    try:
        login_url = "https://www.screener.in/login/"
        res = session.get(login_url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        
        if csrf_token:
            payload = {
                'username': SCREENER_USER,
                'password': SCREENER_PASS,
                'csrfmiddlewaretoken': csrf_token['value']
            }
            headers = {
                'Referer': login_url,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
            session.post(login_url, data=payload, headers=headers, timeout=10)
    except Exception:
        pass
        
    return session

screener_session = get_screener_session()

def get_screener_data(symbol):
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    
    metrics = {
        'market_cap': None,
        'cap_category': 'N/A',
        'sector': 'N/A',
        'industry': 'N/A',
        'high_52w': None,
        'low_52w': None,
        'pe': None,
        'roce': None,
        'roe': None,
        'debt_to_equity': None,
        'sales_growth_ttm': None,
        'sales_growth_3y': None,
        'profit_growth_ttm': None,
        'profit_growth_3y': None,
        'opm': None,
        'interest_coverage_ttm': None,
        'interest_coverage_fy': None,
        'price_cagr_1y': None,
        'price_cagr_3y': None,
        'promoter_holding': None,
        'pledged_percentage': None,
        'fii_holding': None,
        'dii_holding': None,
        'piotroski': None,
    }

    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]

    for url in urls:
        try:
            res = screener_session.get(url, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, 'html.parser')

                # 1. Peer / Sector / Industry info
                peers_sec = soup.find('section', {'id': 'peers'})
                if peers_sec:
                    p_links = peers_sec.find_all('a', href=re.compile(r'/market/'))
                    if p_links:
                        metrics['sector'] = p_links[-1].text.strip()
                        if len(p_links) > 1:
                            metrics['industry'] = p_links[0].text.strip()

                # 2. Exact Top Ratios Box Parsing (Key-Value Name Match)
                ratio_items = soup.find_all('li', class_=re.compile(r'flex-space-between'))
                for item in ratio_items:
                    name_span = item.find('span', class_='name')
                    val_span = item.find('span', class_=re.compile(r'value|nowrap'))
                    
                    if name_span and val_span:
                        key = name_span.get_text(strip=True).lower()
                        val = clean_val(val_span.get_text(strip=True))
                        
                        if 'market cap' in key: metrics['market_cap'] = val
                        elif 'stock p/e' in key or key == 'p/e': metrics['pe'] = val
                        elif 'roce' in key: metrics['roce'] = val
                        elif 'roe' in key: metrics['roe'] = val
                        elif 'debt to equity' in key: metrics['debt_to_equity'] = val
                        elif 'opm' in key: metrics['opm'] = val
                        elif 'pledged' in key: metrics['pledged_percentage'] = val
                        elif 'piotroski' in key: metrics['piotroski'] = int(val) if val is not None else None
                        elif 'int coverage' in key or 'interest coverage' in key: 
                            metrics['interest_coverage_ttm'] = val
                            metrics['interest_coverage_fy'] = val
                        elif 'sales growth 3years' in key or 'sales growth 3yrs' in key: metrics['sales_growth_3y'] = val
                        elif 'profit var 3yrs' in key or 'profit growth 3yrs' in key: metrics['profit_growth_3y'] = val
                        elif 'sales growth' in key and metrics['sales_growth_ttm'] is None: metrics['sales_growth_ttm'] = val
                        elif 'profit growth' in key and metrics['profit_growth_ttm'] is None: metrics['profit_growth_ttm'] = val
                        elif 'promoter holding' in key: metrics['promoter_holding'] = val
                        elif 'fii holding' in key: metrics['fii_holding'] = val
                        elif 'dii holding' in key: metrics['dii_holding'] = val

                # 3. Growth Rates & Price CAGR Tables
                ranges = soup.find_all('table', {'class': re.compile(r'ranges-table')})
                for t in ranges:
                    th = t.find('th')
                    tname = th.text.strip().lower() if th else ""
                    for r in t.find_all('tr'):
                        tds = r.find_all('td')
                        if len(tds) >= 2:
                            dur = tds[0].text.strip().lower()
                            v = clean_val(tds[1].text)
                            if v is not None:
                                if '3 years' in dur or '3 yrs' in dur:
                                    if 'sales' in tname and metrics['sales_growth_3y'] is None: metrics['sales_growth_3y'] = v
                                    elif 'profit' in tname and metrics['profit_growth_3y'] is None: metrics['profit_growth_3y'] = v
                                    elif 'price' in tname or 'cagr' in tname: metrics['price_cagr_3y'] = v
                                elif 'ttm' in dur:
                                    if 'sales' in tname and metrics['sales_growth_ttm'] is None: metrics['sales_growth_ttm'] = v
                                    elif 'profit' in tname and metrics['profit_growth_ttm'] is None: metrics['profit_growth_ttm'] = v
                                elif '1 year' in dur or '1 yr' in dur:
                                    if 'price' in tname or 'cagr' in tname: metrics['price_cagr_1y'] = v

                # 4. Shareholding Table (Fallback)
                shp = soup.find('section', {'id': 'shareholding'})
                if shp:
                    for tr in shp.find_all('tr'):
                        row_txt = tr.get_text(separator=" ", strip=True).lower()
                        tds = tr.find_all(['td', 'th'])
                        nums = [clean_val(td.get_text(strip=True)) for td in tds if clean_val(td.get_text(strip=True)) is not None]
                        if nums:
                            if 'promoter' in row_txt and metrics['promoter_holding'] is None: metrics['promoter_holding'] = nums[-1]
                            elif 'fii' in row_txt and metrics['fii_holding'] is None: metrics['fii_holding'] = nums[-1]
                            elif 'dii' in row_txt and metrics['dii_holding'] is None: metrics['dii_holding'] = nums[-1]
                            elif 'pledged' in row_txt and metrics['pledged_percentage'] is None: metrics['pledged_percentage'] = nums[-1]

                # 5. P&L Interest Coverage Fallback
                if metrics['interest_coverage_ttm'] is None:
                    pnl = soup.find('section', {'id': 'profit-loss'})
                    if pnl:
                        op_row, int_row = None, None
                        for row in pnl.find_all('tr'):
                            rt = row.get_text(separator=' ', strip=True).lower()
                            if 'operating profit' in rt:
                                vals = [clean_val(td.text) for td in row.find_all('td') if clean_val(td.text) is not None]
                                if vals: op_row = vals[-1]
                            elif 'interest' in rt:
                                vals = [clean_val(td.text) for td in row.find_all('td') if clean_val(td.text) is not None]
                                if vals: int_row = vals[-1]
                        if op_row and int_row and int_row > 0:
                            calc_ic = round(op_row / int_row, 2)
                            metrics['interest_coverage_ttm'] = calc_ic
                            metrics['interest_coverage_fy'] = calc_ic

                if metrics['market_cap'] is not None:
                    break
        except Exception:
            pass

    # YFinance Fallback (ಕೇವಲ Screener ನಲ್ಲಿ ಡೇಟಾ ಸಿಗದಿದ್ದರೆ ಮಾತ್ರ)
    if metrics['sector'] == 'N/A' or metrics['industry'] == 'N/A':
        try:
            ticker = yf.Ticker(f"{clean_sym}.NS")
            info = ticker.info or {}
            if info:
                if metrics['sector'] == 'N/A': metrics['sector'] = info.get('sector') or 'N/A'
                if metrics['industry'] == 'N/A': metrics['industry'] = info.get('industry') or 'N/A'
        except Exception:
            pass

    # Exact Cap Category
    if metrics['market_cap'] is not None:
        if metrics['market_cap'] >= 20000:
            metrics['cap_category'] = '🟢 LARGE CAP'
        elif metrics['market_cap'] >= 5000:
            metrics['cap_category'] = '🟡 MID CAP'
        else:
            metrics['cap_category'] = '🔴 SMALL CAP'

    return metrics

def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # 1. Profit Growth (15 Marks) [Target: > 12%]
    pg = m['profit_growth_ttm'] if m['profit_growth_ttm'] is not None else m['profit_growth_3y']
    if pg is not None:
        max_possible_score += 15
        if pg >= 12.0:
            earned_score += 15
            marks['profit_growth'] = True
        else:
            earned_score += 5 if pg >= 5.0 else 0
            marks['profit_growth'] = False
    else:
        marks['profit_growth'] = None

    # 2. ROCE (15 Marks) [Target: > 15%]
    if m['roce'] is not None:
        max_possible_score += 15
        if m['roce'] >= 15.0:
            earned_score += 15
            marks['roce'] = True
        else:
            earned_score += 6 if m['roce'] >= 10.0 else 0
            marks['roce'] = False
    else:
        marks['roce'] = None

    # 3. Debt to Equity (15 Marks) [Target: < 1.0]
    if m['debt_to_equity'] is not None:
        max_possible_score += 15
        if m['debt_to_equity'] < 1.0:
            earned_score += 15
            marks['debt_to_equity'] = True
        else:
            earned_score += 5 if m['debt_to_equity'] < 1.5 else 0
            marks['debt_to_equity'] = False
    else:
        marks['debt_to_equity'] = None

    # 4. ROE (12 Marks) [Target: > 15%]
    if m['roe'] is not None:
        max_possible_score += 12
        if m['roe'] >= 15.0:
            earned_score += 12
            marks['roe'] = True
        else:
            earned_score += 5 if m['roe'] >= 10.0 else 0
            marks['roe'] = False
    else:
        marks['roe'] = None

    # 5. Sales Growth (12 Marks) [Target: > 10%]
    sg = m['sales_growth_ttm'] if m['sales_growth_ttm'] is not None else m['sales_growth_3y']
    if sg is not None:
        max_possible_score += 12
        if sg >= 10.0:
            earned_score += 12
            marks['sales_growth'] = True
        else:
            earned_score += 4 if sg >= 5.0 else 0
            marks['sales_growth'] = False
    else:
        marks['sales_growth'] = None

    # 6. OPM (12 Marks) [Target: > 15%]
    if m['opm'] is not None:
        max_possible_score += 12
        if m['opm'] >= 15.0:
            earned_score += 12
            marks['opm'] = True
        else:
            earned_score += 4 if m['opm'] >= 8.0 else 0
            marks['opm'] = False
    else:
        marks['opm'] = None

    # 7. P/E (10 Marks) [Target: 10 to 45]
    if m['pe'] is not None:
        max_possible_score += 10
        if 10.0 <= m['pe'] <= 45.0:
            earned_score += 10
            marks['pe'] = True
        else:
            earned_score += 4 if m['pe'] <= 60.0 else 0
            marks['pe'] = False
    else:
        marks['pe'] = None

    # 8. Interest Coverage (9 Marks) [Target: > 3.5]
    ic = m['interest_coverage_ttm'] if m['interest_coverage_ttm'] is not None else m['interest_coverage_fy']
    if ic is not None:
        max_possible_score += 9
        if ic >= 3.5:
            earned_score += 9
            marks['interest_coverage'] = True
        else:
            marks['interest_coverage'] = False
    else:
        marks['interest_coverage'] = None

    # Strict 100M Final Score Calculation
    if max_possible_score >= 20:
        final_score = int(round((earned_score / max_possible_score) * 100))
        if final_score >= 80: quality = "🟢 A+ SUPER STRONG"
        elif final_score >= 65: quality = "🟢 A GOOD QUALITY"
        elif final_score >= 50: quality = "🟡 B AVERAGE"
        else: quality = "🔴 C WEAK"
    else:
        final_score = "N/A"
        quality = "⚪ DATA UNAVAILABLE"

    return final_score, quality, marks

def get_fundamental_analysis(symbol):
    try:
        metrics = get_screener_data(symbol)
        score, quality, marks = calculate_100M_score(metrics)
        return {
            "available": (score != "N/A"),
            "score": score,
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": []
        }
    except Exception as e:
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
      }
                  
