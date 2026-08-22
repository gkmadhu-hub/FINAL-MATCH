import requests
import re
from bs4 import BeautifulSoup

def get_screener_data(symbol):
    """
    Scrapes accurate fundamental data from Screener.in.
    Includes Sector, 52W High/Low, Compounded Growth,
    Interest Coverage, Balance Sheet Debt/Equity, and Shareholding (with Promoter Pledge).
    """
    clean_sym = symbol.replace('.NS', '').replace('.BO', '')
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    metrics = {
        'market_cap': 0.0,
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
        'promoter_pledge': 0.0,
        'fii_holding': None,
        'dii_holding': None,
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            url = f"https://www.screener.in/company/{clean_sym}/"
            response = requests.get(url, headers=headers, timeout=12)
            
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Exact Sector / Industry
            try:
                peers_section = soup.find('section', {'id': 'peers'})
                if peers_section:
                    compare_links = peers_section.find_all('a', href=re.compile(r'/company/compare/'))
                    if compare_links:
                        metrics['sector'] = compare_links[-1].get_text(strip=True)
                
                if metrics['sector'] == 'Diversified':
                    sub_title = soup.find('p', class_='sub')
                    if sub_title:
                        for a in sub_title.find_all('a'):
                            txt = a.get_text(strip=True)
                            if txt and not txt.startswith(('http', 'www', 'Privacy', 'Terms')):
                                metrics['sector'] = txt
                                break
            except Exception:
                metrics['sector'] = 'Diversified'

            # 2. Top Overview Ratios
            top_ratios = soup.find('ul', {'id': 'top-ratios'})
            if top_ratios:
                for li in top_ratios.find_all('li'):
                    name_elem = li.find('span', {'class': 'name'})
                    val_elem = li.find('span', {'class': 'number'})
                    if name_elem and val_elem:
                        name = name_elem.text.strip().lower()
                        val_str = val_elem.text.strip().replace(',', '').replace('%', '')
                        try:
                            val = float(val_str)
                            if 'market cap' in name:
                                metrics['market_cap'] = round(val, 1)
                                if val >= 20000:
                                    metrics['cap_category'] = '🟢 LARGE CAP'
                                elif val >= 5000:
                                    metrics['cap_category'] = '🟡 MID CAP'
                                elif val >= 1000:
                                    metrics['cap_category'] = '🟣 SMALL CAP'
                                else:
                                    metrics['cap_category'] = '⚪ MICRO CAP'

                            elif 'high / low' in name or 'high' in name:
                                numbers = li.find_all('span', {'class': 'number'})
                                if len(numbers) >= 2:
                                    metrics['high_52w'] = float(numbers[0].text.strip().replace(',', ''))
                                    metrics['low_52w'] = float(numbers[1].text.strip().replace(',', ''))

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
                        except Exception:
                            pass

            # 3. Compounded Growth & Stock Price CAGR Tables
            ranges_tables = soup.find_all('table', {'class': re.compile(r'ranges-table')})
            for table in ranges_tables:
                th = table.find('th')
                table_name = th.text.strip().lower() if th else ""
                
                rows = table.find_all('tr')
                for row in rows:
                    tds = row.find_all('td')
                    if len(tds) >= 2:
                        duration = tds[0].text.strip().lower()
                        val_text = tds[1].text.strip().replace('%', '').replace(',', '')
                        try:
                            val = float(val_text)
                            if '3 years' in duration or '3 yrs' in duration or '3 yr' in duration:
                                if 'sales' in table_name:
                                    metrics['sales_growth_3y'] = val
                                elif 'profit' in table_name:
                                    metrics['profit_growth_3y'] = val
                                elif 'price' in table_name or 'cagr' in table_name:
                                    metrics['price_cagr_3y'] = val
                            elif '1 year' in duration or '1 yr' in duration:
                                if 'price' in table_name or 'cagr' in table_name:
                                    metrics['price_cagr_1y'] = val
                            elif 'ttm' in duration:
                                if 'sales' in table_name and metrics['sales_growth_ttm'] is None:
                                    metrics['sales_growth_ttm'] = val
                                elif 'profit' in table_name and metrics['profit_growth_ttm'] is None:
                                    metrics['profit_growth_ttm'] = val
                        except Exception:
                            pass

            # 4. P&L Extraction: OPM % and Exact Interest Coverage FY
            pnl_section = soup.find('section', {'id': 'profit-loss'})
            if pnl_section:
                table = pnl_section.find('table', {'class': 'data-table'})
                if table:
                    op_profit_fy, interest_fy = None, None
                    op_profit_ttm, interest_ttm = None, None
                    
                    for tr in table.find_all('tr'):
                        row_txt = tr.text.lower()
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            try:
                                val_fy_str = tds[-2].text.strip().replace('%', '').replace(',', '')
                                val_fy = float(val_fy_str) if val_fy_str else 0.0
                                val_ttm_str = tds[-1].text.strip().replace('%', '').replace(',', '')
                                val_ttm = float(val_ttm_str) if val_ttm_str else 0.0
                                
                                if 'opm %' in row_txt or 'opm' in row_txt:
                                    if metrics['opm'] is None:
                                        metrics['opm'] = val_ttm if val_ttm != 0 else val_fy
                                elif 'operating profit' in row_txt and op_profit_fy is None:
                                    op_profit_fy = val_fy
                                    op_profit_ttm = val_ttm
                                elif 'interest' in row_txt and interest_fy is None:
                                    interest_fy = val_fy
                                    interest_ttm = val_ttm
                            except Exception:
                                pass
                    
                    if op_profit_fy is not None and interest_fy is not None:
                        if interest_fy <= 0:
                            metrics['interest_coverage_fy'] = 50.0
                        else:
                            metrics['interest_coverage_fy'] = round(op_profit_fy / interest_fy, 1)

                    if metrics['interest_coverage_ttm'] is None and op_profit_ttm is not None and interest_ttm is not None:
                        if interest_ttm <= 0:
                            metrics['interest_coverage_ttm'] = 50.0
                        else:
                            metrics['interest_coverage_ttm'] = round(op_profit_ttm / interest_ttm, 2)

            # 5. Debt to Equity Fallback from Balance Sheet
            if metrics['debt_to_equity'] is None:
                bs_section = soup.find('section', {'id': 'balance-sheet'})
                if bs_section:
                    table = bs_section.find('table', {'class': 'data-table'})
                    if table:
                        equity_val, reserves_val, borrowings_val = 0.0, 0.0, 0.0
                        found_equity, found_borrowing = False, False
                        for tr in table.find_all('tr'):
                            row_txt = tr.text.lower()
                            tds = tr.find_all('td')
                            if tds:
                                try:
                                    last_num_str = tds[-1].text.strip().replace(',', '')
                                    last_num = float(last_num_str) if last_num_str else 0.0
                                    if 'equity capital' in row_txt or 'share capital' in row_txt:
                                        equity_val = last_num
                                        found_equity = True
                                    elif 'reserves' in row_txt:
                                        reserves_val = last_num
                                    elif 'borrowings' in row_txt:
                                        borrowings_val = last_num
                                        found_borrowing = True
                                except Exception:
                                    pass
                        
                        total_equity = equity_val + reserves_val
                        if total_equity > 0 and found_borrowing:
                            metrics['debt_to_equity'] = round(borrowings_val / total_equity, 2)
                        elif found_equity and not found_borrowing:
                            metrics['debt_to_equity'] = 0.0

            # 6. Shareholding Pattern & Promoter Pledge
            shp_section = soup.find('section', {'id': 'shareholding'})
            if shp_section:
                tables = shp_section.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all(['td', 'th'])
                        if cols:
                            row_title = cols[0].text.strip().lower()
                            last_val = None
                            for col in reversed(cols[1:]):
                                val_str = col.text.strip().replace('%', '').replace(',', '')
                                try:
                                    last_val = float(val_str)
                                    break
                                except Exception:
                                    continue
                            
                            if last_val is not None:
                                if 'promoter' in row_title and 'pledge' not in row_title:
                                    metrics['promoter_holding'] = last_val
                                elif any(kw in row_title for kw in ['pledged', 'pledge', 'promoter pledge', 'encumbered']):
                                    metrics['promoter_pledge'] = last_val
                                elif 'fii' in row_title:
                                    metrics['fii_holding'] = last_val
                                elif 'dii' in row_title:
                                    metrics['dii_holding'] = last_val

    except Exception as e:
        print(f"Error scraping Screener.in for {clean_sym}: {e}")

    return metrics


def calculate_100M_score(m):
    """
    Calculates 100-Point Normalized Fundamental Health Score.
    """
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # 1. P/E (10 pts)
    if m['pe'] is not None:
        max_possible_score += 10
        if m['pe'] <= 25.0:
            earned_score += 10
            marks['pe'] = True
        elif m['pe'] <= 35.0:
            earned_score += 7
            marks['pe'] = True
        elif m['pe'] <= 50.0:
            earned_score += 4
            marks['pe'] = False
        else:
            marks['pe'] = False
    else:
        marks['pe'] = None

    # 2. ROCE (15 pts)
    if m['roce'] is not None:
        max_possible_score += 15
        if m['roce'] >= 20.0:
            earned_score += 15
            marks['roce'] = True
        elif m['roce'] >= 15.0:
            earned_score += 11
            marks['roce'] = True
        elif m['roce'] >= 10.0:
            earned_score += 6
            marks['roce'] = False
        else:
            marks['roce'] = False
    else:
        marks['roce'] = None

    # 3. ROE (15 pts)
    if m['roe'] is not None:
        max_possible_score += 15
        if m['roe'] >= 20.0:
            earned_score += 15
            marks['roe'] = True
        elif m['roe'] >= 15.0:
            earned_score += 11
            marks['roe'] = True
        elif m['roe'] >= 10.0:
            earned_score += 6
            marks['roe'] = False
        else:
            marks['roe'] = False
    else:
        marks['roe'] = None

    # 4. Debt to Equity (15 pts)
    if m['debt_to_equity'] is not None:
        max_possible_score += 15
        if m['debt_to_equity'] <= 0.30:
            earned_score += 15
            marks['debt_to_equity'] = True
        elif m['debt_to_equity'] <= 0.50:
            earned_score += 11
            marks['debt_to_equity'] = True
        elif m['debt_to_equity'] <= 1.00:
            earned_score += 5
            marks['debt_to_equity'] = False
        else:
            marks['debt_to_equity'] = False
    else:
        marks['debt_to_equity'] = None

    # 5. Sales Growth (12 pts)
    sg = m['sales_growth_3y'] if m['sales_growth_3y'] is not None else m['sales_growth_ttm']
    if sg is not None:
        max_possible_score += 12
        if sg >= 15.0:
            earned_score += 12
            marks['sales_growth'] = True
        elif sg >= 10.0:
            earned_score += 8
            marks['sales_growth'] = True
        elif sg >= 5.0:
            earned_score += 4
            marks['sales_growth'] = False
        else:
            marks['sales_growth'] = False
    else:
        marks['sales_growth'] = None

    # 6. Profit Growth (15 pts)
    pg = m['profit_growth_3y'] if m['profit_growth_3y'] is not None else m['profit_growth_ttm']
    if pg is not None:
        max_possible_score += 15
        if pg >= 15.0:
            earned_score += 15
            marks['profit_growth'] = True
        elif pg >= 10.0:
            earned_score += 11
            marks['profit_growth'] = True
        elif pg >= 5.0:
            earned_score += 5
            marks['profit_growth'] = False
        else:
            marks['profit_growth'] = False
    else:
        marks['profit_growth'] = None

    # 7. OPM % (10 pts)
    if m['opm'] is not None:
        max_possible_score += 10
        if m['opm'] >= 20.0:
            earned_score += 10
            marks['opm'] = True
        elif m['opm'] >= 15.0:
            earned_score += 7
            marks['opm'] = True
        elif m['opm'] >= 10.0:
            earned_score += 4
            marks['opm'] = False
        else:
            marks['opm'] = False
    else:
        marks['opm'] = None

    # 8. Interest Coverage (8 pts)
    ic = m['interest_coverage_ttm'] if m['interest_coverage_ttm'] is not None else m['interest_coverage_fy']
    if ic is not None:
        max_possible_score += 8
        if ic >= 4.0:
            earned_score += 8
            marks['interest_coverage'] = True
        elif ic >= 2.5:
            earned_score += 5
            marks['interest_coverage'] = True
        elif ic >= 1.5:
            earned_score += 2
            marks['interest_coverage'] = False
        else:
            marks['interest_coverage'] = False
    else:
        marks['interest_coverage'] = None

    # Normalization
    if max_possible_score > 0:
        final_score = int(round((earned_score / max_possible_score) * 100))
    else:
        final_score = 50

    # Quality Grade
    if final_score >= 80:
        quality = "🟢 A+ SUPER STRONG"
    elif final_score >= 65:
        quality = "🟢 A GOOD QUALITY"
    elif final_score >= 50:
        quality = "🟡 B AVERAGE"
    else:
        quality = "🔴 C WEAK"

    return final_score, quality, marks


def get_fundamental_analysis(symbol):
    """
    Main entry point for fundamental analysis.
    Returns calculated score, grade, marks, and complete raw metrics.
    """
    try:
        metrics = get_screener_data(symbol)
        
        # Hard Rejections
        rejections = []
        if metrics['market_cap'] > 0 and metrics['market_cap'] < 500:
            rejections.append(f"Market Cap < ₹500 Cr (₹{metrics['market_cap']}Cr)")
        if metrics['debt_to_equity'] is not None and metrics['debt_to_equity'] > 2.0:
            rejections.append(f"High Debt ({metrics['debt_to_equity']})")
        if metrics['promoter_pledge'] is not None and metrics['promoter_pledge'] > 15.0:
            rejections.append(f"High Pledge ({metrics['promoter_pledge']}%)")

        score, quality, marks = calculate_100M_score(metrics)

        return {
            "available": True,
            "score": score,
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": rejections
        }
    except Exception as e:
        print(f"Error in fundamental analysis for {symbol}: {e}")
        return {
            "available": False,
            "score": 50,
            "quality": "🟡 B AVERAGE",
            "marks": {},
            "metrics": {},
            "rejections": []
  }
              
