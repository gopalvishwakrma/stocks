"""
Live Doji Filter (9:15–9:20 IST)
- Reads hard-coded NSE symbol list
- Fetches tick data from NSE public JSON
- Aggregates into 5-min candle
- Filters Doji/Gravestone Doji with range <1%
- Sends an HTML-formatted email via Gmail SMTP
- Schedule via cron at 9:20 IST
"""

import os
from datetime import datetime, time as dtime
from requests import Session
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv

# ——— LOAD ENVIRONMENT VARIABLES ———
load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")       # your Gmail address
GMAIL_APP_PWD = os.getenv("GMAIL_APP_PWD")  # Gmail App Password

# ——— CONSTANTS ———
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
s.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
    "Accept-Language": "en-US,en;q=0.9",
})

# ——— CONFIGURATION ———
SYMBOLS = [
    "ABB", "ACC", "APLAPOLLO", "AUBANK", "AARTIIND", "ADANIENSOL", "ADANIENT", "ADANIGREEN",
    "ADANIPORTS", "ATGL", "ABCAPITAL", "ABFRL", "ALKEM", "AMBUJACEM", "ANGELONE", "APOLLOHOSP",
    "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA", "DMART", "AXISBANK", "BSOFT",
    "BSE", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BALKRISIND", "BANDHANBNK", "BANKBARODA",
    "BANKINDIA", "BEL", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BOSCHLTD",
    "BRITANNIA", "CESC", "CGPOWER", "CANBK", "CDSL", "CHAMBLFERT", "CHOLAFIN", "CIPLA",
    "COALINDIA", "COFORGE", "COLPAL", "CAMS", "CONCOR", "CROMPTON", "CUMMINSIND", "CYIENT",
    "DLF", "DABUR", "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DIVISLAB", "DIXON", "DRREDDY",
    "ETERNAL", "EICHERMOT", "ESCORTS", "EXIDEIND", "NYKAA", "GAIL", "GMRAIRPORT", "GLENMARK",
    "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE",
    "HFCL", "HAVELLS", "HEROMOTOCO", "HINDALCO", "HAL", "HINDCOPPER", "HINDPETRO", "HINDUNILVR",
    "HINDZINC", "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "IIFL", "IRB",
    "ITC", "INDIANB", "IEX", "IOC", "IRCTC", "IRFC", "IREDA", "IGL", "INDUSTOWER", "INDUSINDBK",
    "NAUKRI", "INFY", "INOXWIND", "INDIGO", "JSWENERGY", "JSWSTEEL", "JSL", "JINDALSTEL", "JIOFIN",
    "JUBLFOOD", "KEI", "KPITTECH", "KALYANKJIL", "KOTAKBANK", "LTF", "LICHSGFIN", "LTIM", "LT",
    "LAURUSLABS", "LICI", "LUPIN", "MRF", "LODHA", "MGL", "M&MFIN", "M&M", "MANAPPURAM", "MARICO",
    "MARUTI", "MFSL", "MAXHEALTH", "MPHASIS", "MCX", "MUTHOOTFIN", "NBCC", "NCC", "NHPC", "NMDC",
    "NTPC", "NATIONALUM", "NESTLEIND", "OBEROIRLTY", "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR",
    "PIIND", "PNBHOUSING", "PAGEIND", "PATANJALI", "PERSISTENT", "PETRONET", "PIDILITIND", "PEL",
    "POLYCAB", "POONAWALLA", "PFC", "POWERGRID", "PRESTIGE", "PNB", "RBLBANK", "RECLTD", "RELIANCE",
    "SBICARD", "SBILIFE", "SHREECEM", "SJVN", "SRF", "MOTHERSON", "SHRIRAMFIN", "SIEMENS",
    "SOLARINDS", "SONACOMS", "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND", "SYNGENE", "TATACONSUM",
    "TITAGARH", "TVSMOTOR", "TATACHEM", "TATACOMM", "TCS", "TATAELXSI", "TATAMOTORS", "TATAPOWER",
    "TATASTEEL", "TATATECH", "TECHM", "FEDERALBNK", "INDHOTEL", "PHOENIXLTD", "RAMCOCEM", "TITAN",
    "TORNTPHARM", "TORNTPOWER", "TRENT", "TIINDIA", "UPL", "ULTRACEMCO", "UNIONBANK", "UNITDSPR",
    "VBL", "VEDL", "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE", "NIFTY50"
]

# ——— FUNCTIONS ———
def fetch_ticks(symbol):
    """Return list of (datetime, price) for today from NSE public API."""
    with Session() as s:
        s.headers.update({"User-Agent": USER_AGENT})
        try:
            # Prime cookies
            prime_response = s.get(f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}")
            print(f"Prime response for {symbol}: Status {prime_response.status_code}, Content: {prime_response.text[:200]}")
            
            # Fetch chart data
            r = s.get(
                "https://www.nseindia.com/api/chart-databyindex",
                params={"index": symbol + "EQN"}
            )
            print(f"API response for {symbol}: Status {r.status_code}, Content: {r.text[:200]}")
            
            if r.status_code != 200:
                raise ValueError(f"Non-200 status code: {r.status_code}")
            
            data = r.json().get("grapthData", [])
            if not data:
                print(f"No graph data for {symbol}")
                return []
            return [(datetime.utcfromtimestamp(ts / 1000), price) for ts, price in data]
        except Exception as e:
            print(f"Error fetching ticks for {symbol}: {e}")
            return []

def aggregate_5min(ticks):
    """Aggregate ticks between 09:15 and 09:20 IST into OHLC."""
    window = [price for dt, price in ticks if dtime(9, 15) <= dt.time() < dtime(9, 20)]
    if not window:
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
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Intraday Doji Alert (9:15–9:20 IST)"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER

    html = [
        "<html><body>",
        "<p>The following stocks formed a Doji/Gravestone Doji with &lt;1% range:</p>",
        "<table border='1' cellpadding='5' cellspacing='0'>",
        "<tr><th>Symbol</th><th>Type</th><th>Range (%)</th></tr>"
    ]
    for sym, dtype, ohlc in matches:
        rng_pct = (ohlc['high'] - ohlc['low']) / ohlc['open'] * 100
        html.append(f"<tr><td>{sym}</td><td>{dtype}</td><td>{rng_pct:.2f}</td></tr>")
    html.append("</table></body></html>")

    part = MIMEText("".join(html), "html")
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PWD)
        server.send_message(msg)

# ——— MAIN EXECUTION ———
def main():
    matches = []
    for sym in SYMBOLS:
        try:
            ticks = fetch_ticks(sym)
            ohlc = aggregate_5min(ticks)
            if not ohlc:
                continue
            ok, kind = is_doji(ohlc)
            if ok and (ohlc["high"] - ohlc["low"]) / ohlc["open"] * 100 < 1:
                matches.append((sym, kind, ohlc))
        except Exception as e:
            print(f"Error processing {sym}: {e}")
    if matches:
        send_email_html(matches)

if __name__ == "__main__":
    main()
