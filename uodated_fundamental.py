import requests
from bs4 import BeautifulSoup
import re

def get_fundamental_analysis(symbol):
    """
    Scrapes Screener.in consolidated financial ratios for a given stock symbol.
    Ensures accurate mapping for Piotroski, OPM, Debt/Equity, and Pledged %.
    """
    clean_sym = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
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
            return {'metrics': metrics, 'score': 0, 'quality': '⚪ DATA UNAVAILABLE', 'marks': {}}

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract Ratios from Top Ratios Box / Table
        ratios_div = soup.find('div', {'id': 'top-ratios'})
        if ratios_div:
            items = ratios_div.find_all('li')
            for item in items:
                name_elem = item.find('span', {'class': 'name'})
                val_elem = item.find('span', {'class': 'value'})
                if name_elem and val_elem:
                    n_text = name_elem.text.strip().lower()
                    v_text = val_elem.text.strip().replace(',', '')

                    try:
                        v_float = float(v_text)
                    except ValueError:
                        v_float = v_text

                    if 'market capitalization' in n_text:
                        metrics['mcap'] = v_float
                    elif 'stock p/e' in n_text:
                        metrics['pe'] = v_float
                    elif 'roce' in n_text:
                        metrics['roce'] = v_float
                    elif 'roe' in n_text:
                        metrics['roe'] = v_float
                    elif 'debt to equity' in n_text:
                        metrics['debt_to_equity'] = v_float
                    elif 'pledged percentage' in n_text:
                        metrics['pledged_percentage'] = v_float
                    elif 'opm' in n_text or 'operating profit margin' in n_text:
                        metrics['opm'] = v_float

        # Extract Piotroski F-Score (if available in specific elements)
        for card in soup.find_all('div', {'class': 'flex-column'}):
            text = card.get_text()
            if 'piotroski' in text.lower():
                nums = re.findall(r'\b[0-9]\b', text)
                if nums:
                    metrics['piotroski'] = nums[0]

        # Calculate Marks & Total Score
        marks = {}
        score = 50.0  # Base score

        pe = metrics.get('pe')
        if pe is not None and isinstance(pe, (int, float)):
            marks['pe'] = (10 <= pe <= 45)
            score += 10 if marks['pe'] else -5

        roce = metrics.get('roce')
        if roce is not None and isinstance(roce, (int, float)):
            marks['roce'] = (roce > 15)
            score += 10 if marks['roce'] else -5

        roe = metrics.get('roe')
        if roe is not None and isinstance(roe, (int, float)):
            marks['roe'] = (roe > 15)
            score += 10 if marks['roe'] else -5

        de = metrics.get('debt_to_equity')
        if de is not None and isinstance(de, (int, float)):
            marks['debt_to_equity'] = (de < 1.0)
            score += 10 if marks['debt_to_equity'] else -10

        opm = metrics.get('opm')
        if opm is not None and isinstance(opm, (int, float)):
            marks['opm'] = (opm > 15)
            score += 10 if marks['opm'] else -5

        pledge = metrics.get('pledged_percentage', 0.0)
        if pledge is not None and isinstance(pledge, (int, float)):
            marks['promoter_pledge'] = (pledge < 5.0)  # 0% gets ✅
            score += 10 if marks['promoter_pledge'] else -15

        score = max(0.0, min(100.0, score))

        if score >= 80: quality = "🟢 A+ SUPER STRONG"
        elif score >= 65: quality = "🟢 STRONG"
        elif score >= 50: quality = "🟡 MODERATE"
        else: quality = "🔴 WEAK"

        return {'metrics': metrics, 'score': score, 'quality': quality, 'marks': marks}

    except Exception as e:
        print(f"Fundamental scraping error for {clean_sym}: {e}")
        return {'metrics': metrics, 'score': 0, 'quality': '⚪ DATA UNAVAILABLE', 'marks': {}}
                                               
