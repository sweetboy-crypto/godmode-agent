# agent.py
import time
import csv
import os
import requests
from datetime import datetime
from strategy import generate_trade, fetch_candles

# Load Telegram config from GitHub secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOLS = ["XAU/USD", "EUR/USD", "GBP/USD", "USD/JPY", "NDX"]

def send_telegram(message: str):
    """Send message to Telegram bot"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured properly.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def log_signal(signal):
    """Save trade signal to CSV"""
    with open("signals.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow(),
            signal["symbol"],
            signal["direction"],
            signal["entry"],
            signal["sl"],
            signal["tp1"],
            signal["tp2"],
            signal["tp3"],
            signal["confidence"]
        ])

def monitor_trade(signal):
    """Monitor price and alert milestones"""
    entry, sl, tp1, tp2, tp3 = signal["entry"], signal["sl"], signal["tp1"], signal["tp2"], signal["tp3"]

    send_telegram(
        f"📢 *New Trade Alert*\n"
        f"Pair: {signal['symbol']}\n"
        f"Direction: {signal['direction']}\n"
        f"Entry: {entry}\n"
        f"SL: {sl}\n"
        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"TP3: {tp3}\n"
        f"Confidence: {signal['confidence']}%"
    )

    while True:
        candles = fetch_candles(signal["symbol"], "1min", 2)
        price = float(candles[-1]["close"])

        if signal["direction"] == "long":
            if price >= (entry + (tp1 - entry) / 2):
                send_telegram(f"[{signal['symbol']}] 🔄 Move SL to BE @ {entry}")
            if price >= tp1:
                send_telegram(f"[{signal['symbol']}] ✅ TP1 hit! Take partials.")
            if price >= (entry + (tp2 - entry) / 2):
                send_telegram(f"[{signal['symbol']}] 🔄 Trail SL higher.")
            if price >= tp2:
                send_telegram(f"[{signal['symbol']}] ✅ TP2 hit! Secure more.")
            if price >= tp3:
                send_telegram(f"[{signal['symbol']}] 🎯 TP3 smashed! Close trade.")
                break
            if price <= sl:
                send_telegram(f"[{signal['symbol']}] ❌ SL hit. Trade invalidated.")
                break

        elif signal["direction"] == "short":
            if price <= (entry - (entry - tp1) / 2):
                send_telegram(f"[{signal['symbol']}] 🔄 Move SL to BE @ {entry}")
            if price <= tp1:
                send_telegram(f"[{signal['symbol']}] ✅ TP1 hit! Take partials.")
            if price <= (entry - (entry - tp2) / 2):
                send_telegram(f"[{signal['symbol']}] 🔄 Trail SL lower.")
            if price <= tp2:
                send_telegram(f"[{signal['symbol']}] ✅ TP2 hit! Secure more.")
            if price <= tp3:
                send_telegram(f"[{signal['symbol']}] 🎯 TP3 smashed! Close trade.")
                break
            if price >= sl:
                send_telegram(f"[{signal['symbol']}] ❌ SL hit. Trade invalidated.")
                break

        time.sleep(30)

if __name__ == "__main__":
    for symbol in SYMBOLS:
        try:
            trade = generate_trade(symbol)
            if trade:
                log_signal(trade)
                monitor_trade(trade)
            else:
                print(f"ℹ️ No valid setup for {symbol}")
        except Exception as e:
            print(f"Error with {symbol}: {e}")
