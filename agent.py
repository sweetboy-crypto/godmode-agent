import os
import json
import requests
import pandas as pd
from datetime import datetime
from strategy import generate_signal

# --- Config ---
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
SIGNALS_FILE = "signals.json"

SYMBOLS = ["GBPJPY", "GBPUSD", "EURUSD", "USDJPY", "XAU/USD", "BTC/USD", "ETH/USD"]
ACCOUNT_BALANCE = 25000  # adjust for prop firm


# --- Save & Load ---
def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)


# --- Data Fetch ---
def fetch_ohlcv(symbol, interval="15min", length=50):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={length}&apikey={TWELVEDATA_API_KEY}"
    r = requests.get(url, timeout=10).json()

    if "values" not in r:
        return None

    df = pd.DataFrame(r["values"])
    df = df.rename(columns={"datetime": "time"})
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df = df.iloc[::-1].reset_index(drop=True)  # chronological
    return df


# --- Main Agent ---
def run_agent():
    all_signals = []

    for symbol in SYMBOLS:
        df = fetch_ohlcv(symbol, interval="15min", length=100)
        if df is None:
            continue

        signal = generate_signal(df, symbol, ACCOUNT_BALANCE)
        if signal:
            signal["time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            all_signals.append(signal)

    if all_signals:
        save_signals(all_signals)
        print(f"✅ {len(all_signals)} signals saved.")
    else:
        print("⚠️ No valid A+ setups found.")


if __name__ == "__main__":
    run_agent()
