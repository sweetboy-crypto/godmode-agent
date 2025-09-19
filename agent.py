import os
import requests
from datetime import datetime, timezone
from strategy import generate_signal

# -------------------------------
# Config
# -------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# Symbols to scan
WATCHLIST = ["XAU/USD", "GBPUSD", "EURUSD", "USDJPY", "NAS100"]

ACCOUNT_TYPES = ["PERSONAL_10", "PROP_PHASE1", "PROP_PHASE2", "FUNDED"]

# -------------------------------
# Utilities
# -------------------------------
def fetch_candles(symbol: str, interval: str = "15min", outputsize: int = 50):
    """
    Fetch historical candles from TwelveData.
    """
    url = f"https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": TWELVEDATA_API_KEY,
        "outputsize": outputsize,
    }
    r = requests.get(url, params=params)
    data = r.json()

    if "values" not in data:
        print(f"Error fetching data for {symbol}: {data}")
        return []

    return data["values"]


def send_telegram_message(text: str):
    """
    Send a message to Telegram channel.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


# -------------------------------
# Trading Agent Logic
# -------------------------------
def run_agent():
    """
    Main loop: fetch data → generate signals → send alerts.
    """
    for symbol in WATCHLIST:
        candles = fetch_candles(symbol)
        if not candles:
            continue

        for account in ACCOUNT_TYPES:
            signal = generate_signal(candles, account, symbol)
            if not signal:
                continue

            # Format Telegram alert
            message = f"""
🚨 *TRADE ALERT* 🚨
Account: {account}
Pair: {signal['pair']}
Bias: {signal['bias'].upper()}
Entry: {signal['entry']}
SL: {signal['sl']}
TP1: {signal['tp1']}
TP2: {signal['tp2']}
Lot Size: {signal['lot']}
Confidence: {signal['confidence']}%

⏰ Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
            """

            send_telegram_message(message.strip())
            print(f"Signal sent for {symbol} [{account}]")


if __name__ == "__main__":
    run_agent()
