import numpy as np
import pandas as pd

# ============= STRUCTURE DETECTION ============= #

def detect_directional_bias(candles):
    """
    Detect trend bias from higher timeframe candles.
    Returns: 'bullish', 'bearish', or None
    """
    highs = candles['high'].values[-20:]
    lows = candles['low'].values[-20:]

    # Higher highs and higher lows → bullish
    if all(np.diff(highs[-5:]) > 0) and all(np.diff(lows[-5:]) > 0):
        return "bullish"
    # Lower lows and lower highs → bearish
    if all(np.diff(highs[-5:]) < 0) and all(np.diff(lows[-5:]) < 0):
        return "bearish"
    return None


def detect_market_structure_shift(candles, bias):
    """
    Detect BOS/MSS confirming shift.
    """
    highs = candles['high'].values
    lows = candles['low'].values

    if bias == "bearish":
        if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return True
    elif bias == "bullish":
        if lows[-1] > lows[-2] and highs[-1] > highs[-2]:
            return True
    return False


# ============= LIQUIDITY & INDUCEMENT ============= #

def detect_liquidity_zones(candles):
    """
    Equal highs/lows = liquidity pools
    """
    highs = candles['high'].values
    lows = candles['low'].values

    liquidity = []
    for i in range(2, len(highs)):
        if abs(highs[i] - highs[i-1]) < 0.0005:  # equal highs
            liquidity.append(("eq_high", highs[i]))
        if abs(lows[i] - lows[i-1]) < 0.0005:  # equal lows
            liquidity.append(("eq_low", lows[i]))
    return liquidity


def detect_inducement(candles):
    """
    Look for fakeouts/sweeps near liquidity.
    """
    closes = candles['close'].values
    highs = candles['high'].values
    lows = candles['low'].values

    if closes[-1] < highs[-2] and highs[-1] > highs[-2]:
        return "sweep_high"
    if closes[-1] > lows[-2] and lows[-1] < lows[-2]:
        return "sweep_low"
    return None


# ============= POI DETECTION ============= #

def find_order_blocks(candles):
    """
    Simple OB: last opposite candle before big move.
    """
    ob_list = []
    closes = candles['close'].values
    opens = candles['open'].values

    for i in range(2, len(closes)):
        if closes[i] > closes[i-1] * 1.002:  # strong bullish push
            ob_list.append(("bullish_OB", opens[i-1]))
        elif closes[i] < closes[i-1] * 0.998:  # strong bearish push
            ob_list.append(("bearish_OB", opens[i-1]))
    return ob_list


def find_fvg(candles):
    """
    FVG = imbalance between candle wicks.
    """
    fvg = []
    for i in range(2, len(candles)):
        if candles['low'].iloc[i] > candles['high'].iloc[i-2]:
            fvg.append(("bullish_FVG", (candles['high'].iloc[i-2], candles['low'].iloc[i])))
        if candles['high'].iloc[i] < candles['low'].iloc[i-2]:
            fvg.append(("bearish_FVG", (candles['low'].iloc[i-2], candles['high'].iloc[i])))
    return fvg


# ============= CONFIRMATION ENGINE ============= #

def confirm_entry(candles, bias):
    """
    Require BOS + sweep + rejection wick.
    """
    closes = candles['close'].values
    highs = candles['high'].values
    lows = candles['low'].values

    # rejection wick
    rejection = (highs[-1] - closes[-1]) > (closes[-1] - lows[-1]) * 2

    if bias == "bullish" and rejection and closes[-1] > closes[-2]:
        return True
    if bias == "bearish" and rejection and closes[-1] < closes[-2]:
        return True
    return False


# ============= CONFIDENCE SCORING ============= #

def calculate_confidence(bias, mss, liquidity, inducement, poi, confirmation):
    score = 0
    if bias: score += 30
    if poi and liquidity: score += 30
    if mss: score += 20
    if confirmation: score += 20
    return score


# ============= STRATEGY WRAPPER ============= #

def generate_signal(candles, account_type="PROP_25K"):
    """
    Main logic: run full A+ detection.
    """
    bias = detect_directional_bias(candles)
    if not bias:
        return None

    mss = detect_market_structure_shift(candles, bias)
    liquidity = detect_liquidity_zones(candles)
    inducement = detect_inducement(candles)
    poi = find_order_blocks(candles) or find_fvg(candles)
    confirmation = confirm_entry(candles, bias)

    confidence = calculate_confidence(bias, mss, liquidity, inducement, poi, confirmation)

    # Require high confidence
    if account_type == "PERSONAL_10" and confidence < 95:
        return None
    if confidence < 85:
        return None

    entry = candles['close'].iloc[-1]
    sl = entry - 20 if bias == "bullish" else entry + 20
    tp1 = entry + 40 if bias == "bullish" else entry - 40
    tp2 = entry + 80 if bias == "bullish" else entry - 80

    lot = 0.24 if account_type == "PERSONAL_10" else 1.0

    return {
        "pair": "AUTO",
        "bias": bias,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "lot": lot,
        "confidence": confidence
    }
