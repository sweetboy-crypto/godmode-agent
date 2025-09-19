import datetime
import statistics

class Strategy:
    def __init__(self, candles, symbol, account_type="FUNDED"):
        """
        candles: dict of timeframe -> OHLCV data
        symbol: str (e.g., "XAUUSD")
        account_type: "FUNDED" | "PHASE1" | "PHASE2" | "PERSONAL_10"
        """
        self.candles = candles
        self.symbol = symbol
        self.account_type = account_type
        self.now = datetime.datetime.utcnow()

    def in_session(self):
        """Filter trades only during London & NY sessions"""
        hour = self.now.hour
        # London: 07:00–11:00 UTC, NY: 12:30–16:00 UTC
        return (7 <= hour < 11) or (12 <= hour < 16)

    def detect_bos(self, tf="H4"):
        """Detect Break of Structure (BOS) on higher TF"""
        data = self.candles.get(tf, [])
        if len(data) < 5:
            return None

        last = data[-1]
        prev = data[-2]

        # BOS bullish if close > prev_high
        if last["close"] > prev["high"]:
            return "BOS_UP"
        # BOS bearish if close < prev_low
        elif last["close"] < prev["low"]:
            return "BOS_DOWN"
        return None

    def detect_liquidity_grab(self, tf="M15"):
        """Detect liquidity sweep (wick above/below key level then close opposite)"""
        data = self.candles.get(tf, [])
        if len(data) < 5:
            return None

        last = data[-1]
        prev = data[-2]

        # Sweep above high but close below = bearish liquidity grab
        if last["high"] > prev["high"] and last["close"] < prev["close"]:
            return "SWEEP_HIGH"
        # Sweep below low but close above = bullish liquidity grab
        if last["low"] < prev["low"] and last["close"] > prev["close"]:
            return "SWEEP_LOW"
        return None

    def detect_poi(self, tf="H4"):
        """Detect strong POI (order block / imbalance zone)"""
        data = self.candles.get(tf, [])
        if len(data) < 5:
            return None

        last = data[-1]
        prev = data[-2]

        # Strong bullish impulsive candle (big body, small wick)
        if (last["close"] > last["open"]) and ((last["close"] - last["open"]) > 2 * (last["high"] - last["low"]) / 3):
            return "DEMAND"

        # Strong bearish impulsive candle
        if (last["close"] < last["open"]) and ((last["open"] - last["close"]) > 2 * (last["high"] - last["low"]) / 3):
            return "SUPPLY"

        return None

    def calculate_confidence(self):
        """Confidence score based on confluence"""
        score = 0

        if self.detect_bos("H4"): score += 30
        if self.detect_liquidity_grab("M15"): score += 30
        if self.detect_poi("H4"): score += 25
        if self.in_session(): score += 15

        return min(score, 100)

    def generate_signal(self):
        """Generate trade setup if conditions are met"""
        conf = self.calculate_confidence()

        # Different account risk rules
        if self.account_type == "PERSONAL_10" and conf < 95:
            return None
        elif self.account_type != "PERSONAL_10" and conf < 85:
            return None

        direction = None
        bos = self.detect_bos("H4")
        sweep = self.detect_liquidity_grab("M15")
        poi = self.detect_poi("H4")

        if bos == "BOS_UP" and sweep in ["SWEEP_LOW", None] and poi == "DEMAND":
            direction = "BUY"
        elif bos == "BOS_DOWN" and sweep in ["SWEEP_HIGH", None] and poi == "SUPPLY":
            direction = "SELL"
        else:
            return None

        # Example: last M15 candle for entry
        ref = self.candles["M15"][-1]
        entry = ref["close"]

        # SL at candle high/low
        if direction == "BUY":
            sl = ref["low"]
        else:
            sl = ref["high"]

        risk = abs(entry - sl)

        # TP targets with fixed RR
        tp1 = entry + (risk * 3) if direction == "BUY" else entry - (risk * 3)
        tp2 = entry + (risk * 6) if direction == "BUY" else entry - (risk * 6)
        tp3 = entry + (risk * 10) if direction == "BUY" else entry - (risk * 10)

        return {
            "symbol": self.symbol,
            "direction": direction,
            "entry": round(entry, 3),
            "sl": round(sl, 3),
            "tp1": round(tp1, 3),
            "tp2": round(tp2, 3),
            "tp3": round(tp3, 3),
            "confidence": conf,
            "time": self.now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "account_type": self.account_type
        }
