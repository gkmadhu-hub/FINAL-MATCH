import requests
import re
from bs4 import BeautifulSoup

def get_screener_data(symbol):
    """
    Scrapes accurate fundamental data from Screener.in with dual fallback (Consolidated -> Standalone)
    and robust deep-search for Promoter Pledge & Shareholding.
    """
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    urls = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=12)
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

            # 2. Top Ratios
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
                        elif 'high / low' in name or 'high' in name:
                            nums = li.find_all('span', {'class': 'number'})
                            if len(nums) >= 2:
                                metrics['high_52w'] = float(nums[0].text.strip().replace(',', ''))
                                metrics['low_52w'] = float(nums[1].text.strip().replace(',', ''))
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
                    except Exception:
                        pass

            # 3. Compounded Growth Tables
            ranges = soup.find_all('table', {'class': re.compile(r'ranges-table')})
            for t in ranges:
                th = t.find('th')
                tname = th.text.strip().lower() if th else ""
                for r in t.find_all('tr'):
                    tds = r.find_all('td')
                    if len(tds) >= 2:
                        dur = tds[0].text.strip().lower()
                        vstr = tds[1].text.strip().replace('%', '').replace(',', '')
                        try:
                            v = float(vstr)
                            if '3 years' in dur or '3 yrs' in dur or '3 yr' in dur:
                                if 'sales' in tname: metrics['sales_growth_3y'] = v
                                elif 'profit' in tname: metrics['profit_growth_3y'] = v
                                elif 'price' in tname or 'cagr' in tname: metrics['price_cagr_3y'] = v
                            elif '1 year' in dur or '1 yr' in dur:
                                if 'price' in tname or 'cagr' in tname: metrics['price_cagr_1y'] = v
                        except Exception:
                            pass

            # 4. P&L Extraction: OPM & Interest Coverage
            pnl = soup.find('section', {'id': 'profit-loss'})
            if pnl:
                table = pnl.find('table', {'class': 'data-table'})
                if table:
                    op_fy, int_fy = None, None
                    for tr in table.find_all('tr'):
                        rtxt = tr.text.lower()
                        tds = tr.find_all('td')
                        if len(tds) >= 2:
                            try:
                                v_ttm = float(tds[-1].text.strip().replace('%', '').replace(',', ''))
                                v_fy = float(tds[-2].text.strip().replace('%', '').replace(',', ''))
                                if 'opm %' in rtxt and metrics['opm'] is None:
                                    metrics['opm'] = v_ttm if v_ttm != 0 else v_fy
                                elif 'operating profit' in rtxt and op_fy is None:
                                    op_fy = v_fy
                                elif 'interest' in rtxt and int_fy is None:
                                    int_fy = v_fy
                            except Exception:
                                pass
                    if op_fy is not None and int_fy is not None:
                        metrics['interest_coverage_fy'] = round(op_fy / int_fy, 1) if int_fy > 0 else 50.0

            # 5. Balance Sheet Fallback for Debt to Equity
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
                                try:
                                    n = float(tds[-1].text.strip().replace(',', ''))
                                    if 'share capital' in txt or 'equity capital' in txt: eq = n
                                    elif 'reserves' in txt: res = n
                                    elif 'borrowings' in txt:
                                        bor = n
                                        found_b = True
                                except Exception:
                                    pass
                        if (eq + res) > 0 and found_b:
                            metrics['debt_to_equity'] = round(bor / (eq + res), 2)
                        elif eq > 0 and not found_b:
                            metrics['debt_to_equity'] = 0.0

            # 6. Deep Shareholding & Promoter Pledge Search
            shp = soup.find('section', {'id': 'shareholding'})
            if shp:
                for table in shp.find_all('table'):
                    for row in table.find_all('tr'):
                        cols = row.find_all(['td', 'th', 'button', 'span'])
                        if cols:
                            row_title = cols[0].text.strip().lower()
                            
                            # Deep scan across all columns from latest to oldest
                            last_val = None
                            for col in reversed(cols[1:]):
                                text_clean = col.text.strip().replace('%', '').replace(',', '')
                                try:
                                    last_val = float(text_clean)
                                    break
                                except Exception:
                                    continue
                            
                            if last_val is not None:
                                if any(kw in row_title for kw in ['pledged', 'pledge', 'encumbered']):
                                    metrics['promoter_pledge'] = last_val
                                elif 'promoter' in row_title and metrics['promoter_holding'] is None:
                                    metrics['promoter_holding'] = last_val
                                elif 'fii' in row_title and metrics['fii_holding'] is None:
                                    metrics['fii_holding'] = last_val
                                elif 'dii' in row_title and metrics['dii_holding'] is None:
                                    metrics['dii_holding'] = last_val

            # Break loop if valid data acquired
            if metrics['pe'] is not None or metrics['market_cap'] is not None:
                break
        except Exception:
            continue

    # Fallback to zero pledge only if promoter holding is confirmed present and no pledge reported
    if metrics['promoter_pledge'] is None and metrics['promoter_holding'] is not None:
        metrics['promoter_pledge'] = 0.0

    return metrics


def calculate_100M_score(m):
    """
    Calculates 100-Point Fundamental Score & marks. Missing metrics get None (renders as ⚪).
    """
    earned_score = 0.0
    max_possible_score = 0.0
    marks = {}

    # 1. P/E (10 pts)
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

    # 3. ROE (15 pts)
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

    # 4. Debt to Equity (15 pts)
    if m['debt_to_equity'] is not None:
        max_possible_score += 15
        if m['debt_to_equity'] < 1.0:
            earned_score += 15
            marks['debt_to_equity'] = True
        else:
            marks['debt_to_equity'] = False
    else:
        marks['debt_to_equity'] = None

    # 5. Sales Growth (12 pts)
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

    # 6. Profit Growth (15 pts)
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

    # 7. OPM (10 pts)
    if m['opm'] is not None:
        max_possible_score += 10
        if m['opm'] >= 15.0:
            earned_score += 10
            marks['opm'] = True
        else:
            marks['opm'] = False
    else:
        marks['opm'] = None

    # 8. Interest Coverage (8 pts)
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

    # 9. Promoter Pledge (<= 5.0% target)
    if m['promoter_pledge'] is not None:
        marks['promoter_pledge'] = (m['promoter_pledge'] <= 5.0)
    else:
        marks['promoter_pledge'] = None

    # Final Score Calculation (Requires at least 30 max points to evaluate)
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
    """
    Main entry point for fundamental analysis.
    """
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
        print(f"Fundamental extraction note for {symbol}: {e}")
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
    }
    
