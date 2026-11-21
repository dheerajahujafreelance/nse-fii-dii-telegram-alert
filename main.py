import requests
import datetime
import time
import os
import math
import sys
import logging

from pathlib import Path
from zoneinfo import ZoneInfo
from collections import defaultdict

# ==================================================
# 1. CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

REPORT_PAGE = "https://www.nseindia.com/reports/fii-dii"
NSE_API = "https://www.nseindia.com/api/fiidiiTradeReact"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

IST = ZoneInfo("Asia/Kolkata")

# Today + previous 3 calendar days
LOOKBACK_DAYS = 4

LOG_FILE = Path(
    os.environ.get(
        "NSE_LOG_FILE",
        str(BASE_DIR / "nse_fii_dii.log")
    )
)

CATEGORIES = {"DII", "FII/FPI"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": REPORT_PAGE,
}

# ==================================================
# 2. LOGGING
# ==================================================

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

log_handle = open(
    LOG_FILE,
    "a",
    encoding="utf-8",
    buffering=1
)

class Tee:

    def __init__(self, terminal, logfile):
        self.terminal = terminal
        self.logfile = logfile

    def write(self, message):
        self.terminal.write(message)
        self.logfile.write(message)

    def flush(self):
        self.terminal.flush()
        self.logfile.flush()

sys.stdout = Tee(sys.stdout, log_handle)
sys.stderr = Tee(sys.stderr, log_handle)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%d-%b-%Y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True
)

logger = logging.getLogger("NSE_FII_DII")

logger.info("=" * 50)
logger.info("NSE FII/DII script started")

# ==================================================
# 3. FETCH NSE DATA
# ==================================================

def fetch_nse_data():

    with requests.Session() as session:

        session.headers.update(HEADERS)

        for attempt in range(3):

            try:

                logger.info(
                    "Opening NSE FII/DII report page..."
                )

                page = session.get(
                    REPORT_PAGE,
                    timeout=30
                )

                page.raise_for_status()

                logger.info(
                    "NSE report page status: %s",
                    page.status_code
                )

                time.sleep(2)

                logger.info(
                    "Fetching NSE FII/DII API..."
                )

                response = session.get(
                    NSE_API,
                    timeout=30
                )

                response.raise_for_status()

                data = response.json()

                if not isinstance(data, list) or not data:

                    raise ValueError(
                        "Empty or invalid NSE API response"
                    )

                logger.info(
                    "NSE API successful. Records: %s",
                    len(data)
                )

                return data

            except Exception as error:

                logger.warning(
                    "NSE attempt %s failed: %s",
                    attempt + 1,
                    error
                )

                if attempt == 2:

                    logger.exception(
                        "All NSE fetch attempts failed"
                    )

                    raise

                time.sleep(5 * (attempt + 1))

    raise RuntimeError("Unable to fetch NSE data")

# ==================================================
# 4. DATE VALIDATION
# ==================================================

def parse_report_date(value):

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    if not isinstance(value, str):
        raise ValueError("Invalid report date")

    for date_format in (
        "%d-%b-%Y",
        "%Y-%m-%d"
    ):

        try:

            return datetime.datetime.strptime(
                value.strip(),
                date_format
            ).date()

        except ValueError:
            continue

    raise ValueError(
        f"Unrecognized report date: {value}"
    )

# ==================================================
# 5. RECORD VALIDATION
# ==================================================

def validate_record(row):

    trade_date = parse_report_date(
        row["date"]
    )

    category = row["category"].strip()

    if category not in CATEGORIES:

        raise ValueError(
            "Invalid category"
        )

    buy = float(row["buyValue"])
    sell = float(row["sellValue"])
    net = float(row["netValue"])

    if not all(
        math.isfinite(value)
        for value in (buy, sell, net)
    ):

        raise ValueError(
            "Invalid numerical values"
        )

    # Net must equal Buy minus Sell

    if abs((buy - sell) - net) > 0.02:

        raise ValueError(
            "Net value validation failed"
        )

    return {
        "date": trade_date,
        "category": category,
        "buy": buy,
        "sell": sell,
        "net": net
    }

def parse_nse_records(data):

    parsed = []

    for row in data:

        try:

            parsed.append(
                validate_record(row)
            )

        except (
            KeyError,
            ValueError,
            TypeError,
            AttributeError
        ) as error:

            logger.warning(
                "Skipping invalid NSE record: %s",
                error
            )

    logger.info(
        "Successfully validated records: %s",
        len(parsed)
    )

    return parsed

# ==================================================
# 6. FIND COMPLETE REPORTS
# ==================================================

def get_complete_reports(records):

    grouped = defaultdict(list)

    today = datetime.datetime.now(IST).date()

    for row in records:

        try:

            report_date = parse_report_date(
                row["date"]
            )

            # Ignore future-dated records

            if report_date > today:
                continue

            grouped[report_date].append(row)

        except (
            KeyError,
            ValueError,
            TypeError
        ):

            continue

    complete_reports = {}

    for report_date, rows in grouped.items():

        categories = [
            row["category"]
            for row in rows
        ]

        # Exactly one DII and one FII/FPI record

        if (
            len(rows) == 2
            and categories.count("DII") == 1
            and categories.count("FII/FPI") == 1
        ):

            complete_reports[report_date] = rows

    logger.info(
        "Complete reporting dates found: %s",
        len(complete_reports)
    )

    return complete_reports

# ==================================================
# 7. SELECT REPORT - LAST 4 DAYS
# ==================================================

def select_report(records):

    complete_reports = get_complete_reports(
        records
    )

    today = datetime.datetime.now(IST).date()

    # Check today first, then go backwards

    for day_offset in range(LOOKBACK_DAYS):

        check_date = today - datetime.timedelta(
            days=day_offset
        )

        logger.info(
            "Checking NSE report for: %s",
            check_date.strftime("%d-%b-%Y")
        )

        if check_date in complete_reports:

            selected_rows = complete_reports[
                check_date
            ]

            logger.info(
                "Selected NSE report date: %s",
                check_date.strftime("%d-%b-%Y")
            )

            return check_date, selected_rows

    logger.warning(
        "No complete NSE report found in last %s days.",
        LOOKBACK_DAYS
    )

    return None, None

# ==================================================
# 8. FORMAT NUMBERS
# ==================================================

def format_number(value):

    return f"{float(value):,.2f}"

# ==================================================
# 9. CREATE TELEGRAM MESSAGE
# ==================================================

def create_message(selected_date, rows):

    today = datetime.datetime.now(IST).date()

    date_text = selected_date.strftime(
        "%d-%b-%Y"
    )

    weekday_text = selected_date.strftime(
        "%A"
    )

    if selected_date == today:

        status_text = (
            "✅ Today's NSE report is available."
        )

    else:

        days_old = (today - selected_date).days

        status_text = (
            "⚠️ Today's report is not available.\n"
            "Showing the latest complete NSE report "
            f"from {weekday_text} "
            f"({days_old} calendar day(s) earlier)."
        )

    message = (

        "📊 <b>NSE FII / DII DAILY REPORT</b>\n"

        "━━━━━━━━━━━━━━━━━━━━\n"

        f"📅 <b>Data Date: {date_text} ({weekday_text})</b>\n"

        f"{status_text}\n"

        "📂 Data Source: NSE LIVE API\n"

        "📍 Capital Market Segment\n"

        "💰 Values in ₹ Crores\n\n"

        "<pre>"

        f"{'CATEGORY':<10} "
        f"{'BUY':>11} "
        f"{'SELL':>11} "
        f"{'NET':>11}\n"

        "────────────────────────────────────────\n"

    )

    rows = sorted(
        rows,
        key=lambda r: (
            0 if r["category"] == "DII" else 1
        )
    )

    for row in rows:

        net_text = f"{row['net']:+,.2f}"

        message += (

            f"{row['category']:<10} "

            f"{format_number(row['buy']):>11} "

            f"{format_number(row['sell']):>11} "

            f"{net_text:>11}\n"

        )

    message += "</pre>\n"

    # Net Buyer / Net Seller status

    for row in rows:

        if row["net"] > 0:

            status = "Net Buyer 🟢"

        elif row["net"] < 0:

            status = "Net Seller 🔴"

        else:

            status = "Neutral"

        message += (
            f"\n<b>{row['category']}: </b>{status}"
        )

    # NSE source link

    message += (

        "\n\n<a href='https://www.nseindia.com/reports/fii-dii'>"

        "Source: NSE India</a>"

    )

    return message

# ==================================================
# 10. SEND TELEGRAM MESSAGE
# ==================================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    payload = {

        "chat_id": CHAT_ID,

        "text": message,

        "parse_mode": "HTML",

        "disable_web_page_preview": True

    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=30
        )

        if not response.ok:

            raise RuntimeError(
                f"Telegram HTTP error: {response.status_code}"
            )

        result = response.json()

        if not result.get("ok"):

            raise RuntimeError(
                "Telegram rejected the message"
            )

        logger.info(
            "Telegram alert sent successfully"
        )

    except Exception as error:

        # Never expose bot token in logs

        raise RuntimeError(
            f"Telegram delivery failed: {type(error).__name__}"
        ) from None

# ==================================================
# 11. MAIN PROGRAM
# ==================================================

def main():

    logger.info(
        "Execution time: %s",
        datetime.datetime.now(IST).strftime(
            "%d-%b-%Y %H:%M:%S IST"
        )
    )

    logger.info(
        "Checking today and previous %s calendar days",
        LOOKBACK_DAYS - 1
    )

    logger.info(
        "Log file location: %s",
        LOG_FILE
    )

    selected_date = None
    rows = None

    # Step 1: Fetch NSE data

    try:

        raw_data = fetch_nse_data()

        # Step 2: Validate NSE records

        live_records = parse_nse_records(
            raw_data
        )

        # Step 3: Select latest complete report
        # within the four-day window

        selected_date, rows = select_report(
            live_records
        )

    except Exception as error:

        logger.exception(
            "Unable to fetch or process NSE data: %s",
            error
        )

    # Step 4: Prepare Telegram message

    if selected_date is None:

        message = (

            "⚠️ <b>NSE FII/DII ALERT</b>\n\n"

            f"No complete FII/DII report was found "
            f"for today or the previous "
            f"{LOOKBACK_DAYS - 1} calendar days.\n\n"

            "No older or locally stored data has been used.\n\n"

            "<a href='https://www.nseindia.com/reports/fii-dii'>"

            "Check NSE report</a>"

        )

    else:

        message = create_message(
            selected_date,
            rows
        )

    # Step 5: Print message in execution log

    print("\n")
    print(message)

    # Step 6: SEND TELEGRAM ALERT

    send_telegram(message)

    logger.info(
        "Execution completed successfully"
    )

# ==================================================
# 12. EXECUTION
# ==================================================

if __name__ == "__main__":

    try:

        main()

    except Exception:

        logger.exception(
            "FATAL: NSE FII/DII execution failed"
        )

        raise

    finally:

        try:

            sys.stdout.flush()
            sys.stderr.flush()

        except Exception:

            pass

        # Log file is left open until Python exits.
