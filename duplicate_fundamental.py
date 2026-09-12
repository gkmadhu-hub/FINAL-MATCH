import requests
from bs4 import BeautifulSoup
import re

def get_screener_ratios(ticker):
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://ticker.finology.in/company/{clean_sym}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return {}

    soup = BeautifulSoup(resp.content, "html.parser")
    data = {
        "current_price": "N/A", "market_cap": "N/A", "pe": "N/A",
        "roce": "N/A", "roe": "N/A", "debt_equity": "N/A",
        "sales_growth": "N/A", "sales_growth_3yr": "N/A",
        "profit_growth": "N/A", "profit_var_3yr": "N/A",
        "opm": "N/A", "int_coverage": "N/A", "piotroski": "N/A",
        "pledged": "0.00", "promoter": "N/A", "fii": "N/A",
        "dii": "N/A", "cagr_1y": "N/A", "cagr_3y": "N/A",
        "sector": "Commodities"
    }

    # Extract price
    price_elem = soup.find("span", class_="Number") or soup.find("span", class_="mainprice")
    if price_elem:
        data["current_price"] = price_elem.get_text(strip=True).replace(",", "")

    # Extract sector
    sec_elem = soup.find("a", href=re.compile(r"/sector/"))
    if sec_elem:
        data["sector"] = sec_elem.get_text(strip=True)

    # Essentials Cards
    for card in soup.find_all("div", class_=["cardscreen", "product-item"]):
        t = card.get_text(separator=" ").strip()
        lines = [line.strip() for line in t.split("\n") if line.strip()]
        for i, l in enumerate(lines):
            l_low = l.lower()
            if "market cap" in l_low and i + 1 < len(lines):
                m = re.findall(r"[\d,.]+", lines[i+1].replace(",", ""))
                if m: data['market_cap'] = str(int(float(m[0])))
            elif "p/e" in l_low and i + 1 < len(lines):
                m = re.findall(r"[\d.]+", lines[i+1])
                if m: data['pe'] = m[0]
            elif "roce" in l_low and i + 1 < len(lines):
                m = re.findall(r"[\d.]+", lines[i+1])
                if m: data['roce'] = m[0]
            elif "roe" in l_low and i + 1 < len(lines):
                m = re.findall(r"[\d.]+", lines[i+1])
                if m: data['roe'] = m[0]
            elif "promoter holding" in l_low and i + 1 < len(lines):
                m = re.findall(r"[\d.]+", lines[i+1])
                if m: data['promoter'] = m[0]

    # Tables parsing
    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            k = cells[0].lower()
            v = cells[1].replace(",", "").replace("%", "")
            if "debt to equity" in k or "debt/equity" in k:
                data['debt_equity'] = v
            elif "interest cover" in k:
                data['int_coverage'] = v
            elif "pledge" in k:
                data['pledged'] = v
            elif "opm" in k or "operating profit margin" in k:
                data['opm'] = v
            elif "piotroski" in k:
                data['piotroski'] = v
            elif "fii" in k:
                data['fii'] = v
            elif "dii" in k:
                data['dii'] = v

    # Growth & CAGR blocks
    text_content = soup.get_text()
    sg_3 = re.search(r"Sales Growth.*?3 Year\s*([\d.]+)%", text_content, re.DOTALL | re.IGNORECASE)
    if sg_3: data['sales_growth_3yr'] = sg_3.group(1)

    sg_1 = re.search(r"Sales Growth.*?1 Year\s*([\d.]+)%", text_content, re.DOTALL | re.IGNORECASE)
    if sg_1: data['sales_growth'] = sg_1.group(1)

    pg_3 = re.search(r"Profit Growth.*?3 Year\s*([\d.]+)%", text_content, re.DOTALL | re.IGNORECASE)
    if pg_3: data['profit_var_3yr'] = pg_3.group(1)

    pg_1 = re.search(r"Profit Growth.*?1 Year\s*([\d.]+)%", text_content, re.DOTALL | re.IGNORECASE)
    if pg_1: data['profit_growth'] = pg_1.group(1)

    return data
        
