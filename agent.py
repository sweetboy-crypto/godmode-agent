import os
import json
import time
import requests
from datetime import datetime, timezone

# --- Load secrets from GitHub Actions env ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# --- Files ---
SIGNALS_FILE = "signals.json"

# --- Constants for RR targets ---
TP_RR = {
    "TP1": 3,   # 1:3 RR
    "TP2": 6,   # 1:6 RR
    "TP3": 10   # 1:10 RR
}

# --- Telegram sender ---
def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

# --- Load/save signals ---
def load_signals():
    if not os.path.exists(SIGNALS_FILE):
        return []
    with open(SIGNALS_FILE, "r") as f:
        return json.load(f)

def save_signals(signals):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2)

# --- Fetch latest price from TwelveData ---
def get_price(symbol: str):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVEDATA_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        if "price" in r:
            return float(r["price"])
        else:
            print(f"Error fetching {symbol}: {r}")
            return None
    except Exception as e:
        print(f"Price fetch error {symbol}: {e}")
        return None

# --- Update trades with live monitoring ---
def process_trades():
    signals = load_signals()
    updated = False

    for trade in signals:
        if trade.get("status") == "closed":
            continue  # skip closed trades

        symbol = trade["pair"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        risk = abs(entry - sl)
        direction = "long" if entry > sl else "short"

        price = get_price(symbol)
        if not price:
            continue

        # --- Define targets dynamically ---
        if direction == "long":
            tp1 = entry + risk * TP_RR["TP1"]
            tp2 = entry + risk * TP_RR["TP2"]
            tp3 = entry + risk * TP_RR["TP3"]
        else:
            tp1 = entry - risk * TP_RR["TP1"]
            tp2 = entry - risk * TP_RR["TP2"]
            tp3 = entry - risk * TP_RR["TP3"]

        trade.setdefault("tp1", tp1)
        trade.setdefault("tp2", tp2)
        trade.setdefault("tp3", tp3)

        # --- Check conditions ---
        # Breakeven alert
        if not trade.get("be_moved") and (
            (direction == "long" and price >= entry + risk * 1.5) or
            (direction == "short" and price <= entry - risk * 1.5)
        ):
            send_telegram(f"📊 [BREAKEVEN ALERT]\n{symbol} → Move SL to entry {entry}")
            trade["be_moved"] = True
            updated = True

        # Partial profit (TP1)
        if not trade.get("tp1_hit") and (
            (direction == "long" and price >= tp1) or
            (direction == "short" and price <= tp1)
        ):
            send_telegram(f"✅ [PARTIAL PROFIT]\n{symbol} → TP1 hit at {tp1}\nClose 50%")
            trade["tp1_hit"] = True
            updated = True

        # Trailing stop (midway to TP2)
        midway_tp2 = (tp1 + tp2) / 2 if direction == "long" else (tp1 + tp2) / 2
        if trade.get("tp1_hit") and not trade.get("trailing") and (
            (direction == "long" and price >= midway_tp2) or
            (direction == "short" and price <= midway_tp2)
        ):
            send_telegram(f"📈 [TRAILING STOP]\n{symbol} → Trail SL to secure profits")
            trade["trailing"] = True
            updated = True

        # TP2
        if not trade.get("tp2_hit") and (
            (direction == "long" and price >= tp2) or
            (direction == "short" and price <= tp2)
        ):
            send_telegram(f"🎯 [TARGET 2 HIT]\n{symbol} → TP2 reached at {tp2}")
            trade["tp2_hit"] = True
            updated = True

        # TP3 (final)
        if not trade.get("tp3_hit") and (
            (direction == "long" and price >= tp3) or
            (direction == "short" and price <= tp3)
        ):
            send_telegram(f"🏆 [FINAL TARGET]\n{symbol} → TP3 reached at {tp3}\nTrade closed.")
            trade["tp3_hit"] = True
            trade["status"] = "closed"
            updated = True

        # Reversal (back to SL)
        if (direction == "long" and price <= sl) or (direction == "short" and price >= sl):
            send_telegram(f"⚠️ [STOP LOSS HIT]\n{symbol} → Exit trade at {sl}")
            trade["status"] = "closed"
            updated = True

    if updated:
        save_signals(signals)

# --- Main runner ---
if __name__ == "__main__":
    send_telegram(f"🤖 Trading Agent started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    process_trades()
