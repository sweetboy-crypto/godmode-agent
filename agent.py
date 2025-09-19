import os
import json
import requests
from datetime import datetime, timezone
from strategy import TradingStrategy

# --- Load environment secrets ---
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- File for trade persistence ---
SIGNALS_FILE = "signals.json"

# --- Helper: Telegram Alert ---
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

# --- Helper: Load/Save signals ---
def load_signals():
    if not os.path.exists(SIGNALS_FILE):
        return []
    with open(SIGNALS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)

# --- Fetch live OHLCV data ---
def fetch_market_data(symbol, interval="1h", outputsize=200):
    url = f"https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVEDATA_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()
    if "values" not in data:
        print(f"Error fetching data for {symbol}: {data}")
        return None
    return data["values"][::-1]  # oldest → newest

# --- Main Bot Execution ---
def main():
    strategy = TradingStrategy()

    # Symbols to monitor
    symbols = ["XAU/USD", "GBPUSD", "EURUSD", "USDJPY", "NAS100"]

    signals = load_signals()
    active_signals = []

    for symbol in symbols:
        data = fetch_market_data(symbol)
        if not data:
            continue

        # Run strategy logic
        signal = strategy.find_signal(symbol, data)

        if signal:
            # Build trade message
            message = (
                f"*NEW TRADE SIGNAL*\n"
                f"Pair: {symbol}\n"
                f"Entry: {signal['entry']}\n"
                f"SL: {signal['sl']}\n"
                f"TP1 (1:3): {signal['tp1']}\n"
                f"TP2 (1:6): {signal['tp2']}\n"
                f"TP3 (1:10): {signal['tp3']}\n"
                f"Lot: {signal['lot_size']}\n"
                f"Confidence: {signal['confidence']}%\n\n"
                f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            send_telegram_message(message)

            # Save signal for monitoring
            signals.append(signal)

    # --- Manage Active Trades ---
    for signal in signals:
        # Fetch current price
        mkt = fetch_market_data(signal["symbol"], interval="1min", outputsize=5)
        if not mkt:
            continue
        current_price = float(mkt[-1]["close"])

        entry = float(signal["entry"])
        sl = float(signal["sl"])
        tp1 = float(signal["tp1"])
        tp2 = float(signal["tp2"])
        tp3 = float(signal["tp3"])

        # LONG trade monitoring
        if signal["direction"] == "BUY":
            # Breakeven alert
            if not signal.get("be_moved") and current_price >= entry + (tp1 - entry) / 2:
                send_telegram_message(f"[BE ALERT] {signal['symbol']} move SL → {entry}")
                signal["be_moved"] = True

            # TP1 hit
            if not signal.get("tp1_hit") and current_price >= tp1:
                send_telegram_message(f"[TP1 HIT] {signal['symbol']} hit TP1 @ {tp1}. Close 50%.")
                signal["tp1_hit"] = True

            # Trailing stop before TP2
            if signal.get("tp1_hit") and not signal.get("trail_active") and current_price >= entry + (tp2 - entry) / 2:
                send_telegram_message(f"[TRAILING SL] {signal['symbol']} trail SL under structure.")
                signal["trail_active"] = True

            # TP2 hit
            if not signal.get("tp2_hit") and current_price >= tp2:
                send_telegram_message(f"[TP2 HIT] {signal['symbol']} TP2 @ {tp2}. Lock more profits.")
                signal["tp2_hit"] = True

            # TP3 hit
            if not signal.get("tp3_hit") and current_price >= tp3:
                send_telegram_message(f"[TP3 HIT] {signal['symbol']} TP3 @ {tp3}. Full target achieved!")
                signal["tp3_hit"] = True

        # SHORT trade monitoring
        elif signal["direction"] == "SELL":
            if not signal.get("be_moved") and current_price <= entry - (entry - tp1) / 2:
                send_telegram_message(f"[BE ALERT] {signal['symbol']} move SL → {entry}")
                signal["be_moved"] = True

            if not signal.get("tp1_hit") and current_price <= tp1:
                send_telegram_message(f"[TP1 HIT] {signal['symbol']} hit TP1 @ {tp1}. Close 50%.")
                signal["tp1_hit"] = True

            if signal.get("tp1_hit") and not signal.get("trail_active") and current_price <= entry - (entry - tp2) / 2:
                send_telegram_message(f"[TRAILING SL] {signal['symbol']} trail SL above structure.")
                signal["trail_active"] = True

            if not signal.get("tp2_hit") and current_price <= tp2:
                send_telegram_message(f"[TP2 HIT] {signal['symbol']} TP2 @ {tp2}. Lock more profits.")
                signal["tp2_hit"] = True

            if not signal.get("tp3_hit") and current_price <= tp3:
                send_telegram_message(f"[TP3 HIT] {signal['symbol']} TP3 @ {tp3}. Full target achieved!")
                signal["tp3_hit"] = True

        active_signals.append(signal)

    # Save updated state
    save_signals(active_signals)


if __name__ == "__main__":
    main()
