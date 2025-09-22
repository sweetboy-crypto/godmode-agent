import pandas as pd

class Strategy:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def detect_bias(self):
        recent = self.df.tail(50)
        if all(recent["high"].diff().dropna() > 0) and all(recent["low"].diff().dropna() > 0):
            return "Bullish"
        elif all(recent["high"].diff().dropna() < 0) and all(recent["low"].diff().dropna() < 0):
            return "Bearish"
        return "Neutral"

    def detect_mss(self):
        last_high = self.df["high"].iloc[-2]
        last_low = self.df["low"].iloc[-2]
        curr_close = self.df["close"].iloc[-1]
        if curr_close > last_high:
            return "Bullish Shift"
        elif curr_close < last_low:
            return "Bearish Shift"
        return "No Shift"

    def identify_liquidity(self):
        highs = self.df["high"].rolling(5).max()
        lows = self.df["low"].rolling(5).min()
        return {"liq_high": highs.iloc[-1], "liq_low": lows.iloc[-1]}

    def detect_poi(self):
        last_candle = self.df.iloc[-2]
        if last_candle["close"] < last_candle["open"]:
            return {"type": "OB", "level": last_candle["low"]}
        return {"type": "OB", "level": last_candle["high"]}

    def confirm_entry(self):
        last = self.df.tail(3)
        if last.iloc[-1]["close"] > last.iloc[-1]["open"] and last.iloc[-2]["low"] < last.iloc[-3]["low"]:
            return "Confirmed Long"
        elif last.iloc[-1]["close"] < last.iloc[-1]["open"] and last.iloc[-2]["high"] > last.iloc[-3]["high"]:
            return "Confirmed Short"
        return None
