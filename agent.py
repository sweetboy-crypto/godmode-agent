import os
import time
import requests
import pandas as pd
from strategy import generate_signal
from bot import send_telegram, format_signal, format_update

TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# --- Config ---
BALANCE = 5000
SYMBOLS = ["GBP/JPY", "GBP/USD", "EUR/USD", "XAU/USD", "BTC/USD", "ETH/USD", "USD/JPY"]
INTERVAL = "15min"  # for confirmation entries


def fetch_ohlcv(symbol: str, interval="15min", length=50):
    """Fetch OHLCV candles from TwelveData."""
    url = (
        f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}"
        f"&outputsize={length}&apikey={TWELVEDATA_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10).json()
        df = pd.DataFrame(r["values"])
        df = df.astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float}
        )
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Data fetch error {symbol}: {e}")
        return None


def main():
    active_signals = {}

    while True:
        for symbol in SYMBOLS:
            df = fetch_ohlcv(symbol, INTERVAL)
            if df is None:
                continue

            signal = generate_signal(df, symbol, BALANCE)
            if not signal:
                continue

            # New trade alert
            if symbol not in active_signals:
                send_telegram(format_signal(signal))
                active_signals[symbol] = signal
                continue

            # Manage active trades
            active = active_signals[symbol]
            price = df["close"].iloc[-1]

            # Move SL to BE
            if active["bias"] == "bullish" and price >= active["entry"] + (
                active["entry"] - active["sl"]
            ):
                send_telegram(format_update(active, "BE"))

            elif active["bias"] == "bearish" and price <= active["entry"] - (
                active["sl"] - active["entry"]
            ):
                send_telegram(format_update(active, "BE"))

            # TP1
            if (active["bias"] == "bullish" and price >= active["tp1"]) or (
                active["bias"] == "bearish" and price <= active["tp1"]
            ):
                send_telegram(format_update(active, "TP1"))

            # TP2 (final exit)
            if (active["bias"] == "bullish" and price >= active["tp2"]) or (
                active["bias"] == "bearish" and price <= active["tp2"]
            ):
                send_telegram(format_update(active, "TP2"))
                del active_signals[symbol]

        time.sleep(60)  # run every minute


if __name__ == "__main__":
    send_telegram("🤖 Trading Agent Started")
    main()
