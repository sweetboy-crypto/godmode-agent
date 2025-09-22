import os
import requests
import pandas as pd
from strategy import Strategy
from bot import send_alert

API_KEY = os.getenv("TWELVEDATA_API_KEY")
SYMBOLS = ["GBPJPY", "GBPUSD", "EURUSD", "XAUUSD", "BTCUSD", "ETHUSD", "USDJPY"]

def fetch_data(symbol, interval="15min", output_size=200):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={output_size}&apikey={API_KEY}"
    r = requests.get(url).json()
    if "values" not in r:
        return None
    df = pd.DataFrame(r["values"])
    df = df.rename(columns={"datetime": "time"})
    df[["open","high","low","close"]] = df[["open","high","low","close"]].astype(float)
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def calculate_lot_size(balance, risk_pct, stop_loss_pips, pip_value=10):
    risk_amount = balance * risk_pct
    lot_size = risk_amount / (pip_value * stop_loss_pips)
    return round(lot_size, 2)

def run_agent(balance=25000, risk=0.01):
    for symbol in SYMBOLS:
        df = fetch_data(symbol)
        if df is None:
            continue

        strat = Strategy(df)
        bias = strat.detect_bias()
        if bias == "Neutral":
            continue

        mss = strat.detect_mss()
        liquidity = strat.identify_liquidity()
        poi = strat.detect_poi()
        entry = strat.confirm_entry()

        if not entry:
            continue

        # --- Calculate SL/TP ---
        entry_price = df["close"].iloc[-1]
        stop_loss = poi["level"]
        sl_distance = abs(entry_price - stop_loss)
        sl_pips = max(10, int(sl_distance * 100))  # fallback min 10 pips
        lot_size = calculate_lot_size(balance, risk, sl_pips)

        if bias == "Bullish":
            tp1 = entry_price + sl_distance * 3
            tp2 = entry_price + sl_distance * 6
            tp3 = entry_price + sl_distance * 10
        else:
            tp1 = entry_price - sl_distance * 3
            tp2 = entry_price - sl_distance * 6
            tp3 = entry_price - sl_distance * 10

        # --- Send new trade alert ---
        msg = f"""
📊 [NEW TRADE SIGNAL]
Pair: {symbol}
Bias: {bias}
Entry: {entry_price:.3f}
SL: {stop_loss:.3f} ({sl_pips} pips)
TP1: {tp1:.3f}
TP2: {tp2:.3f}
TP3: {tp3:.3f}
Lot Size: {lot_size} lots (1% risk, ${balance})
"""
        send_alert(msg)

        # --- Risk management alerts ---
        # BE when price moves +1R
        be_trigger = entry_price + sl_distance if bias == "Bullish" else entry_price - sl_distance
        send_alert(f"🔔 [RISK UPDATE] {symbol}: Move SL → BE at {be_trigger:.3f}")

        # TP1 partial profit
        send_alert(f"💰 [PARTIAL PROFIT] {symbol}: TP1 at {tp1:.3f}, close 50%")

        # TP2 trailing stop
        send_alert(f"📈 [TRAILING STOP] {symbol}: TP2 at {tp2:.3f}, trail SL to lock +R")

        # TP3 exit
        send_alert(f"🚪 [FINAL EXIT] {symbol}: TP3 at {tp3:.3f}, leave market")

        # Reversal alert
        if ("Bullish" in bias and "Bearish" in mss) or ("Bearish" in bias and "Bullish" in mss):
            send_alert(f"⚠️ [REVERSAL ALERT] {symbol}: Market structure shift detected, exit trades!")

if __name__ == "__main__":
    run_agent()
