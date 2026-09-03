import os
import re
import requests
from bs4 import BeautifulSoup


# ============================================================
# OPTIONAL CLOUDSCRAPER
# ============================================================

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
    "cricket786"
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
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Connection":
            "keep-alive"
    })

    try:

        login_url = "https://www.screener.in/login/"

        r = session.get(
            login_url,
            timeout=15
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
# NUMBER PARSER
# ============================================================

def parse_number(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("₹", "")
    text = text.replace("%", "")
    text = text.replace("Cr.", "")
    text = text.replace("Cr", "")
    text = text.strip()

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
# LABEL NORMALIZER
# ============================================================

def clean_label(text):

    if text is None:
        return ""

    text = str(text).lower().strip()

    text = text.replace(
        "\xa0",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# FORMAT DECIMAL
# ============================================================

def fmt(value, decimals=2):

    if value is None:
        return "N/A"

    try:

        return f"{float(value):.{decimals}f}"

    except Exception:

        return "N/A"


# ============================================================
# GET ALL TABLES
# ============================================================

def get_table_data(soup):

    tables = []

    for table in soup.find_all("table"):

        rows = []

        for tr in table.find_all("tr"):

            cells = tr.find_all(
                ["th", "td"]
            )

            row = []

            for cell in cells:

                text = cell.get_text(
                    " ",
                    strip=True
                )

                row.append(text)

            if row:
                rows.append(row)

        if rows:
            tables.append(rows)

    return tables


# ============================================================
# FIND TABLE BY ROW LABEL
# ============================================================

def find_table_with_label(
    tables,
    label
):

    target = clean_label(label)

    for table in tables:

        for row in table:

            if not row:
                continue

            first = clean_label(
                row[0]
            )

            if target in first:
                return table

    return None


# ============================================================
# FIND VALUE IN TABLE
# ============================================================

def find_table_value(
    tables,
    labels
):

    labels = [
        clean_label(x)
        for x in labels
    ]

    for table in tables:

        for row in table:

            if not row:
                continue

            first = clean_label(
                row[0]
            )

            for label in labels:

                if first == label or label in first:

                    # Prefer last/current value
                    for value in reversed(row[1:]):

                        number = parse_number(
                            value
                        )

                        if number is not None:
                            return number

    return None


# ============================================================
# GET TOP RATIO DATA
# ============================================================

def get_top_ratios(soup):

    data = {}

    # --------------------------------------------------------
    # Screener ratio list
    # --------------------------------------------------------

    for li in soup.find_all("li"):

        name = li.find(
            "span",
            class_=re.compile("name")
        )

        number = li.find(
            "span",
            class_=re.compile("number")
        )

        if not name or not number:
            continue

        label = clean_label(
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

            data[label] = value

    # --------------------------------------------------------
    # Alternative ratio layout
    # --------------------------------------------------------

    for element in soup.select(
        "#top-ratios li"
    ):

        text = element.get_text(
            " ",
            strip=True
        )

        if not text:
            continue

        value = parse_number(
            text
        )

        if value is not None:
            continue

    return data


# ============================================================
# GET CURRENT PRICE
# ============================================================

def get_current_price(soup):

    # Screener current price
    top = soup.find(
        id="top"
    )

    if top:

        text = top.get_text(
            " ",
            strip=True
        )

        match = re.search(
            r"₹\s*([\d,]+(?:\.\d+)?)",
            text
        )

        if match:

            return parse_number(
                match.group(1)
            )

    # Fallback
    for selector in [
        "#top .number",
        ".company-ratios .number"
    ]:

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
# SECTOR / INDUSTRY
# ============================================================

def get_sector_industry(soup):

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
                href=re.compile(
                    r"/market/"
                )
            )

            names = []

            for link in links:

                text = link.get_text(
                    " ",
                    strip=True
                )

                if text:
                    names.append(text)

            # WABAG page structure:
            # Utilities -> Other Utilities ->
            # Water Supply & Management

            if len(names) >= 3:

                sector = names[0]
                industry = names[-1]

            elif len(names) == 2:

                sector = names[0]
                industry = names[-1]

            elif len(names) == 1:

                sector = names[0]

    except Exception:
        pass

    return sector, industry


# ============================================================
# QUARTERLY DATA
# ============================================================

def get_quarterly_data(soup):

    data = {
        "sales": [],
        "net_profit": [],
        "opm": [],
        "eps": []
    }

    try:

        tables = get_table_data(
            soup
        )

        for table in tables:

            if not table:
                continue

            header = table[0]

            header_text = " ".join(
                clean_label(x)
                for x in header
            )

            # Find quarterly table
            if (
                "jun" not in header_text
                and "sep" not in header_text
                and "dec" not in header_text
            ):
                continue

            for row in table:

                if not row:
                    continue

                label = clean_label(
                    row[0]
                )

                values = []

                for item in row[1:]:

                    number = parse_number(
                        item
                    )

                    if number is not None:
                        values.append(
                            number
                        )

                if label.startswith(
                    "sales"
                ):

                    data["sales"] = values

                elif label.startswith(
                    "net profit"
                ):

                    data["net_profit"] = values

                elif label.startswith(
                    "opm"
                ):

                    data["opm"] = values

                elif label.startswith(
                    "eps"
                ):

                    data["eps"] = values

    except Exception:
        pass

    return data


# ============================================================
# CALCULATE TTM GROWTH
# ============================================================

def calculate_ttm_growth(values):

    if not values or len(values) < 8:
        return None

    try:

        current_ttm = sum(
            values[-4:]
        )

        previous_ttm = sum(
            values[-8:-4]
        )

        if previous_ttm == 0:
            return None

        growth = (
            (current_ttm - previous_ttm)
            / previous_ttm
        ) * 100

        return growth

    except Exception:
        return None


# ============================================================
# SHAREHOLDING
# ============================================================

def get_shareholding(soup):

    result = {

        "promoter_holding": None,
        "fii_holding": None,
        "dii_holding": None,

        "pledged_percentage": None
    }

    try:

        tables = get_table_data(
            soup
        )

        for table in tables:

            for row in table:

                if not row:
                    continue

                label = clean_label(
                    row[0]
                )

                # --------------------------------------------
                # Promoters
                # --------------------------------------------

                if label.startswith(
                    "promoters"
                ):

                    values = []

                    for x in row[1:]:

                        v = parse_number(x)

                        if v is not None:
                            values.append(v)

                    if values:
                        result[
                            "promoter_holding"
                        ] = values[-1]

                # --------------------------------------------
                # FIIs
                # --------------------------------------------

                elif label.startswith(
                    "fiis"
                ):

                    values = []

                    for x in row[1:]:

                        v = parse_number(x)

                        if v is not None:
                            values.append(v)

                    if values:
                        result[
                            "fii_holding"
                        ] = values[-1]

                # --------------------------------------------
                # DIIs
                # --------------------------------------------

                elif label.startswith(
                    "diis"
                ):

                    values = []

                    for x in row[1:]:

                        v = parse_number(x)

                        if v is not None:
                            values.append(v)

                    if values:
                        result[
                            "dii_holding"
                        ] = values[-1]

    except Exception:
        pass

    return result


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
        "sales_growth_5y": None,

        "profit_growth_ttm": None,
        "profit_growth_3y": None,
        "profit_growth_5y": None,

        # ----------------------------------------------------
        # DEBT
        # ----------------------------------------------------

        "debt_to_equity": None,

        "interest_coverage_ttm": None,
        "interest_coverage_fy": None,

        # ----------------------------------------------------
        # SHAREHOLDING
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
        # EXTRA
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
        "peg_ratio": None
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
                timeout=20
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

            top = get_top_ratios(
                soup
            )

            metrics["market_cap"] = top.get(
                "market cap"
            )

            metrics["pe"] = top.get(
                "stock p/e",
                top.get("p/e")
            )

            metrics["book_value"] = top.get(
                "book value"
            )

            metrics["dividend_yield"] = top.get(
                "dividend yield"
            )

            metrics["roce"] = top.get(
                "roce"
            )

            metrics["roe"] = top.get(
                "roe"
            )

            metrics["face_value"] = top.get(
                "face value"
            )

            # =================================================
            # CURRENT PRICE
            # =================================================

            metrics["current_price"] = (
                get_current_price(soup)
            )

            # =================================================
            # SECTOR
            # =================================================

            (
                metrics["sector"],
                metrics["industry"]
            ) = get_sector_industry(
                soup
            )

            # =================================================
            # TABLE DATA
            # =================================================

            tables = get_table_data(
                soup
            )

            # =================================================
            # PROFIT & LOSS DATA
            # =================================================

            sales_table = find_table_with_label(
                tables,
                "sales"
            )

            if sales_table:

                for row in sales_table:

                    if not row:
                        continue

                    label = clean_label(
                        row[0]
                    )

                    if label == "sales":

                        values = []

                        for x in row[1:]:

                            v = parse_number(x)

                            if v is not None:
                                values.append(v)

                        if values:

                            metrics["sales"] = (
                                values[-1]
                            )

                            # TTM sales growth
                            growth = (
                                calculate_ttm_growth(
                                    values
                                )
                            )

                            if growth is not None:

                                metrics[
                                    "sales_growth_ttm"
                                ] = growth

                    # ------------------------------------------------
                    # Operating Margin
                    # ------------------------------------------------

                    elif label.startswith(
                        "opm"
                    ):

                        values = []

                        for x in row[1:]:

                            v = parse_number(x)

                            if v is not None:
                                values.append(v)

                        if values:

                            metrics["opm"] = (
                                values[-1]
                            )

                    # ------------------------------------------------
                    # Net Profit
                    # ------------------------------------------------

                    elif label.startswith(
                        "net profit"
                    ):

                        values = []

                        for x in row[1:]:

                            v = parse_number(x)

                            if v is not None:
                                values.append(v)

                        if values:

                            metrics["net_profit"] = (
                                values[-1]
                            )

                            growth = (
                                calculate_ttm_growth(
                                    values
                                )
                            )

                            if growth is not None:

                                metrics[
                                    "profit_growth_ttm"
                                ] = growth

                    # ------------------------------------------------
                    # EPS
                    # ------------------------------------------------

                    elif label.startswith(
                        "eps"
                    ):

                        values = []

                        for x in row[1:]:

                            v = parse_number(x)

                            if v is not None:
                                values.append(v)

                        if values:

                            metrics["eps"] = (
                                values[-1]
                            )

            # =================================================
            # COMPOUNDED GROWTH SECTION
            # =================================================

            for table in tables:

                for row in table:

                    if not row:
                        continue

                    label = clean_label(
                        row[0]
                    )

                    value_text = " ".join(
                        row
                    )

                    # Sales Growth
                    if label == "3 years":

                        pass

                    if "sales growth" in value_text.lower():

                        text = value_text.lower()

                        match_3y = re.search(
                            r"3\s*years?\s*:\s*"
                            r"([-+]?\d+(?:\.\d+)?)\s*%",
                            text
                        )

                        match_5y = re.search(
                            r"5\s*years?\s*:\s*"
                            r"([-+]?\d+(?:\.\d+)?)\s*%",
                            text
                        )

                        if match_3y:

                            metrics[
                                "sales_growth_3y"
                            ] = float(
                                match_3y.group(1)
                            )

                        if match_5y:

                            metrics[
                                "sales_growth_5y"
                            ] = float(
                                match_5y.group(1)
                            )

                    # Profit Growth
                    if "profit growth" in value_text.lower():

                        text = value_text.lower()

                        match_3y = re.search(
                            r"3\s*years?\s*:\s*"
                            r"([-+]?\d+(?:\.\d+)?)\s*%",
                            text
                        )

                        match_5y = re.search(
                            r"5\s*years?\s*:\s*"
                            r"([-+]?\d+(?:\.\d+)?)\s*%",
                            text
                        )

                        if match_3y:

                            metrics[
                                "profit_growth_3y"
                            ] = float(
                                match_3y.group(1)
                            )

                        if match_5y:

                            metrics[
                                "profit_growth_5y"
                            ] = float(
                                match_5y.group(1)
                            )

            # =================================================
            # BALANCE SHEET
            # =================================================

            borrowings = find_table_value(
                tables,
                [
                    "borrowings"
                ]
            )

            reserves = find_table_value(
                tables,
                [
                    "reserves"
                ]
            )

            equity_capital = find_table_value(
                tables,
                [
                    "equity capital"
                ]
            )

            # ------------------------------------------------
            # Debt / Equity
            #
            # Screener:
            # Debt / Equity =
            # Borrowings / Shareholders Equity
            # ------------------------------------------------

            if borrowings is not None:

                equity = 0.0

                if reserves is not None:
                    equity += reserves

                if equity_capital is not None:
                    equity += equity_capital

                if equity > 0:

                    metrics[
                        "debt_to_equity"
                    ] = (
                        borrowings / equity
                    )

            # =================================================
            # RATIOS
            # =================================================

            metrics["debtors_days"] = (
                find_table_value(
                    tables,
                    ["debtor days"]
                )
            )

            metrics["inventory_days"] = (
                find_table_value(
                    tables,
                    ["inventory days"]
                )
            )

            metrics["days_payable"] = (
                find_table_value(
                    tables,
                    ["days payable"]
                )
            )

            metrics["cash_conversion_cycle"] = (
                find_table_value(
                    tables,
                    ["cash conversion cycle"]
                )
            )

            metrics["working_capital_days"] = (
                find_table_value(
                    tables,
                    ["working capital days"]
                )
            )

            metrics["asset_turnover"] = (
                find_table_value(
                    tables,
                    ["asset turnover"]
                )
            )

            # =================================================
            # SHAREHOLDING
            # =================================================

            holding = get_shareholding(
                soup
            )

            metrics.update(
                holding
            )

            # =================================================
            # CAP CATEGORY
            # =================================================

            if metrics["market_cap"] is not None:

                if metrics["market_cap"] >= 20000:

                    metrics[
                        "cap_category"
                    ] = "🟢 LARGE CAP"

                elif metrics["market_cap"] >= 5000:

                    metrics[
                        "cap_category"
                    ] = "🟡 MID CAP"

                else:

                    metrics[
                        "cap_category"
                    ] = "🔴 SMALL CAP"

            # =================================================
            # STOP IF VALID PAGE
            # =================================================

            if metrics["market_cap"] is not None:
                break

        except Exception:
            continue

    return metrics


# ============================================================
# FIXED 100 POINT FUNDAMENTAL SCORE
# ============================================================

def calculate_100M_score(m):

    earned_score = 0.0

    marks = {}

    # ========================================================
    # PROFIT GROWTH — 15
    # ========================================================

    pg = (
        m.get("profit_growth_ttm")
        if m.get("profit_growth_ttm") is not None
        else m.get("profit_growth_3y")
    )

    if pg is not None:

        if pg >= 12:

            earned_score += 15
            marks["profit_growth"] = True

        elif pg >= 5:

            earned_score += 5
            marks["profit_growth"] = False

        else:

            marks["profit_growth"] = False

    else:

        marks["profit_growth"] = None

    # ========================================================
    # ROCE — 15
    # ========================================================

    roce = m.get("roce")

    if roce is not None:

        if roce >= 15:

            earned_score += 15
            marks["roce"] = True

        elif roce >= 10:

            earned_score += 6
            marks["roce"] = False

        else:

            marks["roce"] = False

    else:

        marks["roce"] = None

    # ========================================================
    # DEBT / EQUITY — 15
    # ========================================================

    de = m.get(
        "debt_to_equity"
    )

    if de is not None:

        if de < 1:

            earned_score += 15
            marks["debt_to_equity"] = True

        elif de < 1.5:

            earned_score += 5
            marks["debt_to_equity"] = False

        else:

            marks["debt_to_equity"] = False

    else:

        marks["debt_to_equity"] = None

    # ========================================================
    # ROE — 12
    # ========================================================

    roe = m.get("roe")

    if roe is not None:

        if roe >= 15:

            earned_score += 12
            marks["roe"] = True

        elif roe >= 10:

            earned_score += 5
            marks["roe"] = False

        else:

            marks["roe"] = False

    else:

        marks["roe"] = None

    # ========================================================
    # SALES GROWTH — 12
    # ========================================================

    sg = (
        m.get("sales_growth_ttm")
        if m.get("sales_growth_ttm") is not None
        else m.get("sales_growth_3y")
    )

    if sg is not None:

        if sg >= 10:

            earned_score += 12
            marks["sales_growth"] = True

        elif sg >= 5:

            earned_score += 4
            marks["sales_growth"] = False

        else:

            marks["sales_growth"] = False

    else:

        marks["sales_growth"] = None

    # ========================================================
    # OPM — 12
    # ========================================================

    opm = m.get("opm")

    if opm is not None:

        if opm >= 15:

            earned_score += 12
            marks["opm"] = True

        elif opm >= 8:

            earned_score += 4
            marks["opm"] = False

        else:

            marks["opm"] = False

    else:

        marks["opm"] = None

    # ========================================================
    # P/E — 10
    # ========================================================

    pe = m.get("pe")

    if pe is not None:

        if 10 <= pe <= 45:

            earned_score += 10
            marks["pe"] = True

        elif pe <= 60:

            earned_score += 4
            marks["pe"] = False

        else:

            marks["pe"] = False

    else:

        marks["pe"] = None

    # ========================================================
    # INTEREST COVERAGE — 9
    # ========================================================

    ic = (
        m.get("interest_coverage_ttm")
        if m.get("interest_coverage_ttm") is not None
        else m.get("interest_coverage_fy")
    )

    if ic is not None:

        if ic >= 3.5:

            earned_score += 9
            marks["interest_coverage"] = True

        else:

            marks["interest_coverage"] = False

    else:

        marks["interest_coverage"] = None

    # ========================================================
    # FIXED 100 POINT SCORE
    # ========================================================

    final_score = int(
        round(earned_score)
    )

    # ========================================================
    # QUALITY
    # ========================================================

    if final_score >= 80:

        quality = "🟢 A+ SUPER STRONG"

    elif final_score >= 65:

        quality = "🟢 A GOOD QUALITY"

    elif final_score >= 50:

        quality = "🟡 B AVERAGE"

    else:

        quality = "🔴 C WEAK"

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

        score, quality, marks = (
            calculate_100M_score(
                metrics
            )
        )

        return {

            "available": (
                metrics.get("market_cap")
                is not None
            ),

            "score": score,

            "quality": quality,

            "marks": marks,

            "metrics": metrics,

            "rejections": []

        }

    except Exception as e:

        return {

            "available": False,

            "score": 0,

            "quality": "⚪ DATA UNAVAILABLE",

            "marks": {},

            "metrics": {},

            "rejections": [
                str(e)
            ]

        }
