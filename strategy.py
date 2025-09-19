# strategy.py
import math
import requests

class TradeSetup:
    def __init__(self, symbol, direction, entry, sl, rr_ratios, confidence, account_type, sl_pips):
        """
        rr_ratios: list of RR multipliers, e.g., [3,6,10]
        account_type: 'personal_10', 'phase1', 'phase2', 'funded'
        sl_pips: Stop loss in pips or points
        """
        self.symbol = symbol
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.rr_ratios = rr_ratios
        self.confidence = confidence
        self.account_type = account_type
        self.sl_pips = sl_pips
        self.tp_levels = self.calculate_tps()
        self.lot_size = self.calculate_lot_size()

    def calculate_tps(self):
        tps = []
        for rr in self.rr_ratios:
            if self.direction.lower() == "buy":
                tp = self.entry + self.sl_pips * rr
            else:
                tp = self.entry - self.sl_pips * rr
            tps.append(round(tp, 5))
        return tps

    def calculate_lot_size(self):
        account_risk_percent = {
            "personal_10": 5,
            "phase1": 2,
            "phase2": 1.25,
            "funded": 0.5
        }
        pip_value_usd = 10
        if "XAU" in self.symbol.upper():
            pip_value_usd = 1

        risk_usd = account_risk_percent[self.account_type] / 100 * self.get_account_balance()
        lot_size = risk_usd / (self.sl_pips * pip_value_usd)
        return round(lot_size, 3)

    def get_account_balance(self):
        balances = {
            "personal_10": 10,
            "phase1": 5000,
            "phase2": 5000,
            "funded": 50000
        }
        return balances.get(self.account_type, 5000)

# --- A+ Setup Logic Functions ---
def identify_directional_bias(htf_candles):
    highs = [c['high'] for c in htf_candles]
    lows = [c['low'] for c in htf_candles]
    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return "buy"
    elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return "sell"
    return None

def detect_market_structure_shift(htf_candles):
    if len(htf_candles) < 3:
        return None
    prev_high = htf_candles[-2]['high']
    prev_low = htf_candles[-2]['low']
    curr_high = htf_candles[-1]['high']
    curr_low = htf_candles[-1]['low']
    if curr_high > prev_high:
        return "bullish_bos"
    elif curr_low < prev_low:
        return "bearish_bos"
    return None

# --- Live POI & Liquidity Detection ---
def fetch_live_candles(symbol, interval="15min", outputsize=50, api_key=None):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={api_key}"
    r = requests.get(url, timeout=10).json()
    if "values" in r:
        candles = [{"high": float(c["high"]), "low": float(c["low"]), "close": float(c["close"])} for c in reversed(r["values"])]
        return candles
    return []

def detect_poi_and_liquidity(htf_candles):
    """
    Detect OB, BB, FVG and liquidity zones.
    For simplicity, we take:
    - OB: last 2 candles of trend before reversal
    - FVG: gap between candles
    - Liquidity: recent highs/lows
    """
    ob_list = []
    fvg_list = []
    liquidity = []

    if len(htf_candles) >= 3:
        last = htf_candles[-1]
        prev = htf_candles[-2]
        prev2 = htf_candles[-3]

        # OB as last candle of trend
        ob_list.append({"top": prev["high"], "bottom": prev["low"], "type": "OB"})

        # FVG
        if prev2["close"] < prev["open"]:
            fvg_list.append({"top": prev["high"], "bottom": prev["low"], "type": "FVG"})

        # Liquidity zones: highs/lows
        liquidity.append(prev["high"])
        liquidity.append(prev["low"])

    return ob_list, fvg_list, liquidity

def confirm_entry(ltf_candles, poi, directional_bias):
    last_candle = ltf_candles[-1]
    if directional_bias == "buy" and last_candle['low'] <= poi['bottom']:
        return True
    elif directional_bias == "sell" and last_candle['high'] >= poi['top']:
        return True
    return False

def confidence_score(structure_shift, poi, confirmation):
    score = 0
    if structure_shift:
        score += 40
    if poi:
        score += 30
    if confirmation:
        score += 30
    return min(score, 100)

def generate_trade(symbol, htf_candles, ltf_candles, account_type, sl_pips=20):
    db = identify_directional_bias(htf_candles)
    if not db:
        return None
    mss = detect_market_structure_shift(htf_candles)
    ob_list, fvg_list, liquidity = detect_poi_and_liquidity(htf_candles)
    poi = ob_list[-1] if ob_list else None
    if not poi:
        return None
    confirm = confirm_entry(ltf_candles, poi, db)
    confidence = confidence_score(mss, poi, confirm)
    if confidence < 85 and account_type != "personal_10":
        return None
    if confidence < 95 and account_type == "personal_10":
        return None
    entry_price = (poi['top'] + poi['bottom']) / 2
    trade = TradeSetup(
        symbol=symbol,
        direction=db,
        entry=entry_price,
        sl=poi['bottom'] if db=="buy" else poi['top'],
        rr_ratios=[3,6,10],
        confidence=confidence,
        account_type=account_type,
        sl_pips=sl_pips
    )
    return trade
