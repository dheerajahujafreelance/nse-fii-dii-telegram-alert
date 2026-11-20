
import requests
import datetime
import time
import os
import json
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

NSE_HOME = "https://www.nseindia.com"

REPORT_PAGE = (
    "https://www.nseindia.com/reports/fii-dii"
)

NSE_API = (
    "https://www.nseindia.com/api/fiidiiTradeReact"
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

IST = ZoneInfo("Asia/Kolkata")

CACHE_FILE = Path(
    os.environ.get(
        "NSE_CACHE_FILE",
        str(BASE_DIR / "nse_fii_dii_backup.json")
    )
)

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

LOG_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

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
    handlers=[
        logging.StreamHandler(sys.stderr)
    ],
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

                time.sleep(
                    5 * (attempt + 1)
                )

    raise RuntimeError("Unable to fetch NSE data")


# ==================================================
# 4. DATE VALIDATION
# ==================================================

def parse_report_date(value):

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
        "date": trade_date.isoformat(),
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
        ):

            continue

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
# 7. LOAD LOCAL JSON BACKUP
# ==================================================

def load_backup():

    if not CACHE_FILE.exists():

        logger.info(
            "No previous JSON backup found."
        )

        return []

    try:

        with CACHE_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            backup = json.load(file)

        if backup.get("version") != 1:

            raise ValueError(
                "Unsupported backup version"
            )

        reports = backup.get("reports", [])

        if not isinstance(reports, list):

            raise ValueError(
                "Invalid backup structure"
            )

        valid_records = []

        for row in reports:

            try:

                normalized = validate_record({

                    "date": row["date"],

                    "category": row["category"],

                    "buyValue": row["buy"],

                    "sellValue": row["sell"],

                    "netValue": row["net"]

                })

                valid_records.append(
                    normalized
                )

            except (
                KeyError,
                ValueError,
                TypeError
            ):

                continue

        logger.info(
            "Valid backup records loaded: %s",
            len(valid_records)
        )

        return valid_records

    except Exception:

        logger.exception(
            "Unable to read JSON backup"
        )

        return []


# ==================================================
# 8. SAVE SUCCESSFUL DATA TO JSON
# ==================================================

def save_backup(existing_records, new_records):

    old_reports = get_complete_reports(
        existing_records
    )

    new_reports = get_complete_reports(
        new_records
    )

    # Preserve all previously saved complete reports

    merged = dict(old_reports)

    # New successful NSE data takes priority
    # for the same reporting date

    merged.update(new_reports)

    output = []

    for report_date in sorted(merged):

        for row in merged[report_date]:

            output.append({

                "date": report_date.isoformat(),

                "category": row["category"],

                "buy": row["buy"],

                "sell": row["sell"],

                "net": row["net"]

            })

    backup = {

        "version": 1,

        "last_updated": datetime.datetime.now(
            IST
        ).isoformat(),

        "reports": output

    }

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_file = CACHE_FILE.with_name(
        CACHE_FILE.name + ".tmp"
    )

    try:

        with temp_file.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                backup,
                file,
                indent=4
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        # Atomic replacement protects existing backup

        os.replace(
            temp_file,
            CACHE_FILE
        )

        logger.info(
            "JSON backup successfully saved: %s",
            CACHE_FILE
        )

        logger.info(
            "Total saved records: %s",
            len(output)
        )

    finally:

        if temp_file.exists():

            temp_file.unlink()


# ==================================================
# 9. SELECT LATEST SUCCESSFUL REPORT
# ==================================================

def select_latest_report(
    live_records,
    backup_records
):

    live_reports = get_complete_reports(
        live_records
    )

    backup_reports = get_complete_reports(
        backup_records
    )

    # Start with historical backup

    available_reports = dict(
        backup_reports
    )

    # Fresh NSE data takes priority for same date

    available_reports.update(
        live_reports
    )

    if not available_reports:

        logger.error(
            "No complete successful report available"
        )

        return None, None, None

    latest_date = max(
        available_reports.keys()
    )

    selected_rows = available_reports[
        latest_date
    ]

    if latest_date in live_reports:

        source = "NSE LIVE"

    else:

        source = "LOCAL JSON BACKUP"

    logger.info(
        "Selected report date: %s",
        latest_date
    )

    logger.info(
        "Selected source: %s",
        source
    )

    return (
        latest_date,
        selected_rows,
        source
    )


# ==================================================
# 10. FORMAT NUMBERS
# ==================================================

def format_number(value):

    return f"{float(value):,.2f}"


# ==================================================
# 11. CREATE TELEGRAM MESSAGE
# ==================================================

def create_message(
    selected_date,
    rows,
    source,
    fetch_error=None
):

    today = datetime.datetime.now(IST).date()

    date_text = selected_date.strftime(
        "%d-%b-%Y"
    )

    if selected_date == today:

        if source == "NSE LIVE":

            status_text = (
                "✅ Today's NSE report available"
            )

        else:

            status_text = (
                "⚠️ Today's report retrieved from backup"
            )

    else:

        status_text = (
            "⚠️ Today's report not available.\n"
            "Showing latest successful previous report."
        )

    message = (

        "📊 <b>NSE FII / DII DAILY REPORT</b>\n"

        "━━━━━━━━━━━━━━━━━━━━\n"

        f"📅 Data Date: {date_text}\n"

        f"{status_text}\n"

        f"📂 Data Source: {source}\n"

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

    if fetch_error and source == "LOCAL JSON BACKUP":

        message += (

            "\n\n⚠️ <b>NSE API unavailable.</b>"

            "\nRetrieved data from local backup."

        )

    message += (

        "\n\n<a href='https://www.nseindia.com/reports/fii-dii'>"

        "Source: NSE India</a>"

    )

    return message


# ==================================================
# 12. SEND TELEGRAM MESSAGE
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

        # Do not expose the bot token in logs
        raise RuntimeError(
            f"Telegram delivery failed: {type(error).__name__}"
        ) from None


# ==================================================
# 13. MAIN PROGRAM
# ==================================================

def main():

    logger.info(
        "Execution time: %s",
        datetime.datetime.now(IST).strftime(
            "%d-%b-%Y %H:%M:%S IST"
        )
    )

    logger.info(
        "JSON backup location: %s",
        CACHE_FILE
    )

    logger.info(
        "Log file location: %s",
        LOG_FILE
    )

    # Step 1: Load historical backup

    backup_records = load_backup()

    live_records = []

    fetch_error = None

    # Step 2: Fetch NSE data

    try:

        raw_data = fetch_nse_data()

        live_records = parse_nse_records(
            raw_data
        )

        # Step 3: Save complete successful reports

        save_backup(
            backup_records,
            live_records
        )

    except Exception as error:

        fetch_error = type(error).__name__

        logger.error(
            "NSE fetch failed: %s",
            fetch_error
        )

        logger.info(
            "Using local backup if available."
        )

    # Step 4: Select latest successful report

    selected_date, rows, source = select_latest_report(

        live_records,

        backup_records

    )

    # Step 5: Create Telegram message

    if selected_date is None:

        message = (

            "⚠️ <b>NSE FII/DII ALERT</b>\n\n"

            "No successfully validated FII/DII "
            "report is available in NSE data "
            "or local JSON backup.\n\n"

            "<a href='https://www.nseindia.com/reports/fii-dii'>"

            "Check NSE report</a>"

        )

    else:

        message = create_message(

            selected_date,

            rows,

            source,

            fetch_error

        )

    # Step 6: Send Telegram alert

    print("\n")
    print(message)

    send_telegram(message)

    logger.info(
        "Execution completed successfully"
    )


# ==================================================
# 14. EXECUTION
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

        log_handle.flush()
        log_handle.close()
