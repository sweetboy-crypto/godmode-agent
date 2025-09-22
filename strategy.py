import numpy as np
import pandas as pd

class Strategy:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    # --- Step 1: Directional Bias ---
    def detect_bias(self, lookback=20):
        highs = self.df["high"].tail(lookback).values
        lows = self.df["low"].tail(lookback).values

        if all(x < y for x, y in zip(highs[:-1], highs[1:])) and all(x < y for x, y in zip(lows[:-1], lows[1:])):
            return "Bullish"
        elif all(x > y for x, y in zip(highs[:-1], highs[1:])) and all(x > y for x, y in zip(lows[:-1], lows[1:])):
            return "Bearish"
        return "Neutral"

    # --- Step 2: Market Structure Shift (MSS / BOS) ---
    def detect_mss(self):
        recent = self.df.tail(3)
        prev_high, curr_high = recent.iloc[-2]["high"], recent.iloc[-1]["high"]
        prev_low, curr_low = recent.iloc[-2]["low"], recent.iloc[-1]["low"]

        if curr_high > prev_high:
            return "Bullish MSS"
        elif curr_low < prev_low:
            return "Bearish MSS"
        return None

    # --- Step 3: Liquidity Pools / Inducements ---
    def identify_liquidity(self, lookback=50):
        highs = self.df["high"].tail(lookback).values
        lows = self.df["low"].tail(lookback).values
        liquidity_zones = []

        # Equal highs/lows → liquidity
        for i in range(1, len(highs)):
            if abs(highs[i] - highs[i-1]) < 0.0005:
                liquidity_zones.append({"type": "EQH", "level": highs[i]})
        for i in range(1, len(lows)):
            if abs(lows[i] - lows[i-1]) < 0.0005:
                liquidity_zones.append({"type": "EQL", "level": lows[i]})

        # Inducement (fakeouts: wick above high / below low)
        last = self.df.iloc[-1]
        if last["high"] > max(highs[:-1]):
            liquidity_zones.append({"type": "Liquidity Grab High", "level": last["high"]})
        if last["low"] < min(lows[:-1]):
            liquidity_zones.append({"type": "Liquidity Grab Low", "level": last["low"]})

        return liquidity_zones

    # --- Step 4: Points of Interest (OB, BB, FVG) ---
    def detect_poi(self, lookback=30):
        candles = self.df.tail(lookback).to_dict("records")
        pois = []

        for i in range(1, len(candles)):
            prev, curr = candles[i-1], candles[i]

            # Order Block: Bullish (down candle before rally)
            if prev["close"] < prev["open"] and curr["close"] > curr["open"] and curr["close"] > prev["high"]:
                pois.append({"type": "Bullish OB", "level": prev["low"]})

            # Order Block: Bearish (up candle before drop)
            if prev["close"] > prev["open"] and curr["close"] < curr["open"] and curr["close"] < prev["low"]:
                pois.append({"type": "Bearish OB", "level": prev["high"]})

            # Breaker Block: failed OB retested
            if prev["close"] < prev["open"] and curr["close"] < prev["low"]:
                pois.append({"type": "Breaker Block", "level": prev["open"]})

            # Fair Value Gap: gap between candles
            if i >= 2:
                gap = candles[i-2]["high"] < curr["low"]
                if gap:
                    pois.append({"type": "FVG", "level": (candles[i-2]["high"] + curr["low"]) / 2})

        return pois[-1] if pois else None

    # --- Step 5: Confirmation Entry (Lower TF) ---
    def confirm_entry(self):
        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        # Wick rejection
        if last["close"] > last["open"] and (last["low"] < prev["low"]):
            return "Bullish Confirm"
        elif last["close"] < last["open"] and (last["high"] > prev["high"]):
            return "Bearish Confirm"

        return None

    # --- Confidence Scoring ---
    def score_setup(self):
        bias = self.detect_bias()
        mss = self.detect_mss()
        liquidity = self.identify_liquidity()
        poi = self.detect_poi()
        confirm = self.confirm_entry()

        score = 0
        if bias != "Neutral": score += 25
        if mss: score += 25
        if liquidity: score += 20
        if poi: score += 20
        if confirm: score += 10

        return score, bias, mss, liquidity, poi, confirm
