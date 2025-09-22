import os
import json
import requests
from time import sleep

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SIGNALS_FILE = "signals.json"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def format_signal(sig):
    return (
        f"*NEW TRADE SIGNAL*\n"
        f"Pair: {sig['symbol']}\n"
        f"Bias: {sig['bias'].capitalize()}\n"
        f"Entry: {sig['entry']}\n"
        f"SL: {sig['sl']}\n"
        f"TP1: {sig['tp1']}\n"
        f"TP2: {sig['tp2']}\n"
        f"Lot Size (1% Risk): {sig['lot']}\n"
        f"Liquidity: {sig['liquidity']}\n"
        f"POI: {sig['poi']}\n"
        f"Time: {sig['time']}"
    )


def run_bot():
    while True:
        try:
            with open(SIGNALS_FILE, "r") as f:
                signals = json.load(f)
        except FileNotFoundError:
            signals = []

        if signals:
            for sig in signals:
                msg = format_signal(sig)
                send_telegram(msg)

            # clear signals after sending
            open(SIGNALS_FILE, "w").write("[]")

        sleep(60)  # check every 1 min


if __name__ == "__main__":
    run_bot()
