import requests
import re
import yfinance as yf
from bs4 import BeautifulSoup

def clean_val(val_str):
    if not val_str:
        return None
    try:
        clean = val_str.replace('%', '').replace(',', '').strip()
        return float(clean)
    except Exception:
        return None


def get_pledge_from_bse_trendlyne(symbol):
    """Tier 1 & 2: Fetch official promoter pledge from Trendlyne / BSE corporate endpoint"""
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    
    # 1. Trendlyne Corporate Shareholding API
    try:
        url = f"https://trendlyne.com/equity/shareholding/{clean_sym}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, 'html.parser')
            # Look for pledge percentages in table or data attributes
            for row in soup.find_all(['tr', 'div', 'p']):
                row_text = row.get_text(separator=" ", strip=True).lower()
                if 'pledge' in row_text or 'encumbered' in row_text:
                    nums = re.findall(r'(\d+\.?\d*)\s*%', row_text)
                    if nums:
                        val = float(nums[0])
                        if val <= 100.0:
                            return val
    except Exception:
        pass

    # 2. Yahoo Finance Insiders Data Check
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        info = ticker.info
        pledged_shares = info.get('sharesPledged', None)
        promoter_shares = info.get('heldPercentInsiders', None)
        if pledged_shares is not None and promoter_shares is not None and promoter_shares > 0:
            return round((pledged_shares / promoter_shares) * 100, 2)
        if 'pledgedPercentage' in info and info['pledgedPercentage'] is not None:
            return round(float(info['pledgedPercentage']), 2)
    except Exception:
        pass

    return None


def get_screener_data(symbol):
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
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
        'promoter_pledge': None,
        'fii_holding': None,
        'dii_holding': None,
    }
    
    session = requests.Session()
    
    for url in urls:
        try:
            response = session.get(url, headers=headers, timeout=12)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            top_ratios = soup.find('ul', {'id': 'top-ratios'})
            if not top_ratios:
                continue

            # 1. Sector
            try:
                peers = soup.find('section', {'id': 'peers'})
                if peers:
                    links = peers.find_all('a', href=re.compile(r'/company/compare/'))
                    if links:
                        metrics['sector'] = links[-1].get_text(strip=True)
                if metrics['sector'] == 'Diversified':
                    sub = soup.find('p', class_='sub')
                    if sub:
                        for a in sub.find_all('a'):
                            txt = a.get_text(strip=True)
                            if txt and not txt.startswith(('http', 'www', 'Privacy', 'Terms')):
                                metrics['sector'] = txt
                                break
            except Exception:
                pass

            # 2. Top Overview Ratios
            for li in top_ratios.find_all('li'):
                name_elem = li.find('span', {'class': 'name'})
                val_elem = li.find('span', {'class': 'number'})
                if name_elem and val_elem:
                    name = name_elem.text.strip().lower()
                    val = clean_val(val_elem.text)
                    if val is not None:
                        if 'market cap' in name:
                            metrics['market_cap'] = round(val, 1)
                        elif 'high / low' in name or 'high' in name:
                            nums = li.find_all('span', {'class': 'number'})
                            if len(nums) >= 2:
                                metrics['high_52w'] = clean_val(nums[0].text)
                                metrics['low_52w'] = clean_val(nums[1].text)
                        elif 'stock p/e' in name or name == 'p/e':
                            metrics['pe'] = val
                        elif 'roce' in name:
                            metrics['roce'] = val
                        elif 'roe' in name or 'return on equity' in name:
                            metrics['roe'] = val
                        elif 'debt to equity' in name:
                            metrics['debt_to_equity'] = val
                        elif 'sales growth' in name and '3' not in name and '5' not in name:
                            metrics['sales_growth_ttm'] = val
                        elif 'profit growth' in name and '3' not in name and '5' not in name:
                            metrics['profit_growth_ttm'] = val
                        elif 'int coverage' in name or 'interest coverage' in name:
                            metrics['interest_coverage_ttm'] = val
                        elif 'opm' in name:
                            metrics['opm'] = val
                        elif any(k in name for k in ['pledged', 'pledge', 'encumbered']):
                            metrics['promoter_pledge'] = val
                        elif 'promoter holding' in name and 'pledge' not in name:
                            metrics['promoter_holding'] = val
                        elif 'fii holding' in name:
                            metrics['fii_holding'] = val
                        elif 'dii holding' in name:
                            metrics['dii_holding'] = val

            # 3. Compounded Growth Tables (CAGR 1Y, 3Y)
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
                            if '3 years' in dur or '3 yrs' in dur or '3 yr' in dur:
                                if 'sales' in tname: metrics['sales_growth_3y'] = v
                                elif 'profit' in tname: metrics['profit_growth_3y'] = v
                                elif 'price' in tname or 'cagr' in tname: metrics['price_cagr_3y'] = v
                            elif '1 year' in dur or '1 yr' in dur:
                                if 'price' in tname or 'cagr' in tname: metrics['price_cagr_1y'] = v
                            elif 'ttm' in dur:
                                if 'sales' in tname and metrics['sales_growth_ttm'] is None:
                                    metrics['sales_growth_ttm'] = v
                                elif 'profit' in tname and metrics['profit_growth_ttm'] is None:
                                    metrics['profit_growth_ttm'] = v

            # 4. Profit & Loss / Quarterly Results Extraction (For Robust TTM)
            pnl = soup.find('section', {'id': 'profit-loss'})
            if pnl:
                table = pnl.find('table', {'class': 'data-table'})
                if table:
                    sales_ttm, sales_fy = None, None
                    net_profit_ttm, net_profit_fy = None, None
                    op_ttm, op_fy = None, None
                    int_ttm, int_fy = None, None
                    
                    for tr in table.find_all('tr'):
                        rtxt = tr.text.lower()
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            v_ttm = clean_val(tds[-1].text)
                            v_fy = clean_val(tds[-2].text)
                            if 'sales' in rtxt:
                                sales_ttm, sales_fy = v_ttm, v_fy
                            elif 'net profit' in rtxt:
                                net_profit_ttm, net_profit_fy = v_ttm, v_fy
                            elif 'opm %' in rtxt and metrics['opm'] is None:
                                metrics['opm'] = v_ttm if v_ttm is not None else v_fy
                            elif 'operating profit' in rtxt:
                                op_ttm, op_fy = v_ttm, v_fy
                            elif 'interest' in rtxt:
                                int_ttm, int_fy = v_ttm, v_fy

                    # Calculate TTM Sales & Profit Growth if missing
                    if metrics['sales_growth_ttm'] is None and sales_ttm is not None and sales_fy is not None and sales_fy > 0:
                        metrics['sales_growth_ttm'] = round(((sales_ttm - sales_fy) / sales_fy) * 100, 1)

                    if metrics['profit_growth_ttm'] is None and net_profit_ttm is not None and net_profit_fy is not None and net_profit_fy > 0:
                        metrics['profit_growth_ttm'] = round(((net_profit_ttm - net_profit_fy) / net_profit_fy) * 100, 1)

                    # Calculate Interest Coverage (TTM & FY)
                    if int_ttm is not None and int_ttm > 0 and op_ttm is not None:
                        metrics['interest_coverage_ttm'] = round(op_ttm / int_ttm, 1)
                    elif int_fy is not None and int_fy > 0 and op_fy is not None:
                        metrics['interest_coverage_fy'] = round(op_fy / int_fy, 1)

            # 5. Balance Sheet for Debt to Equity
            if metrics['debt_to_equity'] is None:
                bs = soup.find('section', {'id': 'balance-sheet'})
                if bs:
                    table = bs.find('table', {'class': 'data-table'})
                    if table:
                        eq, res, bor = 0.0, 0.0, 0.0
                        found_b = False
                        for tr in table.find_all('tr'):
                            txt = tr.text.lower()
                            tds = tr.find_all('td')
                            if tds:
                                n = clean_val(tds[-1].text)
                                if n is not None:
                                    if 'share capital' in txt or 'equity capital' in txt: eq = n
                                    elif 'reserves' in txt: res = n
                                    elif 'borrowings' in txt:
                                        bor = n
                                        found_b = True
                        if (eq + res) > 0 and found_b:
                            metrics['debt_to_equity'] = round(bor / (eq + res), 2)
                        elif eq > 0 and not found_b:
                            metrics['debt_to_equity'] = 0.0

            # 6. Shareholding Pattern
            shp = soup.find('section', {'id': 'shareholding'})
            if shp:
                for table in shp.find_all('table'):
                    for row in table.find_all('tr'):
                        cols = row.find_all(['td', 'th', 'button', 'span'])
                        if cols:
                            row_title = cols[0].text.strip().lower()
                            last_val = None
                            for col in reversed(cols[1:]):
                                val_c = clean_val(col.text)
                                if val_c is not None:
                                    last_val = val_c
                                    break
                            
                            if last_val is not None:
                                if any(kw in row_title for kw in ['pledged', 'pledge', 'encumbered']):
                                    metrics['promoter_pledge'] = last_val
                                elif 'promoter' in row_title and metrics['promoter_holding'] is None:
                                    metrics['promoter_holding'] = last_val
                                elif 'fii' in row_title and metrics['fii_holding'] is None:
                                    metrics['fii_holding'] = last_val
                                elif 'dii' in row_title and metrics['dii_holding'] is None:
                                    metrics['dii_holding'] = last_val

            # 7. Fallback for Promoter Pledge if still missing
            if metrics['promoter_pledge'] is None:
                metrics['promoter_pledge'] = get_pledge_from_bse_trendlyne(symbol)

            if metrics['pe'] is not None or metrics['market_cap'] is not None:
                break
        except Exception:
            continue

    return metrics


def calculate_100M_score(m):
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # P/E (10 pts)
    if m['pe'] is not None:
        max_possible_score += 10
        if 10.0 <= m['pe'] <= 45.0:
            earned_score += 10
            marks['pe'] = True
        else:
            earned_score += 4 if m['pe'] <= 50.0 else 0
            marks['pe'] = False
    else:
        marks['pe'] = None

    # ROCE (15 pts)
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

    # ROE (15 pts)
    if m['roe'] is not None:
        max_possible_score += 15
        if m['roe'] >= 15.0:
            earned_score += 15
            marks['roe'] = True
        else:
            earned_score += 6 if m['roe'] >= 10.0 else 0
            marks['roe'] = False
    else:
        marks['roe'] = None

    # Debt to Equity (15 pts)
    if m['debt_to_equity'] is not None:
        max_possible_score += 15
        if m['debt_to_equity'] < 1.0:
            earned_score += 15
            marks['debt_to_equity'] = True
        else:
            marks['debt_to_equity'] = False
    else:
        marks['debt_to_equity'] = None

    # Sales Growth (12 pts)
    sg = m['sales_growth_ttm'] if m['sales_growth_ttm'] is not None else m['sales_growth_3y']
    if sg is not None:
        max_possible_score += 12
        if sg >= 10.0:
            earned_score += 12
            marks['sales_growth'] = True
        else:
            marks['sales_growth'] = False
    else:
        marks['sales_growth'] = None

    # Profit Growth (15 pts)
    pg = m['profit_growth_ttm'] if m['profit_growth_ttm'] is not None else m['profit_growth_3y']
    if pg is not None:
        max_possible_score += 15
        if pg >= 12.0:
            earned_score += 15
            marks['profit_growth'] = True
        else:
            marks['profit_growth'] = False
    else:
        marks['profit_growth'] = None

    # OPM (10 pts)
    if m['opm'] is not None:
        max_possible_score += 10
        if m['opm'] >= 15.0:
            earned_score += 10
            marks['opm'] = True
        else:
            marks['opm'] = False
    else:
        marks['opm'] = None

    # Interest Coverage (8 pts)
    ic = m['interest_coverage_ttm'] if m['interest_coverage_ttm'] is not None else m['interest_coverage_fy']
    if ic is not None:
        max_possible_score += 8
        if ic >= 3.5:
            earned_score += 8
            marks['interest_coverage'] = True
        else:
            marks['interest_coverage'] = False
    else:
        marks['interest_coverage'] = None

    # Promoter Pledge Check
    if m['promoter_pledge'] is not None:
        marks['promoter_pledge'] = (m['promoter_pledge'] <= 5.0)
    else:
        marks['promoter_pledge'] = None

    # Final Evaluation
    if max_possible_score >= 30:
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
        
