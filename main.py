
import requests
import datetime
import time
import os
from zoneinfo import ZoneInfo

# ----------------------------------
# CONFIGURATION
# ----------------------------------

NSE_HOME = "https://www.nseindia.com"
NSE_API = "https://www.nseindia.com/api/fiidiiTradeReact"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

IST = ZoneInfo("Asia/Kolkata")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/reports/fii-dii",
}

# ----------------------------------
# FETCH NSE DATA
# ----------------------------------

def fetch_nse_data():

    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(3):
        try:
            # Generate NSE session cookies
            session.get(NSE_HOME, timeout=20)
            time.sleep(2)

            session.get(
                "https://www.nseindia.com/reports/fii-dii",
                timeout=20
            )
            time.sleep(2)

            response = session.get(
                NSE_API,
                timeout=20
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list) or not data:
                raise ValueError("NSE returned empty or unexpected data")

            return data

        except Exception as error:
            print(f"Attempt {attempt + 1} failed: {error}")
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))

# ----------------------------------
# FORMAT NUMBERS
# ----------------------------------

def format_number(value):
    return f"{float(value):,.2f}"

# ----------------------------------
# CREATE TELEGRAM MESSAGE
# ----------------------------------

def create_message(data):

    today = datetime.datetime.now(IST).date()

    parsed = []

    for row in data:
        try:
            trade_date = datetime.datetime.strptime(
                row["date"], "%d-%b-%Y"
            ).date()

            category = row["category"].strip()

            if category not in ("DII", "FII/FPI"):
                continue

            buy = float(row["buyValue"])
            sell = float(row["sellValue"])
            net = float(row["netValue"])

            if not all(map(
                lambda x: __import__("math").isfinite(x),
                [buy, sell, net]
            )):
                continue

            # Validate net value
            if abs((buy - sell) - net) > 0.02:
                continue

            parsed.append({
                "date": trade_date,
                "category": category,
                "buy": buy,
                "sell": sell,
                "net": net
            })

        except (KeyError, ValueError, TypeError):
            continue

    # Only today's report should be sent
    rows = [r for r in parsed if r["date"] == today]

    if not rows:
        return (
            f"⚠️ <b>NSE FII/DII ALERT</b>\n\n"
            f"No fresh NSE report available for "
            f"{today.strftime('%d-%b-%Y')}.\n"
            f"Previous data will not be sent as today's data.\n\n"
            f"<a href='https://www.nseindia.com/reports/fii-dii'>"
            f"Check NSE report</a>"
        )

    # Ensure exactly one row per category
    categories = {r["category"] for r in rows}

    if categories != {"DII", "FII/FPI"} or len(rows) != 2:
        raise ValueError("Incomplete or duplicate NSE category data")

    rows.sort(
        key=lambda r: 0 if r["category"] == "DII" else 1
    )

    date_text = today.strftime("%d-%b-%Y")

    message = (
        "📊 <b>NSE FII / DII DAILY REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date: {date_text}\n"
        "📍 Capital Market Segment\n"
        "💰 Values in ₹ Crores\n\n"
        "<pre>"
        f"{'CATEGORY':<10} {'BUY':>11} {'SELL':>11} {'NET':>11}\n"
        "────────────────────────────────────────\n"
    )

    for row in rows:
        net = row["net"]
        net_text = f"{net:+,.2f}"

        message += (
            f"{row['category']:<10} "
            f"{format_number(row['buy']):>11} "
            f"{format_number(row['sell']):>11} "
            f"{net_text:>11}\n"
        )

    message += "</pre>\n"

    for row in rows:
        status = "Net Buyer 🟢" if row["net"] > 0 else (
            "Net Seller 🔴" if row["net"] < 0 else "Neutral"
        )

        message += f"\n<b>{row['category']}: </b>{status}"

    message += (
        "\n\n<a href='https://www.nseindia.com/reports/fii-dii'>"
        "Source: NSE India</a>"
    )

    return message

# ----------------------------------
# SEND TELEGRAM MESSAGE
# ----------------------------------

def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    response = requests.post(
        url,
        json=payload,
        timeout=20
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram error: {result}")

    print("Telegram alert sent successfully!")

# ----------------------------------
# MAIN PROGRAM
# ----------------------------------

if __name__ == "__main__":

    print("Fetching NSE FII/DII data...")

    data = fetch_nse_data()

    message = create_message(data)

    print(message)

    send_telegram(message)
