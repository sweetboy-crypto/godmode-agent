# agent.py
import os
import json
import time
import requests
from datetime import datetime, timezone
from strategy import generate_trade  # your strategy.py

# --- Load secrets from GitHub Actions env ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# --- Files ---
SIGNALS_FILE = "signals.json"

# --- Symbols to monitor ---
SYMBOLS = ["GBPUSD", "EURUSD", "USDJPY", "GOLD", "NAS100"]

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

# --- Fetch OHLC candles from TwelveData ---
def get_candles(symbol, interval="15min", outputsize=50):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={TWELVEDATA_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        if "values" in r:
            candles = [
                {"open": float(c["open"]), "high": float(c["high"]),
                 "low": float(c["low"]), "close": float(c["close"])}
                for c in reversed(r["values"])
            ]
            return candles
        else:
            print(f"Error fetching {symbol} candles: {r}")
            return None
    except Exception as e:
        print(f"Price fetch error {symbol}: {e}")
        return None

# --- Generate new trades based on A+ strategy ---
def scan_for_trades():
    signals = load_signals()
    new_signals = []

    for symbol in SYMBOLS:
        # Fetch HTF (4H) and LTF (15min) candles
        htf_candles = get_candles(symbol, interval="4h", outputsize=50)
        ltf_candles = get_candles(symbol, interval="15min", outputsize=50)
        if not htf_candles or not ltf_candles:
            continue

        # Dummy POI lists (replace with real detection logic or feed)
        ob_list, bb_list, fvg_list = [], [], []

        # For each account type
        for account_type in ["personal_10", "phase1", "phase2", "funded"]:
            trade = generate_trade(symbol, htf_candles, ltf_candles, ob_list, bb_list, fvg_list, account_type)
            if trade:
                trade_dict = {
                    "pair": trade.symbol,
                    "entry": trade.entry,
                    "sl": trade.sl,
                    "tp_levels": trade.tp_levels,
                    "lot": trade.lot_size,
                    "confidence": trade.confidence,
                    "account_type": account_type,
                    "status": "open",
                    "be_moved": False,
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "tp3_hit": False,
                    "trailing": False
                }
                new_signals.append(trade_dict)

    # Merge new signals with existing
    all_signals = signals + [s for s in new_signals if s["pair"] not in [x["pair"] for x in signals]]
    save_signals(all_signals)

# --- Monitor open trades ---
def process_trades():
    signals = load_signals()
    updated = False

    for trade in signals:
        if trade.get("status") == "closed":
            continue

        symbol = trade["pair"]
        entry = float(trade["entry"])
        sl = float(trade["sl"])
        tps = trade["tp_levels"]
        direction = "long" if trade["entry"] > trade["sl"] else "short"

        price = get_candles(symbol, interval="1min", outputsize=1)
        if not price:
            continue
        price = price[-1]["close"]

        # Breakeven
        if not trade.get("be_moved") and (
            (direction == "long" and price >= entry + (sl-entry) * 1.5) or
            (direction == "short" and price <= entry - (sl-entry) * 1.5)
        ):
            send_telegram(f"📊 [BREAKEVEN ALERT]\n{symbol} → Move SL to entry {entry}")
            trade["be_moved"] = True
            updated = True

        # TP1
        if not trade.get("tp1_hit") and (
            (direction == "long" and price >= tps[0]) or
            (direction == "short" and price <= tps[0])
        ):
            send_telegram(f"✅ [PARTIAL PROFIT]\n{symbol} → TP1 hit at {tps[0]}\nClose 50%")
            trade["tp1_hit"] = True
            updated = True

        # Trailing (midway to TP2)
        midway_tp2 = (tps[0]+tps[1])/2
        if trade.get("tp1_hit") and not trade.get("trailing") and (
            (direction=="long" and price>=midway_tp2) or
            (direction=="short" and price<=midway_tp2)
        ):
            send_telegram(f"📈 [TRAILING STOP]\n{symbol} → Trail SL to secure profits")
            trade["trailing"] = True
            updated = True

        # TP2
        if not trade.get("tp2_hit") and (
            (direction == "long" and price >= tps[1]) or
            (direction == "short" and price <= tps[1])
        ):
            send_telegram(f"🎯 [TARGET 2 HIT]\n{symbol} → TP2 reached at {tps[1]}")
            trade["tp2_hit"] = True
            updated = True

        # TP3
        if not trade.get("tp3_hit") and (
            (direction == "long" and price >= tps[2]) or
            (direction == "short" and price <= tps[2])
        ):
            send_telegram(f"🏆 [FINAL TARGET]\n{symbol} → TP3 reached at {tps[2]}\nTrade closed.")
            trade["tp3_hit"] = True
            trade["status"] = "closed"
            updated = True

        # Stop loss
        if (direction == "long" and price <= sl) or (direction=="short" and price>=sl):
            send_telegram(f"⚠️ [STOP LOSS HIT]\n{symbol} → Exit trade at {sl}")
            trade["status"] = "closed"
            updated = True

    if updated:
        save_signals(signals)

# --- Main runner ---
if __name__ == "__main__":
    send_telegram(f"🤖 Trading Agent started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    scan_for_trades()
    process_trades()
