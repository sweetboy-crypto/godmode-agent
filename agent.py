import os
import requests
import random
from datetime import datetime

# === Telegram Config ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Account Types ===
ACCOUNT_TYPES = {
    "funded_phase1": {"balance": 5000, "risk_per_trade": 0.01, "min_conf": 85},
    "funded_phase2": {"balance": 5000, "risk_per_trade": 0.01, "min_conf": 85},
    "funded_live": {"balance": 5000, "risk_per_trade": 0.01, "min_conf": 85},
    "personal_10": {"balance": 10, "risk_per_trade": 1.0, "min_conf": 95},  # 🔥 only >=95%
}

# === Fake Market Analysis (Replace w/ Real Data) ===
def analyze_market():
    pairs = ["XAUUSD", "EURUSD", "GBPUSD"]
    pair = random.choice(pairs)

    # Random example setup
    entry = round(random.uniform(1800, 2000), 2)
    stop_loss = entry - random.uniform(2, 5)
    tp1 = entry + (entry - stop_loss) * 5
    tp2 = entry + (entry - stop_loss) * 10
    confidence = random.randint(80, 99)  # Random confidence (simulate strategy)

    return {
        "pair": pair,
        "entry": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "confidence": confidence,
    }

# === Position Sizing ===
def calculate_lot(balance, risk_per_trade, entry, stop_loss):
    risk_amount = balance * risk_per_trade
    stop_distance = abs(entry - stop_loss)
    if stop_distance == 0:
        return 0.01
    lot_size = risk_amount / stop_distance / 10  # simplified gold lot sizing
    return max(0.01, round(lot_size, 2))

# === Send to Telegram ===
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# === Main Trading Bot ===
def trading_bot():
    signal = analyze_market()

    for acc_name, acc in ACCOUNT_TYPES.items():
        if signal["confidence"] < acc["min_conf"]:
            send_telegram(f"❌ No valid trade for *{acc_name}* today. Confidence {signal['confidence']}% too low.")
            continue

        lot_size = calculate_lot(acc["balance"], acc["risk_per_trade"], signal["entry"], signal["stop_loss"])

        msg = f"""
📊 *Trade Alert for {acc_name.upper()}*
Pair: {signal['pair']}
Entry: {signal['entry']}
SL: {signal['stop_loss']}
TP1: {signal['tp1']}
TP2: {signal['tp2']}
Lot: {lot_size}
Confidence: *{signal['confidence']}%*

Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        send_telegram(msg)

if __name__ == "__main__":
    trading_bot()
