import os
import re
import requests
from bs4 import BeautifulSoup

try:
  import cloudscraper

  HAS_CLOUDSCRAPER = True
except ImportError:
  HAS_CLOUDSCRAPER = False

try:
  import yfinance as yf

  HAS_YFINANCE = True
except ImportError:
  HAS_YFINANCE = False


# -------------------------------------------------------------
# SAFE NUMBER PARSER
# -------------------------------------------------------------
def parse_number(text):
  """Converts text such as ₹1,23,456 Cr., 18.2, -14.6% into float safely."""
  if text is None:
    return None

  text = (
      str(text)
      .replace(",", "")
      .replace("₹", "")
      .replace("%", "")
      .replace("Cr.", "")
      .replace("Cr", "")
      .strip()
  )

  match = re.search(r"-?\d+(?:\.\d+)?", text)
  if not match:
    return None

  try:
    return float(match.group(0))
  except (ValueError, TypeError):
    return None


# -------------------------------------------------------------
# CREATE SECURE SESSION (Cloudscraper / Requests)
# -------------------------------------------------------------
def get_secure_session():
  if HAS_CLOUDSCRAPER:
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
  else:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    })
    return session


# -------------------------------------------------------------
# HYBRID DATA SCRAPER (Screener + YFinance Backup)
# -------------------------------------------------------------
def get_screener_data(symbol):
  clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

  metrics = {
      "piotroski": None,
      "mcap": None,
      "pe": None,
      "roce": None,
      "roe": None,
      "debt_to_equity": None,
      "sales_growth_ttm": None,
      "sales_growth_3y": None,
      "profit_growth_ttm": None,
      "profit_growth_3y": None,
      "opm": None,
      "interest_coverage_ttm": None,
      "interest_coverage_fy": None,
      "pledged_percentage": None,
      "promoter_holding": None,
      "fii_holding": None,
      "dii_holding": None,
      "sector": "N/A",
  }

  # 1. YFinance Backup Data (ಮೊದಲು ಮೂಲ ಮೆಟ್ರಿಕ್ಸ್ ಹಾಕಿಕೊಳ್ಳುವುದು)
  if HAS_YFINANCE:
    try:
      ticker = yf.Ticker(f"{clean_sym}.NS")
      info = ticker.info or {}
      if info:
        metrics["sector"] = info.get("sector") or "N/A"
        mcap = info.get("marketCap")
        if mcap:
          metrics["mcap"] = round(mcap / 10000000.0, 1)
        metrics["pe"] = info.get("trailingPE") or info.get("forwardPE")
        if info.get("debtToEquity") is not None:
          metrics["debt_to_equity"] = round(
              info.get("debtToEquity") / 100.0, 2
          )
        if info.get("operatingMargins") is not None:
          metrics["opm"] = round(info.get("operatingMargins") * 100.0, 1)
        if info.get("returnOnEquity") is not None:
          metrics["roe"] = round(info.get("returnOnEquity") * 100.0, 1)
        if info.get("heldPercentInsiders") is not None:
          metrics["promoter_holding"] = round(
              info.get("heldPercentInsiders") * 100.0, 2
          )
    except Exception:
      pass

  # 2. Screener.in Scraping (ನಿಮ್ಮ ಹೊಸ ವಿಶ್ವಾಸಾರ್ಹ ಪಾರ್ಸಿಂಗ್ ಲಾಜಿಕ್)
  url = f"https://www.screener.in/company/{clean_sym}/"
  session = get_secure_session()

  try:
    response = session.get(url, timeout=15)
    if response.status_code == 200:
      soup = BeautifulSoup(response.content, "html.parser")

      all_items = soup.find_all("li")
      for item in all_items:
        name_elem = item.find("span", class_="name") or item.find(
            "span", class_="text"
        )
        value_elem = (
            item.find("span", class_="number")
            or item.find("span", class_="value")
            or item.find("b")
        )

        if not name_elem or not value_elem:
          continue

        name = " ".join(name_elem.stripped_strings).strip().lower()
        raw_value = value_elem.get_text(" ", strip=True)
        value = parse_number(raw_value)

        if value is None:
          continue

        # ಮ್ಯಾಪಿಂಗ್ ಮಾಡುವುದು
        if "market capitalization" in name or "market cap" in name:
          metrics["mcap"] = value
        elif "stock p/e" in name or name == "p/e" or "price to earning" in name:
          metrics["pe"] = value
        elif "roce" in name or "return on capital employed" in name:
          metrics["roce"] = value
        elif "roe" in name or "return on equity" in name:
          metrics["roe"] = value
        elif any(
            k in name
            for k in ["debt to equity", "debt/equity", "debt - equity"]
        ):
          metrics["debt_to_equity"] = value
        elif "opm" in name or "operating profit margin" in name:
          metrics["opm"] = value
        elif "piotroski" in name:
          metrics["piotroski"] = int(value)
        elif "int coverage" in name or "interest coverage" in name:
          metrics["interest_coverage_ttm"] = value
        elif "pledged percentage" in name or "pledged" in name:
          metrics["pledged_percentage"] = value
        elif "promoter holding" in name:
          metrics["promoter_holding"] = value
        elif "fii holding" in name:
          metrics["fii_holding"] = value
        elif "dii holding" in name:
          metrics["dii_holding"] = value

      # Text Fallback
      page_text = soup.get_text(" ", strip=True)
      if metrics["promoter_holding"] is None:
        match = re.search(
            r"promoter holding\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            page_text,
            flags=re.IGNORECASE,
        )
        if match:
          metrics["promoter_holding"] = float(match.group(1))

      if metrics["pledged_percentage"] is None:
        match = re.search(
            r"pledged percentage\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            page_text,
            flags=re.IGNORECASE,
        )
        if match:
          metrics["pledged_percentage"] = float(match.group(1))

  except Exception as e:
    print(f"Scraping error for {clean_sym}: {e}")

  return metrics


# -------------------------------------------------------------
# FUNDAMENTAL SCORE (100M SCORE)
# -------------------------------------------------------------
def calculate_100M_score(metrics):
  marks = {}
  score = 50.0

  pe = metrics.get("pe")
  if isinstance(pe, (int, float)):
    passed = 10 <= pe <= 45
    marks["pe"] = passed
    score += 8 if passed else -4

  roce = metrics.get("roce")
  if isinstance(roce, (int, float)):
    passed = roce > 15
    marks["roce"] = passed
    score += 8 if passed else -4

  roe = metrics.get("roe")
  if isinstance(roe, (int, float)):
    passed = roe > 15
    marks["roe"] = passed
    score += 8 if passed else -4

  de = metrics.get("debt_to_equity")
  if isinstance(de, (int, float)):
    passed = de < 1.0
    marks["debt_to_equity"] = passed
    score += 8 if passed else -8

  pledge = metrics.get("pledged_percentage")
  if isinstance(pledge, (int, float)):
    passed = pledge < 5.0
    marks["promoter_pledge"] = passed
    score += 10 if passed else -10

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


# -------------------------------------------------------------
# FINAL FUNDAMENTAL ANALYSIS FUNCTION
# -------------------------------------------------------------
def get_fundamental_analysis(symbol):
  clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()

  try:
    metrics = get_screener_data(clean_sym)
    score, quality, marks = calculate_100M_score(metrics)

    fundamental_keys = [
        "mcap",
        "pe",
        "roce",
        "roe",
        "debt_to_equity",
        "sales_growth_3y",
        "profit_growth_3y",
        "opm",
        "promoter_holding",
    ]

    available = any(metrics.get(k) is not None for k in fundamental_keys)

    if not available:
      return {
          "available": False,
          "score": "N/A",
          "quality": "⚪ DATA UNAVAILABLE",
          "marks": {},
          "metrics": metrics,
          "rejections": [],
      }

    return {
        "available": True,
        "score": round(score, 1),
        "quality": quality,
        "marks": marks,
        "metrics": metrics,
        "rejections": [],
    }

  except Exception as e:
    print(f"Fundamental analysis error for {clean_sym}: {e}")
    return {
        "available": False,
        "score": "N/A",
        "quality": "⚪ DATA UNAVAILABLE",
        "marks": {},
        "metrics": {},
        "rejections": [],
    }
    
