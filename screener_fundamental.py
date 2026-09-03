import os
import re
import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False


# ============================================================
# SCREENER LOGIN
# ============================================================

SCREENER_USER = os.getenv(
    "SCREENER_USERNAME",
    "bsbindurani@gmail.com"
)

SCREENER_PASS = os.getenv(
    "SCREENER_PASSWORD",
    ""
)


# ============================================================
# SCREENER SESSION
# ============================================================

def get_screener_session():

    if HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True
            }
        )
    else:
        session = requests.Session()

    session.headers.update({
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36",
        "Accept":
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })

    try:

        login_url = "https://www.screener.in/login/"

        res = session.get(
            login_url,
            timeout=15
        )

        soup = BeautifulSoup(
            res.text,
            "html.parser"
        )

        csrf = soup.find(
            "input",
            {"name": "csrfmiddlewaretoken"}
        )

        if csrf and SCREENER_PASS:

            payload = {
                "username": SCREENER_USER,
                "password": SCREENER_PASS,
                "csrfmiddlewaretoken": csrf.get("value", "")
            }

            session.post(
                login_url,
                data=payload,
                headers={
                    "Referer": login_url
                },
                timeout=15
            )

    except Exception:
        pass

    return session


screener_session = get_screener_session()


# ============================================================
# SAFE NUMBER PARSER
# ============================================================

def parse_number(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # Remove commas
    text = text.replace(",", "")

    # Remove currency
    text = text.replace("₹", "")

    # Remove Cr.
    text = text.replace("Cr.", "")
    text = text.replace("Cr", "")

    # Remove %
    text = text.replace("%", "")

    text = text.strip()

    # Keep first valid number including decimals
    match = re.search(
        r"[-+]?(?:\d+\.\d+|\d+|\.\d+)",
        text
    )

    if not match:
        return None

    try:
        return float(match.group())
    except Exception:
        return None


# ============================================================
# CLEAN LABEL
# ============================================================

def clean_label(text):

    if text is None:
        return ""

    text = str(text).strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.replace(":", "")

    return text.strip()


# ============================================================
# EXTRACT VALUE FROM SCREENER LI
# ============================================================

def extract_ratio_items(soup):

    data = {}

    # Main Screener ratio box
    for li in soup.find_all(
        "li",
        class_=re.compile(r"flex")
    ):

        name_span = li.find(
            "span",
            class_=re.compile(r"name")
        )

        value_span = li.find(
            "span",
            class_=re.compile(r"number")
        )

        if not name_span or not value_span:
            continue

        label = clean_label(
            name_span.get_text(" ", strip=True)
        )

        value_text = value_span.get_text(
            " ",
            strip=True
        )

        value = parse_number(
            value_text
        )

        if label and value is not None:
            data[label] = value

    return data


# ============================================================
# FIND VALUE USING MULTIPLE LABELS
# ============================================================

def get_first_value(data, labels):

    for label in labels:

        key = clean_label(label)

        if key in data:
            return data[key]

    return None


# ============================================================
# GET SECTOR / INDUSTRY
# ============================================================

def extract_sector_industry(soup):

    sector = "N/A"
    industry = "N/A"

    try:

        peers = soup.find(
            "section",
            {"id": "peers"}
        )

        if peers:

            links = peers.find_all(
                "a",
                href=re.compile(r"/market/")
            )

            names = []

            for link in links:

                txt = link.get_text(
                    " ",
                    strip=True
                )

                if txt:
                    names.append(txt)

            if names:

                # Usually first is industry/category
                industry = names[0]

                # Last is broader sector
                sector = names[-1]

    except Exception:
        pass

    return sector, industry


# ============================================================
# GET CURRENT PRICE
# ============================================================

def extract_current_price(soup):

    possible_selectors = [
        "#top .number",
        ".company-ratios .number",
        "#top-ratios .number"
    ]

    for selector in possible_selectors:

        try:

            element = soup.select_one(
                selector
            )

            if element:

                value = parse_number(
                    element.get_text(
                        " ",
                        strip=True
                    )
                )

                if value is not None:
                    return value

        except Exception:
            pass

    return None


# ============================================================
# FULL SCREENER FUNDAMENTAL DATA
# ============================================================

def get_screener_data(symbol):

    clean_sym = (
        str(symbol)
        .replace(".NS", "")
        .replace(".BO", "")
        .strip()
        .upper()
    )

    metrics = {

        # ----------------------------------------------------
        # BASIC
        # ----------------------------------------------------

        "current_price": None,
        "market_cap": None,
        "cap_category": "N/A",

        "sector": "N/A",
        "industry": "N/A",

        # ----------------------------------------------------
        # VALUATION
        # ----------------------------------------------------

        "pe": None,
        "book_value": None,
        "dividend_yield": None,
        "face_value": None,

        # ----------------------------------------------------
        # PROFITABILITY
        # ----------------------------------------------------

        "roce": None,
        "roe": None,
        "opm": None,

        # ----------------------------------------------------
        # GROWTH
        # ----------------------------------------------------

        "sales_growth_ttm": None,
        "sales_growth_3y": None,
        "profit_growth_ttm": None,
        "profit_growth_3y": None,

        # ----------------------------------------------------
        # DEBT
        # ----------------------------------------------------

        "debt_to_equity": None,
        "interest_coverage_ttm": None,
        "interest_coverage_fy": None,

        # ----------------------------------------------------
        # OWNERSHIP
        # ----------------------------------------------------

        "promoter_holding": None,
        "pledged_percentage": None,
        "fii_holding": None,
        "dii_holding": None,

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        "piotroski": None,

        # ----------------------------------------------------
        # EXTRA FUNDAMENTAL DATA
        # ----------------------------------------------------

        "eps": None,
        "sales": None,
        "net_profit": None,

        "debtors_days": None,
        "inventory_days": None,
        "days_payable": None,

        "working_capital_days": None,
        "cash_conversion_cycle": None,

        "asset_turnover": None,

        "price_to_book": None,
        "peg_ratio": None,
    }

    urls = [

        f"https://www.screener.in/company/"
        f"{clean_sym}/consolidated/",

        f"https://www.screener.in/company/"
        f"{clean_sym}/"
    ]

    for url in urls:

        try:

            response = screener_session.get(
                url,
                timeout=15
            )

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(
                response.content,
                "html.parser"
            )

            # ------------------------------------------------
            # RATIO DATA
            # ------------------------------------------------

            ratio_data = extract_ratio_items(
                soup
            )

            # ------------------------------------------------
            # CURRENT PRICE
            # ------------------------------------------------

            current_price = extract_current_price(
                soup
            )

            if current_price is not None:
                metrics["current_price"] = current_price

            # ------------------------------------------------
            # BASIC
            # ------------------------------------------------

            metrics["market_cap"] = get_first_value(
                ratio_data,
                [
                    "market cap"
                ]
            )

            metrics["pe"] = get_first_value(
                ratio_data,
                [
                    "stock p/e",
                    "p/e"
                ]
            )

            metrics["book_value"] = get_first_value(
                ratio_data,
                [
                    "book value"
                ]
            )

            metrics["dividend_yield"] = get_first_value(
                ratio_data,
                [
                    "dividend yield"
                ]
            )

            metrics["face_value"] = get_first_value(
                ratio_data,
                [
                    "face value"
                ]
            )

            # ------------------------------------------------
            # PROFITABILITY
            # ------------------------------------------------

            metrics["roce"] = get_first_value(
                ratio_data,
                [
                    "roce"
                ]
            )

            metrics["roe"] = get_first_value(
                ratio_data,
                [
                    "roe"
                ]
            )

            metrics["opm"] = get_first_value(
                ratio_data,
                [
                    "opm"
                ]
            )

            # ------------------------------------------------
            # GROWTH
            # ------------------------------------------------

            metrics["sales_growth_ttm"] = get_first_value(
                ratio_data,
                [
                    "sales growth",
                    "sales growth ttm"
                ]
            )

            metrics["sales_growth_3y"] = get_first_value(
                ratio_data,
                [
                    "sales growth 3years",
                    "sales growth 3 years",
                    "sales growth 3 yrs"
                ]
            )

            metrics["profit_growth_ttm"] = get_first_value(
                ratio_data,
                [
                    "profit growth",
                    "profit growth ttm"
                ]
            )

            metrics["profit_growth_3y"] = get_first_value(
                ratio_data,
                [
                    "profit var 3yrs",
                    "profit var 3 years",
                    "profit growth 3years",
                    "profit growth 3 years"
                ]
            )

            # ------------------------------------------------
            # DEBT
            # ------------------------------------------------

            metrics["debt_to_equity"] = get_first_value(
                ratio_data,
                [
                    "debt to equity"
                ]
            )

            metrics["interest_coverage_ttm"] = get_first_value(
                ratio_data,
                [
                    "int coverage",
                    "interest coverage"
                ]
            )

            # ------------------------------------------------
            # OWNERSHIP
            # ------------------------------------------------

            metrics["promoter_holding"] = get_first_value(
                ratio_data,
                [
                    "promoter holding"
                ]
            )

            metrics["pledged_percentage"] = get_first_value(
                ratio_data,
                [
                    "pledged percentage",
                    "pledged %",
                    "pledge"
                ]
            )

            metrics["fii_holding"] = get_first_value(
                ratio_data,
                [
                    "fii holding"
                ]
            )

            metrics["dii_holding"] = get_first_value(
                ratio_data,
                [
                    "dii holding"
                ]
            )

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            piotroski = get_first_value(
                ratio_data,
                [
                    "piotroski score"
                ]
            )

            if piotroski is not None:
                metrics["piotroski"] = int(
                    round(piotroski)
                )

            # ------------------------------------------------
            # EXTRA VALUES
            # ------------------------------------------------

            metrics["eps"] = get_first_value(
                ratio_data,
                [
                    "eps"
                ]
            )

            metrics["sales"] = get_first_value(
                ratio_data,
                [
                    "sales"
                ]
            )

            metrics["net_profit"] = get_first_value(
                ratio_data,
                [
                    "net profit"
                ]
            )

            metrics["debtors_days"] = get_first_value(
                ratio_data,
                [
                    "debtors days"
                ]
            )

            metrics["inventory_days"] = get_first_value(
                ratio_data,
                [
                    "inventory days"
                ]
            )

            metrics["days_payable"] = get_first_value(
                ratio_data,
                [
                    "days payable"
                ]
            )

            metrics["working_capital_days"] = get_first_value(
                ratio_data,
                [
                    "working capital days"
                ]
            )

            metrics["cash_conversion_cycle"] = get_first_value(
                ratio_data,
                [
                    "cash conversion cycle"
                ]
            )

            metrics["asset_turnover"] = get_first_value(
                ratio_data,
                [
                    "asset turnover"
                ]
            )

            metrics["price_to_book"] = get_first_value(
                ratio_data,
                [
                    "price to book",
                    "p/b"
                ]
            )

            metrics["peg_ratio"] = get_first_value(
                ratio_data,
                [
                    "peg ratio",
                    "peg"
                ]
            )

            # ------------------------------------------------
            # SECTOR / INDUSTRY
            # ------------------------------------------------

            sector, industry = extract_sector_industry(
                soup
            )

            if sector != "N/A":
                metrics["sector"] = sector

            if industry != "N/A":
                metrics["industry"] = industry

            # ------------------------------------------------
            # CAP CATEGORY
            # ------------------------------------------------

            if metrics["market_cap"] is not None:

                if metrics["market_cap"] >= 20000:

                    metrics["cap_category"] = (
                        "🟢 LARGE CAP"
                    )

                elif metrics["market_cap"] >= 5000:

                    metrics["cap_category"] = (
                        "🟡 MID CAP"
                    )

                else:

                    metrics["cap_category"] = (
                        "🔴 SMALL CAP"
                    )

            # ------------------------------------------------
            # STOP AFTER SUCCESSFUL PAGE
            # ------------------------------------------------

            if metrics["market_cap"] is not None:
                break

        except Exception:
            continue

    return metrics


# ============================================================
# 100M FUNDAMENTAL SCORE
# ============================================================

def calculate_100M_score(m):

    earned_score = 0.0
    max_possible_score = 0.0

    marks = {}

    # --------------------------------------------------------
    # PROFIT GROWTH
    # --------------------------------------------------------

    pg = (
        m["profit_growth_ttm"]
        if m.get("profit_growth_ttm") is not None
        else m.get("profit_growth_3y")
    )

    if pg is not None:

        max_possible_score += 15

        if pg >= 12.0:

            earned_score += 15
            marks["profit_growth"] = True

        else:

            earned_score += (
                5 if pg >= 5.0 else 0
            )

            marks["profit_growth"] = False

    else:

        marks["profit_growth"] = None

    # --------------------------------------------------------
    # ROCE
    # --------------------------------------------------------

    if m.get("roce") is not None:

        max_possible_score += 15

        if m["roce"] >= 15.0:

            earned_score += 15
            marks["roce"] = True

        else:

            earned_score += (
                6 if m["roce"] >= 10.0 else 0
            )

            marks["roce"] = False

    else:

        marks["roce"] = None

    # --------------------------------------------------------
    # DEBT TO EQUITY
    # --------------------------------------------------------

    if m.get("debt_to_equity") is not None:

        max_possible_score += 15

        if m["debt_to_equity"] < 1.0:

            earned_score += 15
            marks["debt_to_equity"] = True

        else:

            earned_score += (
                5 if m["debt_to_equity"] < 1.5 else 0
            )

            marks["debt_to_equity"] = False

    else:

        marks["debt_to_equity"] = None

    # --------------------------------------------------------
    # ROE
    # --------------------------------------------------------

    if m.get("roe") is not None:

        max_possible_score += 12

        if m["roe"] >= 15.0:

            earned_score += 12
            marks["roe"] = True

        else:

            earned_score += (
                5 if m["roe"] >= 10.0 else 0
            )

            marks["roe"] = False

    else:

        marks["roe"] = None

    # --------------------------------------------------------
    # SALES GROWTH
    # --------------------------------------------------------

    sg = (
        m["sales_growth_ttm"]
        if m.get("sales_growth_ttm") is not None
        else m.get("sales_growth_3y")
    )

    if sg is not None:

        max_possible_score += 12

        if sg >= 10.0:

            earned_score += 12
            marks["sales_growth"] = True

        else:

            earned_score += (
                4 if sg >= 5.0 else 0
            )

            marks["sales_growth"] = False

    else:

        marks["sales_growth"] = None

    # --------------------------------------------------------
    # OPM
    # --------------------------------------------------------

    if m.get("opm") is not None:

        max_possible_score += 12

        if m["opm"] >= 15.0:

            earned_score += 12
            marks["opm"] = True

        else:

            earned_score += (
                4 if m["opm"] >= 8.0 else 0
            )

            marks["opm"] = False

    else:

        marks["opm"] = None

    # --------------------------------------------------------
    # P/E
    # --------------------------------------------------------

    if m.get("pe") is not None:

        max_possible_score += 10

        if 10.0 <= m["pe"] <= 45.0:

            earned_score += 10
            marks["pe"] = True

        else:

            earned_score += (
                4 if m["pe"] <= 60.0 else 0
            )

            marks["pe"] = False

    else:

        marks["pe"] = None

    # --------------------------------------------------------
    # INTEREST COVERAGE
    # --------------------------------------------------------

    ic = (
        m["interest_coverage_ttm"]
        if m.get("interest_coverage_ttm") is not None
        else m.get("interest_coverage_fy")
    )

    if ic is not None:

        max_possible_score += 9

        if ic >= 3.5:

            earned_score += 9
            marks["interest_coverage"] = True

        else:

            marks["interest_coverage"] = False

    else:

        marks["interest_coverage"] = None

    # --------------------------------------------------------
    # FINAL SCORE
    # --------------------------------------------------------

    if max_possible_score >= 20:

        final_score = int(
            round(
                (earned_score / max_possible_score) * 100
            )
        )

        if final_score >= 80:

            quality = "🟢 A+ SUPER STRONG"

        elif final_score >= 65:

            quality = "🟢 A GOOD QUALITY"

        elif final_score >= 50:

            quality = "🟡 B AVERAGE"

        else:

            quality = "🔴 C WEAK"

    else:

        final_score = "N/A"
        quality = "⚪ DATA UNAVAILABLE"

    return (
        final_score,
        quality,
        marks
    )


# ============================================================
# FINAL FUNDAMENTAL ANALYSIS
# ============================================================

def get_fundamental_analysis(symbol):

    try:

        metrics = get_screener_data(
            symbol
        )

        score, quality, marks = calculate_100M_score(
            metrics
        )

        return {

            "available": (
                score != "N/A"
            ),

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
