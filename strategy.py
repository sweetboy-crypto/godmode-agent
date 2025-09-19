import numpy as np
import pandas as pd


class TradingStrategy:
    """
    Tony Iyke A+ Setup Playbook Strategy
    """

    def __init__(self, risk_per_trade=0.01):
        self.risk_per_trade = risk_per_trade

    # -----------------
    # Utility functions
    # -----------------

    def identify_directional_bias(self, df):
        if len(df) < 5:
            return None
        highs = df['high'].values[-5:]
        lows = df['low'].values[-5:]
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return "bullish"
        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return "bearish"
        return None

    def detect_market_structure_shift(self, df, bias):
        if len(df) < 10 or bias is None:
            return False
        recent_high = max(df['high'].values[-5:])
        recent_low = min(df['low'].values[-5:])
        close = df['close'].values[-1]
        if bias == "bullish" and close > recent_high:
            return True
        if bias == "bearish" and close < recent_low:
            return True
        return False

    def detect_liquidity_zones(self, df):
        if len(df) < 10:
            return False
        highs = df['high'].values[-5:]
        lows = df['low'].values[-5:]
        if np.isclose(highs[-1], highs[-2], atol=0.1):
            return True
        if np.isclose(lows[-1], lows[-2], atol=0.1):
            return True
        return False

    def detect_poi(self, df):
        if len(df) < 3:
            return False
        c1, c2 = df.iloc[-3], df.iloc[-2]
        body1 = abs(c1['close'] - c1['open'])
        body2 = abs(c2['close'] - c2['open'])
        if body1 > 2 * body2:
            return True
        if c1['high'] < c2['low'] or c1['low'] > c2['high']:
            return True
        return False

    def calculate_confidence(self, db, mss, liq, poi, confirm):
        score = 0
        if db:
            score += 30
        if mss:
            score += 20
        if liq:
            score += 20
        if poi:
            score += 20
        if confirm:
            score += 10
        return min(score, 100)

    # -----------------
    # Main Trade Signal
    # -----------------

    def generate_signal(self, df_daily, df_4h, df_1h, symbol, account_balance):
        db = self.identify_directional_bias(df_daily)
        mss = self.detect_market_structure_shift(df_4h, db)
        liq = self.detect_liquidity_zones(df_1h)
        poi = self.detect_poi(df_4h)
        confirm = self.detect_market_structure_shift(df_1h, db)
        confidence = self.calculate_confidence(db, mss, liq, poi, confirm)

        if confidence < 85:
            return None

        entry = df_1h['close'].values[-1]
        atr = np.mean(df_1h['high'].values[-14:] - df_1h['low'].values[-14:])
        sl = entry - atr if db == "bullish" else entry + atr
        rr = abs(entry - sl)
        tp1 = entry + (rr * 3 if db == "bullish" else -rr * 3)
        tp2 = entry + (rr * 6 if db == "bullish" else -rr * 6)
        tp3 = entry + (rr * 10 if db == "bullish" else -rr * 10)

        risk_usd = account_balance * self.risk_per_trade
        lot = round(risk_usd / (rr * 10), 2)

        return {
            "pair": symbol,
            "bias": db,
            "entry": float(entry),
            "sl": float(sl),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "tp3": float(tp3),
            "lot": lot,
            "confidence": confidence,
            "status": "new"
        }
