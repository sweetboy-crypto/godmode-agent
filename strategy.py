# strategy.py
import requests
import os
import numpy as np

API_KEY = os.getenv("TWELVEDATA_API_KEY")
BASE_URL = "https://api.twelvedata.com"

def fetch_candles(symbol, interval="15min", outputsize=100):
    """Fetch OHLC candles from TwelveData"""
    url = f"{BASE_URL}/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize
    }
    r = requests.get(url, params=params)
    data = r.json()
    if "values" not in data:
        raise ValueError(f"Error fetching {symbol}: {data}")
    candles = list(reversed(data["values"]))  # oldest → newest
    return candles

def get_bias(candles_1h):
    """Simple HTF bias: bullish if price above 50 EMA, bearish otherwise"""
    closes = np.array([float(c["close"]) for c in candles_1h], dtype=float)
    ema50 = np.mean(closes[-50:])
    return "bullish" if closes[-1] > ema50 else "bearish"

def detect_liquidity_grab(candles_15m):
    """Detect liquidity sweeps: wick > prev high/low then close back inside"""
    last = candles_15m[-1]
    prev = candles_15m[-2]

    high, low, close = float(last["high"]), float(last["low"]), float(last["close"])
    prev_high, prev_low = float(prev["high"]), float(prev["low"])

    if high > prev_high and close < prev_high:
        return "swept_high"
    elif low < prev_low and close > prev_low:
        return "swept_low"
    return None

def generate_trade(symbol):
    """Generate trade setup using playbook rules"""
    candles_1h = fetch_candles(symbol, "1h", 100)
    candles_15m = fetch_candles(symbol, "15min", 200)

    bias = get_bias(candles_1h)
    sweep = detect_liquidity_grab(candles_15m)

    entry_candle = candles_15m[-1]
    entry = float(entry_candle["close"])

    if bias == "bullish" and sweep == "swept_low":
        sl = float(entry_candle["low"])
        rr = entry - sl
        return {
            "symbol": symbol,
            "direction": "long",
            "entry": entry,
            "sl": sl,
            "tp1": entry + 3 * rr,
            "tp2": entry + 6 * rr,
            "tp3": entry + 10 * rr,
            "confidence": 90
        }
    elif bias == "bearish" and sweep == "swept_high":
        sl = float(entry_candle["high"])
        rr = sl - entry
        return {
            "symbol": symbol,
            "direction": "short",
            "entry": entry,
            "sl": sl,
            "tp1": entry - 3 * rr,
            "tp2": entry - 6 * rr,
            "tp3": entry - 10 * rr,
            "confidence": 90
        }
    else:
        return None
