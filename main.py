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

# Check today and the previous 3 calendar days
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

