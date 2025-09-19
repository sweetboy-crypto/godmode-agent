import os
import time
import requests
from strategy import generate_signal

# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# TwelveData
API_KEY = os.getenv("TWELVEDATA_API_KEY")

PAIRS = ["GBPUSD", "EURUSD", "XAUUSD", "USDJPY"]  # monitored markets

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Telegram send failed:", e)

def fetch_price(symbol):
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={API_KEY}"
    resp = requests.get(url).json()
    if "price" in resp:
        return float(resp["price"])
    else:
        print(f"Error fetching {symbol}:", resp)
        return None

def monitor_trade(trade):
    """
    Continuously monitor trade and send updates.
    """
    entry = trade["entry"]
    sl = trade["sl"]
    tp1, tp2, tp3 = trade["tp1"], trade["tp2"], trade["tp3"]
    pair = trade["pair"]

    sl_moved = False
    partial_taken = False
    trailing_done = False

    while True:
        price = fetch_price(pair)
        if not price:
            break

        # Stop Loss hit
        if (entry > sl and price <= sl) or (entry < sl and price >= sl):
            send_telegram(f"[STOP LOSS HIT]\nPair: {pair}\nExit: {price}")
            break

        # BE condition (halfway to TP1)
        halfway_tp1 = entry + ((tp1 - entry) / 2)
        if not sl_moved and ((entry < tp1 and price >= halfway_tp1) or (entry > tp1 and price <= halfway_tp1)):
            send_telegram(f"[RISK UPDATE]\nPair: {pair}\nMove SL → Breakeven ({entry})")
            sl_moved = True

        # TP1
        if not partial_taken and ((entry < tp1 and price >= tp1) or (entry > tp1 and price <= tp1)):
            send_telegram(f"[PARTIAL PROFIT]\nPair: {pair}\nTP1 Hit @ {tp1}\nAction: Close 50%")
            partial_taken = True

        # Trailing SL halfway to TP2
        halfway_tp2 = tp1 + ((tp2 - tp1) / 2)
        if partial_taken and not trailing_done and ((entry < tp2 and price >= halfway_tp2) or (entry > tp2 and price <= halfway_tp2)):
            new_sl = tp1
            send_telegram(f"[TRAILING STOP]\nPair: {pair}\nNew SL: {new_sl}")
            trailing_done = True

        # TP2
        if ((entry < tp2 and price >= tp2) or (entry > tp2 and price <= tp2)):
            send_telegram(f"[TP2 REACHED]\nPair: {pair}\nLock profits & trail further.")
        
        # TP3
        if ((entry < tp3 and price >= tp3) or (entry > tp3 and price <= tp3)):
            send_telegram(f"[FINAL TP3 HIT]\nPair: {pair}\nMassive Win ✅\nExit: {tp3}")
            break

        time.sleep(60)  # wait 1 min before next check

def main():
    for account_type in ["PHASE_1", "PHASE_2", "FUNDED", "PERSONAL_10"]:
        for symbol in PAIRS:
            price = fetch_price(symbol)
            if not price:
                continue

            market_data = {"symbol": symbol, "close": price}
            signal = generate_signal(market_data, account_type=account_type)

            if signal:
                msg = (
                    f"[NEW TRADE SIGNAL] ({account_type})\n"
                    f"Pair: {signal['pair']}\n"
                    f"Entry: {signal['entry']}\n"
                    f"SL: {signal['sl']}\n"
                    f"TP1: {signal['tp1']}\n"
                    f"TP2: {signal['tp2']}\n"
                    f"TP3: {signal['tp3']}\n"
                    f"Lot: {signal['lot']}\n"
                    f"Confidence: {signal['confidence']}%\n"
                )
                send_telegram(msg)

                # Start monitoring
                monitor_trade(signal)

if __name__ == "__main__":
    main()
