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
        """
        Identify Directional Bias (DB) on higher timeframe (Daily or 4H).
        Returns: 'bullish', 'bearish', or None
        """
        if len(df) < 5:
            return None

        closes = df['close'].values[-5:]
        highs = df['high'].values[-5:]
        lows = df['low'].values[-5:]

        # Bullish bias if HH/HL
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return "bullish"
        # Bearish bias if LL/LH
        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return "bearish"
        else:
            return None

    def detect_market_structure_shift(self, df, bias):
        """
        Detect Market Structure Shift (MSS).
        For bullish → break of last LL.
        For bearish → break of last HH.
        """
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
        """
        Detect simple liquidity zones:
        - Equal highs/lows (double tops/bottoms)
        - Wick sweeps
        """
        if len(df) < 10:
            return False

        highs = df['high'].values[-5:]
        lows = df['low'].values[-5:]

        # Equal highs or lows
        if np.isclose(highs[-1], highs[-2], atol=0.1):
            return True
        if np.isclose(lows[-1], lows[-2], atol=0.1):
            return True

        return False

    def detect_poi(self, df):
        """
        Simplified POI detection:
        - Order block = large candle before strong move
        - FVG = gap between candles
        """
        if len(df) < 3:
            return False

        c1, c2 = df.iloc[-3], df.iloc[-2]
        body1 = abs(c1['close'] - c1['open'])
        body2 = abs(c2['close'] - c2['open'])

        # Large candle body → potential OB
        if body1 > 2 * body2:
            return True

        # FVG → gap between candles
        if c1['high'] < c2['low'] or c1['low'] > c2['high']:
            return True

        return False

    def calculate_confidence(self, db, mss, liq, poi, confirm):
        """
        Confidence scoring based on playbook rules
        """
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
        """
        Generates an A+ trade signal if all rules align
        """
        # 1. Directional Bias
        db = self.identify_directional_bias(df_daily)

        # 2. MSS
        mss = self.detect_market_structure_shift(df_4h, db)

        # 3. Liquidity
        liq = self.detect_liquidity_zones(df_1h)

        # 4. POI
        poi = self.detect_poi(df_4h)

        # 5. Confirmation on LTF (1H here)
        confirm = self.detect_market_structure_shift(df_1h, db)

        # Confidence
        confidence = self.calculate_confidence(db, mss, liq, poi, confirm)

        if confidence < 85:
            return None

        # Entry at last close
        entry = df_1h['close'].values[-1]
        atr = np.mean(df_1h['high'].values[-14:] - df_1h['low'].values[-14:])
        sl = entry - atr if db == "bullish" else entry + atr

        # TP1 = 1:3, TP2 = 1:6, TP3 = 1:10
        rr = abs(entry - sl)
        tp1 = entry + (rr * 3 if db == "bullish" else -rr * 3)
        tp2 = entry + (rr * 6 if db == "bullish" else -rr * 6)
        tp3 = entry + (rr * 10 if db == "bullish" else -rr * 10)

        # Lot size (1% risk model)
        risk_usd = account_balance * self.risk_per_trade
        lot = round(risk_usd / (rr * 10), 2)  # simplified

        return {
            "pair": symbol,
            "bias": db,
            "entry": float(entry),
            "sl": float(sl),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "tp3": float(tp3),
            "lot": lot,
            "confidence": confidence
        }
