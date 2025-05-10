import os
import time
from datetime import datetime, time as dtime
from requests import Session
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PWD = os.getenv("GMAIL_APP_PWD")

if not GMAIL_USER or not GMAIL_APP_PWD:
    logger.error("Gmail credentials not set in environment variables")
    raise ValueError("GMAIL_USER and GMAIL_APP_PWD must be set")

# --- CONSTANTS ---
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

SYMBOLS = [
    "ABB", "ACC", "APLAPOLLO", "AUBANK", "AARTIIND", "ADANIENSOL", "ADANIENT", "ADANIGREEN",
]

# --- FUNCTIONS ---
def create_session():
    """Create a requests Session with retry logic."""
    session = Session()
    session.headers.update(HEADERS)
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    return session

def fetch_ticks(symbol, retries=3):
    """Return list of (datetime, price) for today from NSE public API."""
    for attempt in range(retries):
        with create_session() as s:
            try:
                # Prime cookies
                prime_url = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
                prime_response = s.get(prime_url, timeout=10)
                logger.info(
                    f"Prime {symbol}: Status {prime_response.status_code}, "
                    f"Content: {prime_response.text[:100]}"
                )
                if prime_response.status_code != 200:
                    logger.warning(f"Prime failed for {symbol}: Status {prime_response.status_code}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue

                # Fetch chart data
                api_url = "https://www.nseindia.com/api/chart-databyindex"
                params = {"index": symbol + "EQN"}
                response = s.get(api_url, params=params, timeout=10)
                logger.info(
                    f"API {symbol}: Status {response.status_code}, "
                    f"Content: {response.text[:100]}"
                )

                if response.status_code == 429:
                    logger.warning(f"Rate limit hit for {symbol}. Retrying after delay...")
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code != 200:
                    logger.error(f"API failed for {symbol}: Status {response.status_code}")
                    return []

                try:
                    data = response.json().get("grapthData", [])
                    if not data:
                        logger.info(f"No graph data for {symbol}")
                        return []
                    return [(datetime.utcfromtimestamp(ts / 1000), price) for ts, price in data]
                except ValueError as e:
                    logger.error(f"JSON parse error for {symbol}: {e}")
                    time.sleep(2 ** attempt)
                    continue
            except Exception as e:
                logger.error(f"Request error for {symbol}: {e}")
                time.sleep(2 ** attempt)
                continue
        time.sleep(1)  # Delay between retries
    logger.error(f"Failed to fetch ticks for {symbol} after {retries} attempts")
    return []

def aggregate_5min(ticks):
    """Aggregate ticks between 09:15 and 09:20 IST into OHLC."""
    window = [price for dt, price in ticks if dtime(9, 15) <= dt.time() < dtime(9, 20)]
    if not window:
        logger.info("No ticks in 9:15–9:20 window")
        return None
    return {
        "open": window[0],
        "high": max(window),
        "low": min(window),
        "close": window[-1]
    }

def is_doji(ohlc, body_thresh=0.1):
    """Check if the given OHLC represents a Doji or Gravestone Doji."""
    o, h, l, c = ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"]
    body = abs(c - o)
    rng = h - l
    if rng <= 0 or body / rng > body_thresh:
        return False, None
    lower_sh = min(o, c) - l
    upper_sh = h - max(o, c)
    if lower_sh <= body * 1.5 and upper_sh >= body * 2:
        return True, "Gravestone Doji"
    return True, "Doji"

def send_email_html(matches):
    """Send HTML email listing matching stocks in a table."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Intraday Doji Alert (9:15–9:20 IST)"
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER

        html = [
            "<html><body>",
            "<p>The following stocks formed a Doji/Gravestone Doji with <1% range:</p>",
            "<table border='1' cellpadding='5' cellspacing='0'>",
            "<tr><th>Symbol</th><th>Type</th><th>Range (%)</th></tr>"
        ]
        for sym, dtype, ohlc in matches:
            rng_pct = (ohlc['high'] - ohlc['low']) / ohlc['open'] * 100
            html.append(f"<tr><td>{sym}</td><td>{dtype}</td><td>{rng_pct:.2f}</td></tr>")
        html.append("</table></body></html>")

        part = MIMEText("".join(html), "html")
        msg.attach(part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_APP_PWD)
            server.send_message(msg)
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

# --- MAIN EXECUTION ---
def main():
    matches = []
    for i, sym in enumerate(SYMBOLS):
        logger.info(f"Processing {sym}")
        ticks = fetch_ticks(sym)
        ohlc = aggregate_5min(ticks)
        if not ohlc:
            logger.info(f"No OHLC data for {sym}")
            continue
        ok, kind = is_doji(ohlc)
        if ok and (ohlc["high"] - ohlc["low"]) / ohlc["open"] * 100 < 1:
            matches.append((sym, kind, ohlc))
            logger.info(f"Match found for {sym}: {kind}")
        time.sleep(2)  # Delay to avoid rate limits
    if matches:
        logger.info(f"Sending email with {len(matches)} matches")
        send_email_html(matches)
    else:
        logger.info("No matches found, no email sent")

if __name__ == "__main__":
    main()
