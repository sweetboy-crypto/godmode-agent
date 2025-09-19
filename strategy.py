# strategy.py
import math

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
        """Calculate take profits based on RR ratios"""
        tps = []
        for rr in self.rr_ratios:
            if self.direction.lower() == "buy":
                tp = self.entry + self.sl_pips * rr
            else:
                tp = self.entry - self.sl_pips * rr
            tps.append(round(tp, 5))
        return tps

    def calculate_lot_size(self):
        """
        Lot sizing per account type.
        Risk formulas adapted to instrument type.
        """
        account_risk_percent = {
            "personal_10": 5,   # aggressive $10 account
            "phase1": 2,
            "phase2": 1.25,
            "funded": 0.5
        }
        # Assume pip_value per standard lot
        pip_value_usd = 10  # for standard USD pairs
        if "XAU" in self.symbol.upper():
            pip_value_usd = 1  # gold approx $1 per pip per 0.01 lot
        
        risk_usd = account_risk_percent[self.account_type] / 100 * self.get_account_balance()
        lot_size = risk_usd / (self.sl_pips * pip_value_usd)
        return round(lot_size, 3)

    def get_account_balance(self):
        """Mock account balance by type"""
        balances = {
            "personal_10": 10,
            "phase1": 5000,
            "phase2": 5000,
            "funded": 50000
        }
        return balances.get(self.account_type, 5000)

# --- A+ Setup Logic Functions ---
def identify_directional_bias(htf_candles):
    """
    htf_candles: list of dicts [{ 'high':, 'low':, 'close': }]
    Returns: 'buy' or 'sell' or None
    """
    highs = [c['high'] for c in htf_candles]
    lows = [c['low'] for c in htf_candles]
    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return "buy"
    elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return "sell"
    else:
        return None

def detect_market_structure_shift(htf_candles):
    """
    Returns True if BOS/CHoCH is detected
    """
    if len(htf_candles) < 3:
        return False
    prev_high = htf_candles[-2]['high']
    prev_low = htf_candles[-2]['low']
    curr_high = htf_candles[-1]['high']
    curr_low = htf_candles[-1]['low']
    # Bullish BOS
    if curr_high > prev_high:
        return "bullish_bos"
    # Bearish BOS
    elif curr_low < prev_low:
        return "bearish_bos"
    else:
        return None

def find_poi(ob_list, bb_list, fvg_list):
    """
    ob_list: list of order blocks [{ 'top':, 'bottom': }]
    bb_list: list of breaker blocks
    fvg_list: list of fair value gaps
    Returns best POI dict {'type':'OB','top':, 'bottom':}
    """
    # Institutional style: prioritize OB > BB > FVG
    if ob_list:
        return ob_list[-1]
    elif bb_list:
        return bb_list[-1]
    elif fvg_list:
        return fvg_list[-1]
    else:
        return None

def confirm_entry(ltf_candles, poi, directional_bias):
    """
    Checks lower TF confirmation: BOS, liquidity grab, wick spike
    Returns True if valid entry
    """
    # Simplified: last candle wick touches POI
    last_candle = ltf_candles[-1]
    if directional_bias == "buy":
        if last_candle['low'] <= poi['bottom']:
            return True
    elif directional_bias == "sell":
        if last_candle['high'] >= poi['top']:
            return True
    return False

def confidence_score(structure_shift, poi, confirmation):
    """
    Returns confidence 0-100%
    """
    score = 0
    if structure_shift:
        score += 40
    if poi:
        score += 30
    if confirmation:
        score += 30
    return min(score, 100)

# Example function to generate TradeSetup
def generate_trade(symbol, htf_candles, ltf_candles, ob_list, bb_list, fvg_list, account_type, sl_pips=20):
    db = identify_directional_bias(htf_candles)
    if not db:
        return None
    mss = detect_market_structure_shift(htf_candles)
    poi = find_poi(ob_list, bb_list, fvg_list)
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
