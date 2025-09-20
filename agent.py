# agent.py
import os
import json
import time
from datetime import datetime, timezone
import requests
from strategy import generate_trade, fetch_live_candles

# --- Load secrets ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")

# --- Files ---
SIGNALS_FILE = "signals.json"

# --- RR targets ---
TP_RR = {"TP1": 3, "TP2": 6, "TP3": 10}

# --- Telegram ---
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

# --- Fetch latest price ---
def get_price(symbol: str):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVEDATA_API_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        return float(r.get("price")) if "price" in r else None
    except Exception as e:
        print(f"Price fetch error {symbol}: {e}")
        return None

# --- Main trading loop ---
def run_trading_agent(symbols, account_type="phase1"):
    signals = load_signals()
    new_trades = []

    for symbol in symbols:
        # Fetch HTF and LTF candles
        htf_candles = fetch_live_candles(symbol, interval="1h", api_key=TWELVEDATA_API_KEY)
        ltf_candles = fetch_live_candles(symbol, interval="15min", api_key=TWELVEDATA_API_KEY)
        if not htf_candles or not ltf_candles:
            print(f"No candles for {symbol}")
            continue

        # Generate trade
        trade = generate_trade(symbol, htf_candles, ltf_candles, account_type)
        if trade:
            # Avoid duplicates
            if not any(t["pair"] == trade.symbol for t in signals):
                trade_dict = {
                    "pair": trade.symbol,
                    "entry": trade.entry,
                    "sl": trade.sl,
                    "tp_levels": trade.tp_levels,
                    "lot": trade.lot_size,
                    "direction": trade.direction,
                    "confidence": trade.confidence,
                    "status": "open",
                    "be_moved": False,
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "tp3_hit": False,
                    "trailing": False
                }
                signals.append(trade_dict)
                new_trades.append(trade_dict)
    
    if new_trades:
        save_signals(signals)
        for t in new_trades:
            send_telegram(f"🚀 [NEW TRADE SIGNAL]\nPair: {t['pair']}\nDir: {t['direction']}\nEntry: {t['entry']}\nSL: {t['sl']}\nTP1: {t['tp_levels'][0]}\nTP2: {t['tp_levels'][1]}\nTP3: {t['tp_levels'][2]}\nLot: {t['lot']}\nConfidence: {t['confidence']}%")

# --- Monitor trades ---
def monitor_trades():
    signals = load_signals()
    updated = False

    for trade in signals:
        if trade.get("status") == "closed":
            continue

        symbol = trade["pair"]
        price = get_price(symbol)
        if not price:
            continue

        entry = trade["entry"]
        sl = trade["sl"]
        tp1, tp2, tp3 = trade["tp_levels"]
        direction = trade["direction"]

        # Breakeven alert
        if not trade.get("be_moved"):
            if (direction=="buy" and price >= entry + (tp1-entry)/2) or (direction=="sell" and price <= entry - (entry-tp1)/2):
                send_telegram(f"📊 [BREAKEVEN ALERT]\n{symbol} → Move SL to entry {entry}")
                trade["be_moved"] = True
                updated = True

        # Partial profit
        if not trade.get("tp1_hit"):
            if (direction=="buy" and price >= tp1) or (direction=="sell" and price <= tp1):
                send_telegram(f"✅ [PARTIAL PROFIT]\n{symbol} → TP1 hit at {tp1}\nClose 50%")
                trade["tp1_hit"] = True
                updated = True

        # Trailing stop (midway to TP2)
        midway_tp2 = (tp1 + tp2)/2
        if trade.get("tp1_hit") and not trade.get("trailing"):
            if (direction=="buy" and price >= midway_tp2) or (direction=="sell" and price <= midway_tp2):
                new_sl = entry if direction=="buy" else entry
                send_telegram(f"📈 [TRAILING STOP]\n{symbol} → Trail SL to {new_sl}")
                trade["trailing"] = True
                updated = True

        # TP2
        if not trade.get("tp2_hit"):
            if (direction=="buy" and price >= tp2) or (direction=="sell" and price <= tp2):
                send_telegram(f"🎯 [TARGET 2 HIT]\n{symbol} → TP2 reached at {tp2}")
                trade["tp2_hit"] = True
                updated = True

        # TP3 (final)
        if not trade.get("tp3_hit"):
            if (direction=="buy" and price >= tp3) or (direction=="sell" and price <= tp3):
                send_telegram(f"🏆 [FINAL TARGET]\n{symbol} → TP3 reached at {tp3}\nTrade closed.")
                trade["tp3_hit"] = True
                trade["status"] = "closed"
                updated = True

        # Stop loss / reversal
        if (direction=="buy" and price <= sl) or (direction=="sell" and price >= sl):
            send_telegram(f"⚠️ [STOP LOSS HIT]\n{symbol} → Exit trade at {sl}")
            trade["status"] = "closed"
            updated = True

    if updated:
        save_signals(signals)

# --- Main ---
if __name__ == "__main__":
    symbols = ["GBPUSD", "EURUSD", "USDJPY", "XAUUSD"]  # add any symbols
    send_telegram(f"🤖 Trading Agent started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # Run every X seconds
    while True:
        try:
            run_trading_agent(symbols, account_type="phase1")
            monitor_trades()
            time.sleep(60)  # check every minute
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)
