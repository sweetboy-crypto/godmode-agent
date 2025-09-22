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
    if "values" not in r: return None
    df = pd.DataFrame(r["values"]).astype(float)
    df = df.rename(columns={"datetime": "time"})
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

        if entry:
            stop_loss = abs(df["close"].iloc[-1] - poi["level"])
            sl_pips = max(10, int(stop_loss * 100))
            lot_size = calculate_lot_size(balance, risk, sl_pips)

            msg = f"""
📊 [NEW TRADE SIGNAL]
Pair: {symbol}
Bias: {bias}
Entry: {df['close'].iloc[-1]:.3f}
SL: {poi['level']:.3f} ({sl_pips} pips)
TP1: {liquidity['liq_high'] if bias=='Bullish' else liquidity['liq_low']:.3f}
Lot Size: {lot_size} lots (1% risk, ${balance})
"""
            send_alert(msg)

if __name__ == "__main__":
    run_agent()
