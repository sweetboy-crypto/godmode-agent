import numpy as np
import pandas as pd

# --- Config ---
RISK_PER_TRADE = 0.01  # 1% per trade


# --- Utility Functions ---
def calculate_lot_size(balance_usd, sl_pips, symbol):
    """Prop firm lot sizing formula (1% risk per trade)."""
    risk_amount = balance_usd * RISK_PER_TRADE

    pip_value = 10  # Default USD pairs
    if "JPY" in symbol:
        pip_value = 6.62
    elif symbol in ["XAU/USD", "XAG/USD"]:
        pip_value = 10
    elif symbol in ["BTC/USD", "ETH/USD"]:
        pip_value = 1  # Approx, depends on broker

    lot_size = risk_amount / (pip_value * sl_pips)
    return round(lot_size, 2)

# --- Trend Bias ---
def identify_directional_bias(df: pd.DataFrame):
    closes = df["close"].values
    # EMA filter for stronger bias detection
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()
    if df["ema50"].iloc[-1] > df["ema200"].iloc[-1]:
        return "bullish"
    elif df["ema50"].iloc[-1] < df["ema200"].iloc[-1]:
        return "bearish"
    return "sideways"
    
# --- Market Structure Shift (MSS/BOS) ---
def detect_market_structure(df: pd.DataFrame, bias: str):
    """Check for market structure shifts (MSS/BOS)."""
    highs = df["high"].values
    lows = df["low"].values

    if bias == "bullish" and lows[-1] < lows[-3]:
        return True  # Bullish MSS
    elif bias == "bearish" and highs[-1] > highs[-3]:
        return True  # Bearish MSS
    return False

# --- Liquidity Pools ---
def find_liquidity_zones(df: pd.DataFrame):
    """Detect liquidity pools (equal highs/lows)."""
   liquidity = {}
    recent_highs = df["high"].tail(20).round(3)
    recent_lows = df["low"].tail(20).round(3)

    equal_highs = recent_highs.value_counts()
    equal_lows = recent_lows.value_counts()

    if equal_highs.max() >= 2:
        liquidity["sell_side"] = equal_highs.index[0]
    if equal_lows.max() >= 2:
        liquidity["buy_side"] = equal_lows.index[0]

    return liquidity

# --- POI Detection ---
def find_poi(df: pd.DataFrame, bias: str):
    last_candle = df.iloc[-2]

    # Example: Fair Value Gap detection
    if df["low"].iloc[-2] > df["high"].iloc[-3]:
        return {"type": "FVG", "level": df["low"].iloc[-2]}
    
    if bias == "bullish":
        return {"type": "OB", "level": last_candle["low"]}
    elif bias == "bearish":
        return {"type": "OB", "level": last_candle["high"]}
    return None

# --- Confirmation Entry ---
def confirmation_entry(df: pd.DataFrame, poi, bias: str):
    last = df.iloc[-1]
    if bias == "bullish":
        return last["low"] <= poi["level"] and last["close"] > last["open"]
    if bias == "bearish":
        return last["high"] >= poi["level"] and last["close"] < last["open"]
    return False

# --- Signal Generator ---
def generate_signal(df: pd.DataFrame, symbol: str, balance: float):
    """Full A+ setup detection pipeline."""
    bias = identify_directional_bias(df)
    if bias == "sideways":
        return None

    if not detect_market_structure(df, bias):
        return None

    liquidity = find_liquidity_zones(df)
    poi = find_poi(df, bias)
    if not poi:
        return None

    if not confirmation_entry(df, poi, bias):
        return None

    entry = df["close"].iloc[-1]
    sl = poi["level"]
    sl_pips = abs(entry - sl) * 100  # rough pip calc
    lot = calculate_lot_size(balance, sl_pips, symbol)
    
     rr = 3
    tp1 = entry + (entry - sl) * rr if bias == "bullish" else entry - (sl - entry) * rr
    tp2 = entry + (entry - sl) * (rr + 2) if bias == "bullish" else entry - (sl - entry) * (rr + 2)

    return {
        "symbol": symbol,
        "bias": bias,
        "entry": round(entry, 3),
        "sl": round(sl, 3),
        "tp1": round(tp1, 3),
        "tp2": round(tp2, 3),
        "lot": lot,
        "liquidity": liquidity,
        "poi": poi,
    }
