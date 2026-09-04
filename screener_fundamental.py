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
# SESSION
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

        r = session.get(
            login_url,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        csrf = soup.find(
            "input",
            {"name": "csrfmiddlewaretoken"}
        )

        if csrf and SCREENER_PASS:

            session.post(
                login_url,
                data={
                    "username": SCREENER_USER,
                    "password": SCREENER_PASS,
                    "csrfmiddlewaretoken":
                        csrf.get("value", "")
                },
                headers={
                    "Referer": login_url
                },
                timeout=20
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

    text = (
        text
        .replace(",", "")
        .replace("₹", "")
        .replace("%", "")
        .replace("Cr.", "")
        .replace("Cr", "")
        .strip()
    )

    match = re.search(
        r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)",
        text
    )

    if not match:
        return None

    try:
        return float(match.group(0))
    except Exception:
        return None


# ============================================================
# LABEL NORMALIZER
# ============================================================

def normalize_label(text):

    if text is None:
        return ""

    text = str(text).lower()

    text = text.replace(
        "\xa0",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.replace(
        ":",
        ""
    )

    return text.strip()


# ============================================================
# FORMAT NUMBER
# ============================================================

def format_number(
    value,
    decimals=2
):

    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "N/A"


# ============================================================
# GET ROW VALUE
# ============================================================

def row_numbers(row):

    values = []

    for cell in row:

        value = parse_number(
            cell
        )

        if value is not None:
            values.append(value)

    return values


# ============================================================
# EXTRACT ALL HTML TABLE ROWS
# ============================================================

def extract_rows(soup):

    rows = []

    for table in soup.find_all("table"):

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            if not cells:
                continue

            values = []

            for cell in cells:

                text = cell.get_text(
                    " ",
                    strip=True
                )

                values.append(text)

            if values:
                rows.append(values)

    return rows


# ============================================================
# FIND ROW
# ============================================================

def find_row(
    rows,
    labels
):

    labels = [
        normalize_label(x)
        for x in labels
    ]

    for row in rows:

        if not row:
            continue

        first = normalize_label(
            row[0]
        )

        for label in labels:

            if (
                first == label
                or first.startswith(label)
            ):
                return row

    return None


# ============================================================
# FIND CURRENT/LATEST VALUE
# ============================================================

def latest_row_value(
    rows,
    labels
):

    row = find_row(
        rows,
        labels
    )

    if not row:
        return None

    # Screener tables have periods from
    # oldest -> newest.
    # Last numeric value = latest available value.

    values = row_numbers(
        row[1:]
    )

    if values:
        return values[-1]

    return None


# ============================================================
# TOP RATIOS
# ============================================================

def get_top_ratios(soup):

    result = {}

    # --------------------------------------------------------
    # Standard Screener ratio list
    # --------------------------------------------------------

    for li in soup.select(
        "#top-ratios li"
    ):

        name = li.select_one(
            ".name"
        )

        number = li.select_one(
            ".number"
        )

        if not name or not number:
            continue

        label = normalize_label(
            name.get_text(
                " ",
                strip=True
            )
        )

        value = parse_number(
            number.get_text(
                " ",
                strip=True
            )
        )

        if label and value is not None:
            result[label] = value

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not result:

        for li in soup.find_all("li"):

            name = li.find(
                "span",
                class_=re.compile(
                    r"\bname\b"
                )
            )

            number = li.find(
                "span",
                class_=re.compile(
                    r"\bnumber\b"
                )
            )

            if not name or not number:
                continue

            label = normalize_label(
                name.get_text(
                    " ",
                    strip=True
                )
            )

            value = parse_number(
                number.get_text(
                    " ",
                    strip=True
                )
            )

            if label and value is not None:
                result[label] = value

    return result


# ============================================================
# GET RATIO VALUE
# ============================================================

def ratio_value(
    ratios,
    labels
):

    for label in labels:

        key = normalize_label(
            label
        )

        if key in ratios:
            return ratios[key]

    return None


# ============================================================
# SECTOR / INDUSTRY
# ============================================================

def get_sector_industry(soup):

    sector = "N/A"
    industry = "N/A"

    try:

        # Current Screener breadcrumb/category area
        candidates = []

        for a in soup.find_all(
            "a",
            href=True
        ):

            href = a.get("href", "")

            if "/market/" not in href:
                continue

            text = a.get_text(
                " ",
                strip=True
            )

            if text:
                candidates.append(text)

        # Remove duplicates while preserving order
        unique = []

        for item in candidates:

            if item not in unique:
                unique.append(item)

        if len(unique) >= 1:
            sector = unique[0]

        if len(unique) >= 2:
            industry = unique[-1]

    except Exception:
        pass

    return sector, industry


# ============================================================
# SHAREHOLDING TABLE
# ============================================================

def get_shareholding_data(
    soup
):

    result = {
        "promoter_holding": None,
        "fii_holding": None,
        "dii_holding": None,
        "pledged_percentage": None
    }

    try:

        tables = soup.find_all(
            "table"
        )

        for table in tables:

            rows = []

            for tr in table.find_all("tr"):

                cells = tr.find_all(
                    ["th", "td"]
                )

                if not cells:
                    continue

                row = [
                    cell.get_text(
                        " ",
                        strip=True
                    )
                    for cell in cells
                ]

                rows.append(row)

            if not rows:
                continue

            for row in rows:

                if not row:
                    continue

                label = normalize_label(
                    row[0]
                )

                values = row_numbers(
                    row[1:]
                )

                if not values:
                    continue

                latest = values[-1]

                # --------------------------------------------
                # PROMOTERS
                # --------------------------------------------

                if (
                    label == "promoters"
                    or label.startswith(
                        "promoters"
                    )
                ):

                    result[
                        "promoter_holding"
                    ] = latest

                # --------------------------------------------
                # FIIs
                # --------------------------------------------

                elif (
                    label == "fiis"
                    or label.startswith(
                        "fiis"
                    )
                ):

                    result[
                        "fii_holding"
                    ] = latest

                # --------------------------------------------
                # DIIs
                # --------------------------------------------

                elif (
                    label == "diis"
                    or label.startswith(
                        "diis"
                    )
                ):

                    result[
                        "dii_holding"
                    ] = latest

                # --------------------------------------------
                # PUBLIC / PROMOTER PLEDGE
                # --------------------------------------------

                elif (
                    "pledged" in label
                    and "%" in " ".join(row)
                ):

                    result[
                        "pledged_percentage"
                    ] = latest

    except Exception:
        pass

    # --------------------------------------------------------
    # Direct pledged percentage from HTML text
    # --------------------------------------------------------

    try:

        page_text = soup.get_text(
            " ",
            strip=True
        )

        patterns = [

            r"pledged\s*[:\-]?\s*"
            r"(\d+(?:\.\d+)?)\s*%",

            r"pledge\s*[:\-]?\s*"
            r"(\d+(?:\.\d+)?)\s*%"

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                page_text,
                re.I
            )

            if match:

                result[
                    "pledged_percentage"
                ] = float(
                    match.group(1)
                )

                break

    except Exception:
        pass

    return result


# ============================================================
# COMPOUNDED GROWTH
# ============================================================

def get_compounded_growth(
    soup
):

    result = {
        "sales_growth_3y": None,
        "sales_growth_5y": None,
        "profit_growth_3y": None,
        "profit_growth_5y": None
    }

    try:

        section = soup.find(
            "section",
            id="profit-loss"
        )

        if not section:
            section = soup

        text = section.get_text(
            " ",
            strip=True
        )

        # ----------------------------------------------------
        # Sales Growth
        # ----------------------------------------------------

        sales_match = re.search(
            r"Sales Growth.*?"
            r"3Years?\s*[:\-]?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*%"
            r".*?"
            r"5Years?\s*[:\-]?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*%",
            text,
            re.I
        )

        if sales_match:

            result[
                "sales_growth_3y"
            ] = float(
                sales_match.group(1)
            )

            result[
                "sales_growth_5y"
            ] = float(
                sales_match.group(2)
            )

        # ----------------------------------------------------
        # Profit Growth
        # ----------------------------------------------------

        profit_match = re.search(
            r"Profit Growth.*?"
            r"3Years?\s*[:\-]?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*%"
            r".*?"
            r"5Years?\s*[:\-]?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*%",
            text,
            re.I
        )

        if profit_match:

            result[
                "profit_growth_3y"
            ] = float(
                profit_match.group(1)
            )

            result[
                "profit_growth_5y"
            ] = float(
                profit_match.group(2)
            )

    except Exception:
        pass

    return result


# ============================================================
# FULL FUNDAMENTAL DATA
# ============================================================

def get_screener_data(
    symbol
):

    clean_sym = (
        str(symbol)
        .replace(".NS", "")
        .replace(".BO", "")
        .strip()
        .upper()
    )

    metrics = {

        # BASIC
        "current_price": None,
        "market_cap": None,
        "cap_category": "N/A",

        "sector": "N/A",
        "industry": "N/A",

        # VALUATION
        "pe": None,
        "book_value": None,
        "dividend_yield": None,
        "face_value": None,
        "price_to_book": None,
        "peg_ratio": None,

        # PROFITABILITY
        "roce": None,
        "roe": None,
        "opm": None,

        # GROWTH
        "sales_growth_ttm": None,
        "sales_growth_3y": None,
        "sales_growth_5y": None,

        "profit_growth_ttm": None,
        "profit_growth_3y": None,
        "profit_growth_5y": None,

        # DEBT
        "debt_to_equity": None,
        "interest_coverage_ttm": None,
        "interest_coverage_fy": None,

        # SHAREHOLDING
        "promoter_holding": None,
        "pledged_percentage": None,
        "fii_holding": None,
        "dii_holding": None,

        # QUALITY
        "piotroski": None,

        # EXTRA
        "eps": None,
        "sales": None,
        "net_profit": None,

        "debtors_days": None,
        "inventory_days": None,
        "days_payable": None,
        "working_capital_days": None,
        "cash_conversion_cycle": None,
        "asset_turnover": None
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
                timeout=25
            )

            if response.status_code != 200:
                continue

            soup = BeautifulSoup(
                response.content,
                "html.parser"
            )

            # =================================================
            # TOP RATIOS
            # =================================================

            ratios = get_top_ratios(
                soup
            )

            metrics[
                "market_cap"
            ] = ratio_value(
                ratios,
                ["market cap"]
            )

            metrics[
                "pe"
            ] = ratio_value(
                ratios,
                [
                    "stock p/e",
                    "p/e"
                ]
            )

            metrics[
                "book_value"
            ] = ratio_value(
                ratios,
                ["book value"]
            )

            metrics[
                "dividend_yield"
            ] = ratio_value(
                ratios,
                ["dividend yield"]
            )

            metrics[
                "face_value"
            ] = ratio_value(
                ratios,
                ["face value"]
            )

            metrics[
                "roce"
            ] = ratio_value(
                ratios,
                ["roce"]
            )

            metrics[
                "roe"
            ] = ratio_value(
                ratios,
                ["roe"]
            )

            # =================================================
            # CURRENT PRICE
            # =================================================

            metrics[
                "current_price"
            ] = ratio_value(
                ratios,
                [
                    "current price",
                    "price"
                ]
            )

            if metrics[
                "current_price"
            ] is None:

                top = soup.find(
                    id="top"
                )

                if top:

                    text = top.get_text(
                        " ",
                        strip=True
                    )

                    price_match = re.search(
                        r"₹\s*"
                        r"([\d,]+(?:\.\d+)?)",
                        text
                    )

                    if price_match:

                        metrics[
                            "current_price"
                        ] = parse_number(
                            price_match.group(1)
                        )

            # =================================================
            # SECTOR / INDUSTRY
            # =================================================

            (
                metrics["sector"],
                metrics["industry"]
            ) = get_sector_industry(
                soup
            )

            # =================================================
            # ALL TABLE ROWS
            # =================================================

            rows = extract_rows(
                soup
            )

            # =================================================
            # PROFITABILITY
            # =================================================

            opm = latest_row_value(
                rows,
                [
                    "opm"
                ]
            )

            if opm is not None:
                metrics["opm"] = opm

            # =================================================
            # SALES
            # =================================================

            sales_row = find_row(
                rows,
                ["sales"]
            )

            if sales_row:

                sales_values = row_numbers(
                    sales_row[1:]
                )

                if sales_values:

                    metrics[
                        "sales"
                    ] = sales_values[-1]

                    # TTM growth from last 8 periods
                    if len(sales_values) >= 8:

                        current = sum(
                            sales_values[-4:]
                        )

                        previous = sum(
                            sales_values[-8:-4]
                        )

                        if previous != 0:

                            metrics[
                                "sales_growth_ttm"
                            ] = (
                                (
                                    current -
                                    previous
                                )
                                / previous
                            ) * 100

            # =================================================
            # NET PROFIT
            # =================================================

            profit_row = find_row(
                rows,
                [
                    "net profit",
                    "net profit after tax"
                ]
            )

            if profit_row:

                profit_values = row_numbers(
                    profit_row[1:]
                )

                if profit_values:

                    metrics[
                        "net_profit"
                    ] = profit_values[-1]

                    if len(profit_values) >= 8:

                        current = sum(
                            profit_values[-4:]
                        )

                        previous = sum(
                            profit_values[-8:-4]
                        )

                        if previous != 0:

                            metrics[
                                "profit_growth_ttm"
                            ] = (
                                (
                                    current -
                                    previous
                                )
                                / previous
                            ) * 100

            # =================================================
            # EPS
            # =================================================

            metrics[
                "eps"
            ] = latest_row_value(
                rows,
                ["eps"]
            )

            # =================================================
            # DEBT / EQUITY
            # =================================================

            debt_equity = latest_row_value(
                rows,
                [
                    "debt to equity"
                ]
            )

            if debt_equity is not None:

                metrics[
                    "debt_to_equity"
                ] = debt_equity

            # =================================================
            # INTEREST COVERAGE
            # =================================================

            interest = latest_row_value(
                rows,
                [
                    "interest coverage",
                    "int coverage"
                ]
            )

            if interest is not None:

                metrics[
                    "interest_coverage_ttm"
                ] = interest

            # =================================================
            # OTHER RATIOS
            # =================================================

            metrics[
                "debtors_days"
            ] = latest_row_value(
                rows,
                [
                    "debtor days",
                    "debtors days"
                ]
            )

            metrics[
                "inventory_days"
            ] = latest_row_value(
                rows,
                [
                    "inventory days"
                ]
            )

            metrics[
                "days_payable"
            ] = latest_row_value(
                rows,
                [
                    "days payable"
                ]
            )

            metrics[
                "working_capital_days"
            ] = latest_row_value(
                rows,
                [
                    "working capital days"
                ]
            )

            metrics[
                "cash_conversion_cycle"
            ] = latest_row_value(
                rows,
                [
                    "cash conversion cycle"
                ]
            )

            metrics[
                "asset_turnover"
            ] = latest_row_value(
                rows,
                [
                    "asset turnover"
                ]
            )

            metrics[
                "price_to_book"
            ] = latest_row_value(
                rows,
                [
                    "price to book",
                    "p/b"
                ]
            )

            metrics[
                "peg_ratio"
            ] = latest_row_value(
                rows,
                [
                    "peg ratio",
                    "peg"
                ]
            )

            # =================================================
            # COMPOUNDED GROWTH
            # =================================================

            growth = get_compounded_growth(
                soup
            )

            for key, value in growth.items():

                if value is not None:

                    metrics[key] = value

            # =================================================
            # SHAREHOLDING
            # =================================================

            holding = get_shareholding_data(
                soup
            )

            metrics.update(
                holding
            )

            # =================================================
            # PIOTROSKI
            # =================================================

            piotroski = ratio_value(
                ratios,
                [
                    "piotroski score"
                ]
            )

            if piotroski is not None:

                metrics[
                    "piotroski"
                ] = int(
                    round(
                        piotroski
                    )
                )

            # =================================================
            # CAP CATEGORY
            # =================================================

            market_cap = metrics[
                "market_cap"
            ]

            if market_cap is not None:

                if market_cap >= 20000:

                    metrics[
                        "cap_category"
                    ] = "🟢 LARGE CAP"

                elif market_cap >= 5000:

                    metrics[
                        "cap_category"
                    ] = "🟡 MID CAP"

                else:

                    metrics[
                        "cap_category"
                    ] = "🔴 SMALL CAP"

            # =================================================
            # STOP WHEN VALID
            # =================================================

            if market_cap is not None:
                break

        except Exception:
            continue

    return metrics


# ============================================================
# 100 POINT FUNDAMENTAL SCORE
# ============================================================

def calculate_100M_score(
    m
):

    earned_score = 0

    marks = {}

    # ========================================================
    # PROFIT GROWTH = 15
    # ========================================================

    pg = (
        m.get("profit_growth_ttm")
        if m.get("profit_growth_ttm")
        is not None
        else m.get("profit_growth_3y")
    )

    if pg is not None:

        if pg >= 12:

            earned_score += 15
            marks[
                "profit_growth"
            ] = True

        elif pg >= 5:

            earned_score += 5
            marks[
                "profit_growth"
            ] = False

        else:

            marks[
                "profit_growth"
            ] = False

    else:

        marks[
            "profit_growth"
        ] = None

    # ========================================================
    # ROCE = 15
    # ========================================================

    roce = m.get(
        "roce"
    )

    if roce is not None:

        if roce >= 15:

            earned_score += 15
            marks[
                "roce"
            ] = True

        elif roce >= 10:

            earned_score += 6
            marks[
                "roce"
            ] = False

        else:

            marks[
                "roce"
            ] = False

    else:

        marks[
            "roce"
        ] = None

    # ========================================================
    # DEBT / EQUITY = 15
    # ========================================================

    debt = m.get(
        "debt_to_equity"
    )

    if debt is not None:

        if debt < 1:

            earned_score += 15
            marks[
                "debt_to_equity"
            ] = True

        elif debt < 1.5:

            earned_score += 5
            marks[
                "debt_to_equity"
            ] = False

        else:

            marks[
                "debt_to_equity"
            ] = False

    else:

        marks[
            "debt_to_equity"
        ] = None

    # ========================================================
    # ROE = 12
    # ========================================================

    roe = m.get(
        "roe"
    )

    if roe is not None:

        if roe >= 15:

            earned_score += 12
            marks[
                "roe"
            ] = True

        elif roe >= 10:

            earned_score += 5
            marks[
                "roe"
            ] = False

        else:

            marks[
                "roe"
            ] = False

    else:

        marks[
            "roe"
        ] = None

    # ========================================================
    # SALES GROWTH = 12
    # ========================================================

    sg = (
        m.get("sales_growth_ttm")
        if m.get("sales_growth_ttm")
        is not None
        else m.get("sales_growth_3y")
    )

    if sg is not None:

        if sg >= 10:

            earned_score += 12
            marks[
                "sales_growth"
            ] = True

        elif sg >= 5:

            earned_score += 4
            marks[
                "sales_growth"
            ] = False

        else:

            marks[
                "sales_growth"
            ] = False

    else:

        marks[
            "sales_growth"
        ] = None

    # ========================================================
    # OPM = 12
    # ========================================================

    opm = m.get(
        "opm"
    )

    if opm is not None:

        if opm >= 15:

            earned_score += 12
            marks[
                "opm"
            ] = True

        elif opm >= 8:

            earned_score += 4
            marks[
                "opm"
            ] = False

        else:

            marks[
                "opm"
            ] = False

    else:

        marks[
            "opm"
        ] = None

    # ========================================================
    # P/E = 10
    # ========================================================

    pe = m.get(
        "pe"
    )

    if pe is not None:

        if 10 <= pe <= 45:

            earned_score += 10
            marks[
                "pe"
            ] = True

        elif pe <= 60:

            earned_score += 4
            marks[
                "pe"
            ] = False

        else:

            marks[
                "pe"
            ] = False

    else:

        marks[
            "pe"
        ] = None

    # ========================================================
    # INTEREST COVERAGE = 9
    # ========================================================

    ic = (
        m.get(
            "interest_coverage_ttm"
        )
        if m.get(
            "interest_coverage_ttm"
        ) is not None
        else m.get(
            "interest_coverage_fy"
        )
    )

    if ic is not None:

        if ic >= 3.5:

            earned_score += 9
            marks[
                "interest_coverage"
            ] = True

        else:

            marks[
                "interest_coverage"
            ] = False

    else:

        marks[
            "interest_coverage"
        ] = None

    # ========================================================
    # FINAL SCORE
    # ========================================================

    final_score = int(
        earned_score
    )

    # ========================================================
    # QUALITY
    # ========================================================

    if final_score >= 80:

        quality = (
            "🟢 A+ SUPER STRONG"
        )

    elif final_score >= 65:

        quality = (
            "🟢 A GOOD QUALITY"
        )

    elif final_score >= 50:

        quality = (
            "🟡 B AVERAGE"
        )

    else:

        quality = (
            "🔴 C WEAK"
        )

    return (
        final_score,
        quality,
        marks
    )


# ============================================================
# FINAL FUNDAMENTAL ANALYSIS
# ============================================================

def get_fundamental_analysis(
    symbol
):

    try:

        metrics = get_screener_data(
            symbol
        )

        score, quality, marks = (
            calculate_100M_score(
                metrics
            )
        )

        return {

            "available":
                metrics.get(
                    "market_cap"
                ) is not None,

            "score":
                score,

            "quality":
                quality,

            "marks":
                marks,

            "metrics":
                metrics,

            "rejections":
                []

        }

    except Exception as e:

        return {

            "available":
                False,

            "score":
                0,

            "quality":
                "⚪ DATA UNAVAILABLE",

            "marks":
                {},

            "metrics":
                {},

            "rejections":
                [str(e)]

        }
