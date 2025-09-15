import os
import requests

def main():
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {"chat_id": chat_id, "text": "✅ Trading Bot test: pipeline is working!"}
    r = requests.post(url, json=payload)
    print("Telegram response:", r.json())

if __name__ == "__main__":
    main()
