import os
import json
import requests
import pandas as pd
from datetime import datetime
from strategy import generate_signal

# --- Config ---
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
SIGNALS_FILE = "signals.json"

SYMBOLS = ["GBP/JPY", "GBP/USD", "EUR/USD", "USDJ/PY", "XAU/USD", "BTC/USD", "ETH/USD"]
ACCOUNT_BALANCE = 5000  # adjust for prop firm


# --- Save & Load ---
def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)


# --- Data Fetch ---
def fetch_ohlcv(symbol: str, interval="15min", length=100):
    """Fetch OHLCV data from TwelveData with retries and error handling."""
    # Automatically fix symbol format (e.g. GBPUSD → GBP/USD)
    if "/" not in symbol and len(symbol) == 6:
        symbol = symbol[:3] + "/" + symbol[3:]

    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": length,
        "apikey": TWELVEDATA_API_KEY,
    }

    for attempt in range(3):  # Try up to 3 times
        try:
            r = requests.get(base_url, params=params, timeout=10)
            if r.status_code != 200 or not r.text.strip():
                print(f"⚠️ Empty or bad response for {symbol} (status {r.status_code}), retrying...")
                time.sleep(2)
                continue

            data = r.json()
            if "values" not in data:
                print(f"⚠️ Invalid response format for {symbol}: {data}")
                time.sleep(2)
                continue

            df = pd.DataFrame(data["values"])
            df = df.astype({
                "open": "float",
                "high": "float",
                "low": "float",
                "close": "float",
            })
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.sort_values("datetime").reset_index(drop=True)
            return df

        except Exception as e:
            print(f"❌ Error fetching {symbol} (attempt {attempt+1}/3): {e}")
            time.sleep(2)

    print(f"🚫 Failed to fetch data for {symbol} after 3 attempts.")
    return pd.DataFrame()


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
