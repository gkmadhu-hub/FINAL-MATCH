import os
import re
import requests
from bs4 import BeautifulSoup

# Screener Credentials
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
    """Screener.in ನ ಲಾಗಿನ್ ಸೆಷನ್ ನಿರ್ವಹಣೆ."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    
    try:
        login_url = "https://www.screener.in/login/"
        res = session.get(login_url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        csrf_token = csrf_input['value'] if csrf_input else ""
        
        login_payload = {
            'username': SCREENER_USER,
            'password': SCREENER_PASS,
            'csrfmiddlewaretoken': csrf_token,
            'next': '/'
        }
        
        headers = {
            'Referer': login_url,
            'X-CSRFToken': csrf_token,
            'Origin': 'https://www.screener.in'
        }
        
        session.post(login_url, data=login_payload, headers=headers, timeout=10)
        return session
    except Exception as e:
        print(f"⚠️ Login Error: {e}")
        return session

screener_session = get_screener_session()

def get_screener_data(symbol):
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]
    
    metrics = {
        'market_cap': None,
        'cap_category': '🟢 LARGE CAP',
        'sector': 'Diversified',
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

    for url in urls:
        try:
            res = screener_session.get(url, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, 'html.parser')
                
                # 1. Direct Screener Top Ratios Card Scraper (Exact Screen Data)
                top_ratios = soup.find('ul', {'id': 'top-ratios'}) or soup.find('ul', {'class': lambda x: x and 'top-ratios' in x})
                if top_ratios:
                    for li in top_ratios.find_all('li'):
                        name_elem = li.find(['span', 'div'], {'class': lambda x: x and ('name' in x or 'title' in x)})
                        val_elem = li.find(['span', 'div'], {'class': lambda x: x and ('number' in x or 'value' in x or 'nowrap' in x)})
                        
                        if name_elem and val_elem:
                            name = name_elem.text.strip().lower()
                            val = clean_val(val_elem.text)
                            
                            if val is not None:
                                if 'market cap' in name: metrics['market_cap'] = round(val, 1)
                                elif 'stock p/e' in name or name == 'p/e': metrics['pe'] = val
                                elif 'roce' in name: metrics['roce'] = val
                                elif 'roe' in name or 'return on equity' in name: metrics['roe'] = val
                                elif 'debt to equity' in name: metrics['debt_to_equity'] = val
                                elif 'sales growth 3years' in name or 'sales var 3yrs' in name: metrics['sales_growth_3y'] = val
                                elif 'sales growth' in name: metrics['sales_growth_ttm'] = val
                                elif 'profit var 3yrs' in name or 'profit growth 3years' in name: metrics['profit_growth_3y'] = val
                                elif 'profit growth' in name: metrics['profit_growth_ttm'] = val
                                elif 'opm' in name: metrics['opm'] = val
                                elif any(k in name for k in ['int coverage', 'interest coverage']):
                                    metrics['interest_coverage_ttm'] = val
                                    metrics['interest_coverage_fy'] = val
                                elif 'piotroski' in name: metrics['piotroski'] = int(round(val))
                                elif any(k in name for k in ['pledged', 'pledge']): 
                                    metrics['pledged_percentage'] = val
                                elif 'promoter holding' in name: metrics['promoter_holding'] = val
                                elif 'fii holding' in name: metrics['fii_holding'] = val
                                elif 'dii holding' in name: metrics['dii_holding'] = val

                # 2. Growth & CAGR Tables
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
                                elif '1 year' in dur or '1 yr' in dur:
                                    if 'price' in tname or 'cagr' in tname: metrics['price_cagr_1y'] = v

                # 3. Shareholding Pattern
                shp = soup.find('section', {'id': 'shareholding'})
                if shp:
                    for tr in shp.find_all('tr'):
                        row_txt = tr.get_text(separator=" ", strip=True).lower()
                        tds = tr.find_all(['td', 'th', 'span'])
                        nums = [clean_val(td.get_text(strip=True)) for td in tds if clean_val(td.get_text(strip=True)) is not None]
                        if nums:
                            if any(k in row_txt for k in ['pledged', 'pledge', 'encumbered']) and metrics['pledged_percentage'] is None: 
                                metrics['pledged_percentage'] = nums[-1]
                            elif 'promoter' in row_txt and metrics['promoter_holding'] is None: 
                                metrics['promoter_holding'] = nums[-1]
                            elif 'fii' in row_txt and metrics['fii_holding'] is None: 
                                metrics['fii_holding'] = nums[-1]
                            elif 'dii' in row_txt and metrics['dii_holding'] is None: 
                                metrics['dii_holding'] = nums[-1]

                if metrics['market_cap'] is not None or metrics['pe'] is not None:
                    break
        except Exception:
            pass

    return metrics

def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # 1. Profit Growth (15 pts)
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

    # 2. ROCE (15 pts)
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

    # 3. Debt to Equity (15 pts)
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

    # 4. ROE (12 pts)
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

    # 5. Sales Growth (12 pts)
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

    # 6. OPM (12 pts)
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

    # 7. P/E (10 pts)
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

    # 8. Interest Coverage (9 pts)
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

    # Pledged Percentage Check
    if m['pledged_percentage'] is not None:
        marks['promoter_pledge'] = (m['pledged_percentage'] <= 5.0)
    else:
        marks['promoter_pledge'] = None

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
        
