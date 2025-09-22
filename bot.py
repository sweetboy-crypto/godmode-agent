import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message: str):
    """Send message to Telegram bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def format_signal(signal: dict):
    """Format new trade signal alert."""
    return (
        f"📊 *NEW TRADE SIGNAL*\n\n"
        f"Pair: {signal['symbol']}\n"
        f"Bias: {signal['bias'].upper()}\n"
        f"Entry: {signal['entry']}\n"
        f"SL: {signal['sl']}\n"
        f"TP1: {signal['tp1']}\n"
        f"TP2: {signal['tp2']}\n"
        f"Lot Size: {signal['lot']} lots\n\n"
        f"POI: {signal['poi']}\n"
        f"Liquidity: {signal['liquidity']}"
    )


def format_update(signal: dict, update_type: str):
    """Format trade management updates."""
    if update_type == "BE":
        return f"🔒 [RISK UPDATE]\n{signal['symbol']} → Move SL to BE ({signal['entry']})"
    elif update_type == "TP1":
        return f"✅ [PARTIAL PROFIT]\n{signal['symbol']} TP1 Hit @ {signal['tp1']}"
    elif update_type == "TP2":
        return f"🏆 [FULL TP]\n{signal['symbol']} TP2 Hit @ {signal['tp2']}"
    elif update_type == "EXIT":
        return f"⚠️ [MARKET REVERSAL]\nExit {signal['symbol']} immediately!"
    return None
