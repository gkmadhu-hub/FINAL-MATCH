import requests
from bs4 import BeautifulSoup
import re

def get_finology_ratios(ticker):
    clean_sym = ticker.replace('.NS', '').replace('.BO', '').strip().upper()
    url = f"https://ticker.finology.in/company/{clean_sym}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    data = {}

    # 1. Company essentials & Top ratios
    for card in soup.find_all("div", class_=["cardscreen", "product-item", "card"]):
        text = card.get_text(separator=" ").strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for idx, line in enumerate(lines):
            line_l = line.lower()
            if "market cap" in line_l and idx + 1 < len(lines):
                data['market_cap'] = re.findall(r"[\d,.]+", lines[idx+1].replace(",", ""))[0]
            elif "p/e" in line_l and idx + 1 < len(lines):
                data['pe'] = re.findall(r"[\d.]+", lines[idx+1])[0]
            elif "roce" in line_l and idx + 1 < len(lines):
                data['roce'] = re.findall(r"[\d.]+", lines[idx+1])[0]
            elif "roe" in line_l and idx + 1 < len(lines):
                data['roe'] = re.findall(r"[\d.]+", lines[idx+1])[0]
            elif "debt to equity" in line_l and idx + 1 < len(lines):
                data['debt_equity'] = re.findall(r"[\d.]+", lines[idx+1])[0]

    # 2. General ratio table parsing
    for row in soup.find_all("tr"):
        row_text = row.get_text(separator=" ").strip()
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) >= 2:
            k = cells[0].lower()
            v = cells[1].replace(",", "").replace("%", "")
            
            if "piotroski" in k:
                data['piotroski'] = v
            elif "promoter pledged" in k or "pledged" in k:
                data['pledged'] = v
            elif "promoter" in k and "promoter" not in data:
                data['promoter'] = v
            elif "fii" in k:
                data['fii'] = v
            elif "dii" in k:
                data['dii'] = v
            elif "interest coverage" in k:
                data['int_coverage'] = v
            elif "operating profit margin" in k or "opm" in k:
                data['opm'] = v

    # 3. Sector & Current Price
    price_tag = soup.find("span", class_="Number") or soup.find("div", class_="price")
    data['current_price'] = price_tag.get_text(strip=True).replace(",", "") if price_tag else "N/A"

    sector_tag = soup.find("a", href=re.compile(r"/sector/"))
    data['sector'] = sector_tag.get_text(strip=True) if sector_tag else "Metals & Mining"

    return data

if __name__ == "__main__":
    ticker = "HINDZINC"
    ratios = get_finology_ratios(ticker)
    for k, v in ratios.items():
        print(f"{k}: {v}")
        
