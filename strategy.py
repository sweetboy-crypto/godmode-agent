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


def identify_directional_bias(df: pd.DataFrame):
    """Detect higher TF trend (bullish, bearish, sideways)."""
    closes = df["close"].values

    if closes[-1] > closes[-5] and closes[-5] > closes[-10]:
        return "bullish"
    elif closes[-1] < closes[-5] and closes[-5] < closes[-10]:
        return "bearish"
    return "sideways"


def detect_market_structure(df: pd.DataFrame, bias: str):
    """Check for market structure shifts (MSS/BOS)."""
    highs = df["high"].values
    lows = df["low"].values

    if bias == "bullish" and lows[-1] < lows[-3]:
        return True  # Bullish MSS
    elif bias == "bearish" and highs[-1] > highs[-3]:
        return True  # Bearish MSS
    return False


def find_liquidity_zones(df: pd.DataFrame):
    """Detect liquidity pools (equal highs/lows)."""
    liquidity = {}
    highs = df["high"].tail(10).round(3).values
    lows = df["low"].tail(10).round(3).values

    if len(set(highs)) <= 3:
        liquidity["sell_side"] = max(highs)
    if len(set(lows)) <= 3:
        liquidity["buy_side"] = min(lows)

    return liquidity


def find_poi(df: pd.DataFrame, bias: str):
    """Find POIs (OB/FVG/Breaker)."""
    last_candle = df.iloc[-2]

    if bias == "bullish":
        return {"type": "OB", "level": last_candle["low"]}
    elif bias == "bearish":
        return {"type": "OB", "level": last_candle["high"]}
    return None


def confirmation_entry(df: pd.DataFrame, poi, bias: str):
    """Check for confirmation entry at POI."""
    last = df.iloc[-1]

    if bias == "bullish" and last["low"] <= poi["level"]:
        return True
    elif bias == "bearish" and last["high"] >= poi["level"]:
        return True
    return False


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

    tp1 = entry + (entry - sl) * (3 if bias == "bullish" else -3)
    tp2 = entry + (entry - sl) * (5 if bias == "bullish" else -5)

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
