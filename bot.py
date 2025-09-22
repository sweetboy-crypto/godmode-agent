import os
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramBot:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def send_message(self, text: str, parse_mode="Markdown"):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode
        }
        try:
            r = requests.post(self.base_url, data=payload)
            return r.json()
        except Exception as e:
            print(f"[ERROR] Telegram send failed: {e}")
            return None

    # --- Send trade signal ---
    def send_trade_signal(self, symbol, timeframe, bias, mss, liquidity, poi, confirm, confidence):
        time_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        msg = f"""
📊 *Trading Signal Alert*  
━━━━━━━━━━━━━━━  
**Pair:** {symbol}  
**Timeframe:** {timeframe}  
**Bias:** {bias}  
**MSS/BOS:** {mss if mss else "None"}  
**Liquidity:** {", ".join([l['type'] for l in liquidity]) if liquidity else "None"}  
**POI:** {poi['type']} @ {round(poi['level'], 5)} if poi else "None"  
**Confirmation:** {confirm if confirm else "None"}  
━━━━━━━━━━━━━━━  
🔥 *Confidence Score:* {confidence}%  
⏰ {time_now}  
        """
        self.send_message(msg)

    # --- Send trade management update ---
    def send_trade_update(self, symbol, status, price):
        time_now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = f"""
⚡ *Trade Update*  
━━━━━━━━━━━━━━━  
**Pair:** {symbol}  
**Status:** {status}  
**Price:** {price}  
⏰ {time_now}  
        """
        self.send_message(msg)
