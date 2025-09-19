import statistics

def min_confidence_required(account_type: str) -> int:
    """
    Minimum confidence threshold per account type.
    """
    return 95 if account_type == "PERSONAL_10" else 85


def calculate_lot_size(account_type: str, risk_usd: float, stop_loss_pips: float) -> float:
    """
    Simplified lot size calculator (prop firm risk model).
    """
    if stop_loss_pips <= 0:
        return 0.01
    
    usd_per_pip_per_01 = 1  # gold/majors approx.
    lot = (risk_usd / (stop_loss_pips * usd_per_pip_per_01)) * 0.1
    return round(max(lot, 0.01), 2)


# ---------------------------
# Strategy Implementation
# ---------------------------

def identify_directional_bias(candles: list) -> str:
    """
    Identify directional bias on higher TF using swing logic.
    - Bullish = Higher Highs & Higher Lows
    - Bearish = Lower Lows & Lower Highs
    - Sideways = No clear structure
    """
    closes = [float(c["close"]) for c in candles[:20]]
    highs = [float(c["high"]) for c in candles[:20]]
    lows = [float(c["low"]) for c in candles[:20]]

    avg_high = statistics.mean(highs)
    avg_low = statistics.mean(lows)

    if closes[0] > avg_high and closes[0] > closes[-1]:
        return "bullish"
    elif closes[0] < avg_low and closes[0] < closes[-1]:
        return "bearish"
    return "sideways"


def detect_market_structure_shift(candles: list, bias: str) -> bool:
    """
    Detect Market Structure Shift (MSS).
    - For bullish setups: price must break prior LL.
    - For bearish setups: price must break prior HH.
    """
    highs = [float(c["high"]) for c in candles[:10]]
    lows = [float(c["low"]) for c in candles[:10]]

    if bias == "bullish" and min(lows) < lows[-1]:
        return True
    if bias == "bearish" and max(highs) > highs[-1]:
        return True
    return False


def detect_liquidity_zones(candles: list):
    """
    Detect simple liquidity pools (equal highs/lows).
    """
    highs = [round(float(c["high"]), 1) for c in candles[:30]]
    lows = [round(float(c["low"]), 1) for c in candles[:30]]

    liquidity_highs = [h for h in set(highs) if highs.count(h) > 2]
    liquidity_lows = [l for l in set(lows) if lows.count(l) > 2]

    return liquidity_highs, liquidity_lows


def detect_poi(candles: list, bias: str):
    """
    Detect POI = last opposite candle before move.
    Simplified Order Block / FVG.
    """
    last_candle = candles[0]
    entry = float(last_candle["close"])

    if bias == "bullish":
        sl = float(last_candle["low"]) - 20
        tp1 = entry + 60
        tp2 = entry + 120
    else:
        sl = float(last_candle["high"]) + 20
        tp1 = entry - 60
        tp2 = entry - 120

    return entry, sl, tp1, tp2


def generate_signal(candles: list, account_type: str, symbol: str) -> dict | None:
    """
    Full A+ Setup detection pipeline.
    """
    bias = identify_directional_bias(candles)
    if bias == "sideways":
        return None

    if not detect_market_structure_shift(candles, bias):
        return None

    liquidity_highs, liquidity_lows = detect_liquidity_zones(candles)
    if not liquidity_highs and not liquidity_lows:
        return None

    entry, sl, tp1, tp2 = detect_poi(candles, bias)

    stop_loss_pips = abs(entry - sl)
    if stop_loss_pips < 10:
        return None

    # Risk per account type
    risk_map = {
        "PERSONAL_10": 1,
        "PROP_PHASE1": 100,
        "PROP_PHASE2": 75,
        "FUNDED": 50,
    }
    risk_usd = risk_map.get(account_type, 50)

    lot = calculate_lot_size(account_type, risk_usd, stop_loss_pips)

    # Confidence score based on confluences
    confidence = 80
    if liquidity_highs or liquidity_lows:
        confidence += 5
    if lot > 0.1:
        confidence += 5
    if abs(tp2 - entry) / stop_loss_pips >= 3:  # R:R >= 1:3
        confidence += 5

    if confidence < min_confidence_required(account_type):
        return None

    return {
        "pair": symbol,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "lot": lot,
        "confidence": confidence,
        "bias": bias,
    }
