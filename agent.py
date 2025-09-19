import os
import requests
import pandas as pd
from datetime import datetime
from strategy import generate_signal

# Get API key from GitHub Secrets
API_KEY = os.getenv("TWELVEDATA_API_KEY")

# ✅ Use correct TwelveData symbols
symbols = ["XAU/USD", "GBP/USD", "EUR/USD", "USD/JPY", "NDX"]

# CSV file to save signals
SIGNAL_FILE = "signals.csv"


def fetch_candles(symbol, interval="15min", outputsize=200):
    """
    Fetch recent OHLCV candles from TwelveData.
    """
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={API_KEY}"
    )
    try:
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            print(f"❌ Error fetching {symbol}: {data}")
            return None

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)

        print(f"✅ {symbol} → fetched {len(df)} candles ({interval})")
        return df

    except Exception as e:
        print(f"⚠️ Exception fetching {symbol}: {e}")
        return None


def save_signal(signal):
    """
    Save signal to CSV file.
    """
    new_entry = pd.DataFrame([signal])
    if os.path.exists(SIGNAL_FILE):
        df = pd.read_csv(SIGNAL_FILE)
        df = pd.concat([df, new_entry], ignore_index=True)
    else:
        df = new_entry
    df.to_csv(SIGNAL_FILE, index=False)
    print(f"💾 Saved signal: {signal['pair']} @ {signal['entry']}")


def main():
    """
    Main agent loop: fetch data, run strategy, save signal.
    """
    for symbol in symbols:
        df = fetch_candles(symbol, interval="15min", outputsize=200)
        if df is None:
            continue

        signal = generate_signal(df, symbol)

        if signal:
            save_signal(signal)
        else:
            print(f"ℹ️ No signal for {symbol} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")


if __name__ == "__main__":
    main()
