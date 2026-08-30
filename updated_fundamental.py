import requests
from bs4 import BeautifulSoup
import re


# -------------------------------------------------------------
# SAFE NUMBER PARSER
# -------------------------------------------------------------
def parse_number(text):
    """
    Converts Screener text such as:
    ₹1,23,456 Cr.
    18.2
    -14.6%
    into float safely.
    """
    if text is None:
        return None

    text = str(text).strip()

    # Remove commas, currency and percentage
    text = (
        text.replace(",", "")
            .replace("₹", "")
            .replace("%", "")
            .replace("Cr.", "")
            .replace("Cr", "")
            .strip()
    )

    # Find first valid numeric value
    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except (ValueError, TypeError):
        return None


# -------------------------------------------------------------
# SCREENER DATA
# -------------------------------------------------------------
def get_screener_data(clean_sym):

    url = f"https://www.screener.in/company/{clean_sym}/consolidated/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }

    # IMPORTANT:
    # Missing data = None.
    # Do NOT use fake/default positive values.
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

        "sector": None
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print(
                f"Screener HTTP {response.status_code} "
                f"for {clean_sym}"
            )
            return metrics

        soup = BeautifulSoup(
            response.content,
            "html.parser"
        )

        # -----------------------------------------------------
        # 1. TOP RATIOS
        # -----------------------------------------------------
        ratios_div = soup.find(
            "div",
            {"id": "top-ratios"}
        )

        if ratios_div:

            items = ratios_div.find_all("li")

            for item in items:

                name_elem = item.find(
                    "span",
                    {"class": "name"}
                )

                val_elem = item.find(
                    "span",
                    {"class": "value"}
                )

                if not name_elem or not val_elem:
                    continue

                name = " ".join(
                    name_elem.stripped_strings
                ).strip().lower()

                value = parse_number(
                    val_elem.get_text(" ", strip=True)
                )

                if value is None:
                    continue

                # -------------------------------------------------
                # MARKET CAP
                # -------------------------------------------------
                if (
                    "market capitalization" in name
                    or name == "market cap"
                ):
                    metrics["mcap"] = value

                # -------------------------------------------------
                # P/E
                # -------------------------------------------------
                elif (
                    name == "stock p/e"
                    or name == "p/e"
                    or "stock p/e" in name
                ):
                    metrics["pe"] = value

                # -------------------------------------------------
                # ROCE
                # -------------------------------------------------
                elif "roce" in name:
                    metrics["roce"] = value

                # -------------------------------------------------
                # ROE
                # -------------------------------------------------
                elif (
                    "roe" in name
                    or "return on equity" in name
                ):
                    metrics["roe"] = value

                # -------------------------------------------------
                # DEBT / EQUITY
                # -------------------------------------------------
                elif (
                    "debt to equity" in name
                    or "debt/equity" in name
                    or "debt-equity" in name
                ):
                    metrics["debt_to_equity"] = value

                # -------------------------------------------------
                # OPM
                # -------------------------------------------------
                elif "opm" in name:
                    metrics["opm"] = value

                # -------------------------------------------------
                # PLEDGED
                # -------------------------------------------------
                elif "pledged percentage" in name:
                    metrics["pledged_percentage"] = value

                # -------------------------------------------------
                # PIOTROSKI
                # -------------------------------------------------
                elif "piotroski" in name:
                    metrics["piotroski"] = value

                # -------------------------------------------------
                # INTEREST COVERAGE
                #
                # IMPORTANT:
                # Do NOT put the same value into both TTM and FY.
                # Only assign if the label actually specifies it.
                # -------------------------------------------------
                elif (
                    "interest coverage" in name
                    or "int coverage" in name
                ):

                    if "ttm" in name:
                        metrics[
                            "interest_coverage_ttm"
                        ] = value

                    elif (
                        "fy" in name
                        or "year" in name
                        or "annual" in name
                    ):
                        metrics[
                            "interest_coverage_fy"
                        ] = value

                    else:
                        # Unknown period:
                        # keep as TTM only if nothing exists.
                        if (
                            metrics[
                                "interest_coverage_ttm"
                            ] is None
                        ):
                            metrics[
                                "interest_coverage_ttm"
                            ] = value

                # -------------------------------------------------
                # SALES GROWTH
                # -------------------------------------------------
                elif "sales growth" in name:

                    if (
                        "3 year" in name
                        or "3year" in name
                        or "3 years" in name
                        or "3years" in name
                        or "3 yr" in name
                        or "3yr" in name
                    ):
                        metrics[
                            "sales_growth_3y"
                        ] = value

                    elif (
                        "ttm" in name
                        or "latest" in name
                        or "current" in name
                    ):
                        metrics[
                            "sales_growth_ttm"
                        ] = value

                # -------------------------------------------------
                # PROFIT GROWTH
                # -------------------------------------------------
                elif "profit growth" in name:

                    if (
                        "3 year" in name
                        or "3year" in name
                        or "3 years" in name
                        or "3years" in name
                        or "3 yr" in name
                        or "3yr" in name
                    ):
                        metrics[
                            "profit_growth_3y"
                        ] = value

                    elif (
                        "ttm" in name
                        or "latest" in name
                        or "current" in name
                    ):
                        metrics[
                            "profit_growth_ttm"
                        ] = value

        # -----------------------------------------------------
        # 2. SHAREHOLDING
        # -----------------------------------------------------
        shareholding = soup.find(
            lambda tag:
            tag.name in ["section", "div"]
            and tag.get("id")
            and "shareholding" in tag.get("id").lower()
        )

        # Fallback: search page text/links around shareholding
        if shareholding is None:

            for heading in soup.find_all(
                ["h2", "h3", "button"]
            ):

                heading_text = heading.get_text(
                    " ",
                    strip=True
                ).lower()

                if "shareholding" in heading_text:

                    parent = heading.parent

                    if parent:
                        shareholding = parent

                    break

        # -----------------------------------------------------
        # 3. PROMOTER / FII / DII / PLEDGE
        #
        # Search the whole document conservatively.
        # -----------------------------------------------------
        page_text = soup.get_text(
            " ",
            strip=True
        )

        # These are only fallback extractions.
        # They do NOT create fake values if absent.

        patterns = {

            "promoter_holding": [
                r"promoter holding\s*([0-9]+(?:\.[0-9]+)?)\s*%"
            ],

            "fii_holding": [
                r"fii holding\s*([0-9]+(?:\.[0-9]+)?)\s*%"
            ],

            "dii_holding": [
                r"dii holding\s*([0-9]+(?:\.[0-9]+)?)\s*%"
            ],

            "pledged_percentage": [
                r"pledged percentage\s*([0-9]+(?:\.[0-9]+)?)\s*%"
            ]
        }

        for key, regex_list in patterns.items():

            for pattern in regex_list:

                match = re.search(
                    pattern,
                    page_text,
                    flags=re.IGNORECASE
                )

                if match:

                    try:
                        metrics[key] = float(
                            match.group(1)
                        )
                    except (ValueError, TypeError):
                        pass

                    break

        return metrics

    except Exception as e:

        print(
            f"Screener scraping error for "
            f"{clean_sym}: {e}"
        )

        return metrics


# -------------------------------------------------------------
# FUNDAMENTAL SCORE
# -------------------------------------------------------------
def calculate_100M_score(metrics):

    marks = {}

    # Start from neutral base.
    score = 50.0

    # ---------------------------------------------------------
    # P/E
    # ---------------------------------------------------------
    pe = metrics.get("pe")

    if isinstance(pe, (int, float)):

        passed = 10 <= pe <= 45

        marks["pe"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # ROCE
    # ---------------------------------------------------------
    roce = metrics.get("roce")

    if isinstance(roce, (int, float)):

        passed = roce > 15

        marks["roce"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # ROE
    # ---------------------------------------------------------
    roe = metrics.get("roe")

    if isinstance(roe, (int, float)):

        passed = roe > 15

        marks["roe"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # DEBT / EQUITY
    # ---------------------------------------------------------
    de = metrics.get("debt_to_equity")

    if isinstance(de, (int, float)):

        passed = de < 1.0

        marks["debt_to_equity"] = passed

        score += 8 if passed else -8

    # ---------------------------------------------------------
    # SALES GROWTH
    #
    # IMPORTANT:
    # Prefer TTM when available.
    # Otherwise use 3Y.
    #
    # This is clearer than:
    # sales_growth_3y or sales_growth_ttm
    # ---------------------------------------------------------
    sg_ttm = metrics.get(
        "sales_growth_ttm"
    )

    sg_3y = metrics.get(
        "sales_growth_3y"
    )

    if isinstance(sg_ttm, (int, float)):

        passed = sg_ttm > 10

        marks["sales_growth_ttm"] = passed

        score += 8 if passed else -4

    elif isinstance(sg_3y, (int, float)):

        passed = sg_3y > 10

        marks["sales_growth_3y"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # PROFIT GROWTH
    # ---------------------------------------------------------
    pg_ttm = metrics.get(
        "profit_growth_ttm"
    )

    pg_3y = metrics.get(
        "profit_growth_3y"
    )

    if isinstance(pg_ttm, (int, float)):

        passed = pg_ttm > 12

        marks["profit_growth_ttm"] = passed

        score += 8 if passed else -4

    elif isinstance(pg_3y, (int, float)):

        passed = pg_3y > 12

        marks["profit_growth_3y"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # OPM
    # ---------------------------------------------------------
    opm = metrics.get("opm")

    if isinstance(opm, (int, float)):

        passed = opm > 15

        marks["opm"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # INTEREST COVERAGE
    # ---------------------------------------------------------
    ic_ttm = metrics.get(
        "interest_coverage_ttm"
    )

    if isinstance(ic_ttm, (int, float)):

        passed = ic_ttm > 3.5

        marks["interest_coverage"] = passed

        score += 8 if passed else -4

    # ---------------------------------------------------------
    # PROMOTER PLEDGE
    #
    # IMPORTANT:
    # Missing pledge = UNKNOWN.
    # It must NOT automatically receive +10.
    # ---------------------------------------------------------
    pledge = metrics.get(
        "pledged_percentage"
    )

    if isinstance(pledge, (int, float)):

        passed = pledge < 5.0

        marks["promoter_pledge"] = passed

        score += 10 if passed else -10

    # ---------------------------------------------------------
    # LIMIT
    # ---------------------------------------------------------
    score = max(
        0.0,
        min(100.0, score)
    )

    # ---------------------------------------------------------
    # QUALITY
    # ---------------------------------------------------------
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
# FINAL FUNDAMENTAL ANALYSIS
# -------------------------------------------------------------
def get_fundamental_analysis(symbol):

    clean_sym = (
        symbol
        .replace(".NS", "")
        .replace(".BO", "")
        .strip()
        .upper()
    )

    try:

        metrics = get_screener_data(
            clean_sym
        )

        score, quality, marks = (
            calculate_100M_score(metrics)
        )

        # At least one meaningful fundamental
        # metric must exist for data to be
        # considered available.
        fundamental_keys = [
            "mcap",
            "pe",
            "roce",
            "roe",
            "debt_to_equity",
            "sales_growth_ttm",
            "sales_growth_3y",
            "profit_growth_ttm",
            "profit_growth_3y",
            "opm",
            "interest_coverage_ttm",
            "interest_coverage_fy",
            "promoter_holding",
            "fii_holding",
            "dii_holding"
        ]

        available = any(
            metrics.get(k) is not None
            for k in fundamental_keys
        )

        if not available:

            return {
                "available": False,
                "score": "N/A",
                "quality": "⚪ DATA UNAVAILABLE",
                "marks": {},
                "metrics": metrics,
                "rejections": []
            }

        return {
            "available": True,
            "score": round(score, 1),
            "quality": quality,
            "marks": marks,
            "metrics": metrics,
            "rejections": []
        }

    except Exception as e:

        print(
            f"Fundamental analysis error "
            f"for {clean_sym}: {e}"
        )

        return {
            "available": False,
            "score": "N/A",
            "quality": "⚪ DATA UNAVAILABLE",
            "marks": {},
            "metrics": {},
            "rejections": []
    }
