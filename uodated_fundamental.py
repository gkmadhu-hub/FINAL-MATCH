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
    
    try:
        login_url = "https://www.screener.in/login/"
        res = session.get(login_url, timeout=12)
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
            session.post(login_url, data=payload, headers=headers, timeout=12)
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
            res = screener_session.get(url, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, 'html.parser')

                # 1. Sector & Industry
                peers_sec = soup.find('section', {'id': 'peers'})
                if peers_sec:
                    p_links = peers_sec.find_all('a', href=re.compile(r'/market/'))
                    if p_links:
                        metrics['sector'] = p_links[-1].text.strip()
                        if len(p_links) > 1:
                            metrics['industry'] = p_links[0].text.strip()

                # 2. Universal Top-Ratios Box Parser (Supports Default & Custom Ratios)
                for li in soup.find_all('li', class_=re.compile(r'flex-space-between|flex')):
                    name_span = li.find('span', class_='name')
                    val_span = li.find('span', class_=re.compile(r'value|nowrap|number'))
                    
                    if name_span and val_span:
                        k = name_span.get_text(strip=True).lower()
                        v = clean_val(val_span.get_text(strip=True))
                        
                        if 'market cap' in k and metrics['market_cap'] is None: metrics['market_cap'] = v
                        elif ('stock p/e' in k or k == 'p/e') and metrics['pe'] is None: metrics['pe'] = v
                        elif 'roce' in k and metrics['roce'] is None: metrics['roce'] = v
                        elif 'roe' in k and metrics['roe'] is None: metrics['roe'] = v
                        elif 'debt to equity' in k and metrics['debt_to_equity'] is None: metrics['debt_to_equity'] = v
                        elif 'opm' in k and metrics['opm'] is None: metrics['opm'] = v
                        elif 'pledged' in k and metrics['pledged_percentage'] is None: metrics['pledged_percentage'] = v
                        elif 'piotroski' in k and metrics['piotroski'] is None: metrics['piotroski'] = int(v) if v is not None else None
                        elif ('int coverage' in k or 'interest coverage' in k) and metrics['interest_coverage_ttm'] is None:
                            metrics['interest_coverage_ttm'] = v
                            metrics['interest_coverage_fy'] = v

                # 3. Growth & CAGR Tables
                for t in soup.find_all('table', class_=re.compile(r'ranges-table')):
                    th = t.find('th')
                    tname = th.text.strip().lower() if th else ""
                    for r in t.find_all('tr'):
                        tds = r.find_all('td')
                        if len(tds) >= 2:
                            dur = tds[0].text.strip().lower()
                            val = clean_val(tds[1].text)
                            if val is not None:
                                if '3 years' in dur or '3 yrs' in dur:
                                    if 'sales' in tname and metrics['sales_growth_3y'] is None: metrics['sales_growth_3y'] = val
                                    elif 'profit' in tname and metrics['profit_growth_3y'] is None: metrics['profit_growth_3y'] = val
                                    elif 'price' in tname or 'cagr' in tname: metrics['price_cagr_3y'] = val
                                elif 'ttm' in dur or '12m' in dur:
                                    if 'sales' in tname and metrics['sales_growth_ttm'] is None: metrics['sales_growth_ttm'] = val
                                    elif 'profit' in tname and metrics['profit_growth_ttm'] is None: metrics['profit_growth_ttm'] = val
                                elif '1 year' in dur or '1 yr' in dur:
                                    if 'price' in tname or 'cagr' in tname: metrics['price_cagr_1y'] = val

                # 4. P&L & Quarters Backup for OPM & Interest Coverage
                op_sales, op_profit, int_val = None, None, None
                for sec_id in ['quarters', 'profit-loss']:
                    sec = soup.find('section', {'id': sec_id})
                    if sec:
                        for tr in sec.find_all('tr'):
                            row_txt = tr.get_text(separator=' ', strip=True).lower()
                            vals = [clean_val(td.text) for td in tr.find_all('td') if clean_val(td.text) is not None]
                            if vals:
                                if 'sales' in row_txt and op_sales is None: op_sales = vals[-1]
                                elif 'operating profit' in row_txt and op_profit is None: op_profit = vals[-1]
                                elif 'opm' in row_txt and metrics['opm'] is None: metrics['opm'] = vals[-1]
                                elif 'interest' in row_txt and int_val is None: int_val = vals[-1]

                if metrics['opm'] is None and op_sales and op_profit and op_sales > 0:
                    metrics['opm'] = round((op_profit / op_sales) * 100, 1)

                if metrics['interest_coverage_ttm'] is None and op_profit and int_val and int_val > 0:
                    calc_ic = round(op_profit / int_val, 2)
                    metrics['interest_coverage_ttm'] = calc_ic
                    metrics['interest_coverage_fy'] = calc_ic

                # 5. Shareholding Pattern Backup for Promoter, FII, DII, Pledged
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

                # 6. Default Fallbacks for Debt-Free / Clean Companies
                if metrics['pledged_percentage'] is None: metrics['pledged_percentage'] = 0.0
                if metrics['debt_to_equity'] is None: metrics['debt_to_equity'] = 0.0

                if metrics['market_cap'] is not None:
                    break
        except Exception:
            pass

    # YFinance Fallback for Sector/Industry
    if metrics['sector'] == 'N/A' or metrics['industry'] == 'N/A':
        try:
            ticker = yf.Ticker(f"{clean_sym}.NS")
            info = ticker.info or {}
            if metrics['sector'] == 'N/A': metrics['sector'] = info.get('sector') or 'Diversified'
            if metrics['industry'] == 'N/A': metrics['industry'] = info.get('industry') or info.get('sector') or 'Diversified'
        except Exception:
            pass

    return metrics

def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # 1. Profit Growth (15 Marks)
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

    # 2. ROCE (15 Marks)
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

    # 3. Debt to Equity (15 Marks)
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

    # 4. ROE (12 Marks)
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

    # 5. Sales Growth (12 Marks)
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

    # 6. OPM (12 Marks)
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

    # 7. P/E (10 Marks)
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

    # 8. Interest Coverage (9 Marks)
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
    except Exception:
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
        }
        
