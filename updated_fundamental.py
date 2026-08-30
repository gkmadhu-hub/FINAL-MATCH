import requests
from bs4 import BeautifulSoup
import re

def get_screener_data(clean_sym):
    """
    Scrapes Screener.in consolidated financial ratios and key points
    to extract 100% original fundamental data for all parameters.
    """
    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    metrics = {
        'piotroski': 'N/A',
        'mcap': None,
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
        'pledged_percentage': 0.0,
        'promoter_holding': None,
        'fii_holding': None,
        'dii_holding': None,
        'price_cagr_1y': None,
        'price_cagr_3y': None,
        'sector': 'Diversified'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return metrics

        soup = BeautifulSoup(response.content, 'html.parser')

        # Scraping from top-ratios list items
        ratios_div = soup.find('div', {'id': 'top-ratios'})
        if ratios_div:
            items = ratios_div.find_all('li')
            for item in items:
                name_elem = item.find('span', {'class': 'name'})
                val_elem = item.find('span', {'class': 'value'})
                if name_elem and val_elem:
                    n_text = name_elem.text.strip().lower()
                    v_text = val_elem.text.strip().replace(',', '').replace('%', '').replace('₹', '').replace('Cr.', '').strip()

                    try:
                        v_float = float(v_text)
                    except ValueError:
                        v_float = v_text

                    if 'market capitalization' in n_text or n_text == 'market cap':
                        metrics['mcap'] = v_float
                    elif 'stock p/e' in n_text or n_text == 'p/e':
                        metrics['pe'] = v_float
                    elif 'roce' in n_text:
                        metrics['roce'] = v_float
                    elif 'roe' in n_text or 'return on equity' in n_text:
                        metrics['roe'] = v_float
                    elif 'debt to equity' in n_text:
                        metrics['debt_to_equity'] = v_float
                    elif 'pledged percentage' in n_text:
                        metrics['pledged_percentage'] = v_float
                    elif n_text == 'opm' or 'operating profit margin' in n_text:
                        metrics['opm'] = v_float
                    elif 'profit growth' in n_text and '3' not in n_text:
                        metrics['profit_growth_ttm'] = v_float
                    elif 'profit var 3yrs' in n_text or 'profit growth 3' in n_text:
                        metrics['profit_growth_3y'] = v_float
                    elif 'sales growth' in n_text and '3' not in n_text:
                        metrics['sales_growth_ttm'] = v_float
                    elif 'sales growth 3years' in n_text or 'sales growth 3' in n_text:
                        metrics['sales_growth_3y'] = v_float
                    elif 'int coverage' in n_text or 'interest coverage' in n_text:
                        metrics['interest_coverage_ttm'] = v_float
                        metrics['interest_coverage_fy'] = v_float
                    elif 'piotroski score' in n_text:
                        metrics['piotroski'] = v_float
                    elif 'promoter holding' in n_text:
                        metrics['promoter_holding'] = v_float
                    elif 'fii holding' in n_text:
                        metrics['fii_holding'] = v_float
                    elif 'dii holding' in n_text:
                        metrics['dii_holding'] = v_float

        # Backup robust text search for any missing fields
        for elem in soup.find_all(['li', 'tr']):
            text = elem.text.strip().lower()
            if metrics['mcap'] is None and ('market cap' in text or 'market capitalization' in text):
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    try: metrics['mcap'] = float(nums[-1])
                    except: pass
            if metrics['piotroski'] == 'N/A' and 'piotroski' in text:
                nums = re.findall(r'\b[0-9]\b', text)
                if nums:
                    metrics['piotroski'] = nums[0]

        return metrics

    except Exception as e:
        print(f"Screener scraping error for {clean_sym}: {e}")
        return metrics

def calculate_100M_score(metrics):
    """
    Calculates score, quality status, and individual marks based on original metrics.
    """
    marks = {}
    score = 50.0  # Base score

    pe = metrics.get('pe')
    if pe is not None and isinstance(pe, (int, float)):
        marks['pe'] = (10 <= pe <= 45)
        score += 8 if marks['pe'] else -4

    roce = metrics.get('roce')
    if roce is not None and isinstance(roce, (int, float)):
        marks['roce'] = (roce > 15)
        score += 8 if marks['roce'] else -4

    roe = metrics.get('roe')
    if roe is not None and isinstance(roe, (int, float)):
        marks['roe'] = (roe > 15)
        score += 8 if marks['roe'] else -4

    de = metrics.get('debt_to_equity')
    if de is not None and isinstance(de, (int, float)):
        marks['debt_to_equity'] = (de < 1.0)
        score += 8 if marks['debt_to_equity'] else -8

    sg = metrics.get('sales_growth_3y') or metrics.get('sales_growth_ttm')
    if sg is not None and isinstance(sg, (int, float)):
        marks['sales_growth'] = (sg > 10)
        score += 8 if marks['sales_growth'] else -4

    pg = metrics.get('profit_growth_3y') or metrics.get('profit_growth_ttm')
    if pg is not None and isinstance(pg, (int, float)):
        marks['profit_growth'] = (pg > 12)
        score += 8 if marks['profit_growth'] else -4

    opm = metrics.get('opm')
    if opm is not None and isinstance(opm, (int, float)):
        marks['opm'] = (opm > 15)
        score += 8 if marks['opm'] else -4

    ic = metrics.get('interest_coverage_ttm')
    if ic is not None and isinstance(ic, (int, float)):
        marks['interest_coverage'] = (ic > 3.5)
        score += 8 if marks['interest_coverage'] else -4

    pledge = metrics.get('pledged_percentage', 0.0)
    if pledge is not None and isinstance(pledge, (int, float)):
        marks['promoter_pledge'] = (pledge < 5.0)
        score += 10 if marks['promoter_pledge'] else -10

    score = max(0.0, min(100.0, score))

    if score >= 80:
        quality = "🟢 A+ SUPER STRONG"
    elif score >= 65:
        quality = "🟢 STRONG"
    elif score >= 50:
        quality = "🟡 MODERATE"
    else:
        quality = "🔴 WEAK"

    return score, quality, marks

def get_fundamental_analysis(symbol):
    """
    Main entry point for fundamental analysis. Returns dictionary with metrics, score, and rejections.
    """
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    try:
        metrics = get_screener_data(clean_sym)
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
        print(f"Fundamental analysis error for {clean_sym}: {e}")
        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
    }
                                
