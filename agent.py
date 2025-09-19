import os
import requests
import pandas as pd
from datetime import datetime
from strategy import TradingStrategy

# Load secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

SYMBOLS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "NAS100", "BTC/USD"]

# Active trades memory
ACTIVE_TRADES = {}

def fetch_data(symbol, interval, outputsize=100):
    url = f"https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "apikey": TWELVEDATA_API_KEY, "outputsize": outputsize}
    r = requests.get(url, params=params)
    data = r.json()
    if "values" not in data:
        print(f"Error fetching {symbol}: {data}")
        return None
    df = pd.DataFrame(data["values"])
    df = df.rename(columns={"datetime": "date"})
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
    df = df[::-1].reset_index(drop=True)
    return df

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def check_trade_updates(symbol, signal, current_price):
    """
    Manage trade updates (BE, partials, trailing, exit)
    """
    entry, sl, tp1, tp2, tp3 = signal["entry"], signal["sl"], signal["tp1"], signal["tp2"], signal["tp3"]
    bias = signal["bias"]
    trade_id = f"{symbol}_{entry}"

    if trade_id not in ACTIVE_TRADES:
        ACTIVE_TRADES[trade_id] = {"status": "active", "last_update": None}

    # Halfway to TP1 → Move SL to BE
    if signal["status"] == "new" and ((bias == "bullish" and current_price >= (entry + (tp1 - entry)/2)) or (bias == "bearish" and current_price <= (entry - (entry - tp1)/2))):
        send_telegram(f"⚡ {symbol}: Price halfway to TP1 → Move SL to BE")
        signal["status"] = "BE"

    # TP1 Hit → Take partials
    if current_price >= tp1 if bias == "bullish" else current_price <= tp1:
        send_telegram(f"✅ {symbol}: TP1 hit → Take partials")
        signal["status"] = "TP1"

    # Halfway to TP2 → Trail SL
    if signal["status"] == "TP1" and ((bias == "bullish" and current_price >= (tp1 + (tp2 - tp1)/2)) or (bias == "bearish" and current_price <= (tp1 - (tp1 - tp2)/2))):
        send_telegram(f"⚡ {symbol}: Halfway to TP2 → Trail SL")
        signal["status"] = "trail"

    # TP2 Hit
    if current_price >= tp2 if bias == "bullish" else current_price <= tp2:
        send_telegram(f"✅ {symbol}: TP2 hit → Lock more profits, hold for TP3")
        signal["status"] = "TP2"

    # TP3 Hit
    if current_price >= tp3 if bias == "bullish" else current_price <= tp3:
        send_telegram(f"🏆 {symbol}: TP3 hit → Close remaining position")
        signal["status"] = "TP3"

    # Reversal (price back to entry after TP1)
    if signal["status"] in ["TP1", "trail"] and ((bias == "bullish" and current_price < entry) or (bias == "bearish" and current_price > entry)):
        send_telegram(f"⚠️ {symbol}: Market reversal → Exit trade!")
        signal["status"] = "exit"

def main():
    strategy = TradingStrategy()
    account_balance = 10000

    for symbol in SYMBOLS:
        df_daily = fetch_data(symbol, "1day")
        df_4h = fetch_data(symbol, "4h")
        df_1h = fetch_data(symbol, "1h")
        if df_daily is None or df_4h is None or df_1h is None:
            continue

        signal = strategy.generate_signal(df_daily, df_4h, df_1h, symbol, account_balance)
        if signal:
            msg = (
                f"📊 *A+ Setup Found!*\n\n"
                f"Pair: {signal['pair']}\n"
                f"Bias: {signal['bias'].upper()}\n"
                f"Entry: {signal['entry']}\n"
                f"SL: {signal['sl']}\n"
                f"TP1: {signal['tp1']}\n"
                f"TP2: {signal['tp2']}\n"
                f"TP3: {signal['tp3']}\n"
                f"Lot: {signal['lot']}\n"
                f"Confidence: {signal['confidence']}%\n\n"
                f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            send_telegram(msg)

            # Monitor live price
            current_price = df_1h['close'].values[-1]
            check_trade_updates(symbol, signal, current_price)
