import random
import datetime

class TradingStrategy:
    def __init__(self):
        # Define account lot-sizing rules
        self.lot_table = {
            "10": {
                "Phase1": {"risk_usd_min": 1, "risk_usd_max": 2, "lot_min": 0.01, "lot_max": 0.02},
                "Funded": {"risk_usd_min": 2, "risk_usd_max": 3, "lot_min": 0.02, "lot_max": 0.03},
            },
            "5000": {
                "Phase1": {"risk_usd_min": 75, "risk_usd_max": 100, "lot_min": 0.075, "lot_max": 0.1},
                "Phase2": {"risk_usd_min": 50, "risk_usd_max": 62.5, "lot_min": 0.05, "lot_max": 0.0625},
                "Funded": {"risk_usd_min": 12.5, "risk_usd_max": 37.5, "lot_min": 0.0125, "lot_max": 0.0375},
            },
            "10000": {
                "Phase1": {"risk_usd_min": 150, "risk_usd_max": 200, "lot_min": 0.15, "lot_max": 0.2},
                "Phase2": {"risk_usd_min": 100, "risk_usd_max": 125, "lot_min": 0.1, "lot_max": 0.125},
                "Funded": {"risk_usd_min": 25, "risk_usd_max": 75, "lot_min": 0.025, "lot_max": 0.075},
            },
            "25000": {
                "Phase1": {"risk_usd_min": 375, "risk_usd_max": 500, "lot_min": 0.375, "lot_max": 0.5},
                "Phase2": {"risk_usd_min": 250, "risk_usd_max": 312.5, "lot_min": 0.25, "lot_max": 0.3125},
                "Funded": {"risk_usd_min": 62.5, "risk_usd_max": 187.5, "lot_min": 0.0625, "lot_max": 0.1875},
            },
            "50000": {
                "Phase1": {"risk_usd_min": 750, "risk_usd_max": 1000, "lot_min": 0.75, "lot_max": 1.0},
                "Phase2": {"risk_usd_min": 500, "risk_usd_max": 625, "lot_min": 0.5, "lot_max": 0.625},
                "Funded": {"risk_usd_min": 125, "risk_usd_max": 375, "lot_min": 0.125, "lot_max": 0.375},
            },
            "100000": {
                "Phase1": {"risk_usd_min": 1500, "risk_usd_max": 2000, "lot_min": 1.5, "lot_max": 2.0},
                "Phase2": {"risk_usd_min": 1000, "risk_usd_max": 1250, "lot_min": 1.0, "lot_max": 1.25},
                "Funded": {"risk_usd_min": 250, "risk_usd_max": 750, "lot_min": 0.25, "lot_max": 0.75},
            },
            "200000": {
                "Phase1": {"risk_usd_min": 3000, "risk_usd_max": 4000, "lot_min": 3.0, "lot_max": 4.0},
                "Phase2": {"risk_usd_min": 2000, "risk_usd_max": 2500, "lot_min": 2.0, "lot_max": 2.5},
                "Funded": {"risk_usd_min": 500, "risk_usd_max": 1500, "lot_min": 0.5, "lot_max": 1.5},
            },
        }

    def calculate_risk(self, account_size, phase="Phase1"):
        if account_size not in self.lot_table:
            return None
        if phase not in self.lot_table[account_size]:
            phase = "Phase1"
        return self.lot_table[account_size][phase]

    def generate_signal(self, symbol, price, account_size="5000", phase="Phase1"):
        # Confidence score
        confidence = random.randint(80, 99)

        # Skip low-confidence trades for $10 account
        if account_size == "10" and confidence < 95:
            return None
        elif account_size != "10" and confidence < 85:
            return None

        # Risk settings
        risk = self.calculate_risk(account_size, phase)
        if not risk:
            return None

        lot = round(random.uniform(risk["lot_min"], risk["lot_max"]), 2)

        # Direction bias
        direction = random.choice(["BUY", "SELL"])

        # SL and TP logic
        if direction == "BUY":
            sl = round(price * 0.995, 3)  # ~50 pips below
            tp1 = round(price * 1.003, 3)  # RR ~ 1:3
            tp2 = round(price * 1.006, 3)  # RR ~ 1:6
            tp3 = round(price * 1.010, 3)  # RR ~ 1:10
        else:
            sl = round(price * 1.005, 3)
            tp1 = round(price * 0.997, 3)
            tp2 = round(price * 0.994, 3)
            tp3 = round(price * 0.990, 3)

        signal = {
            "pair": symbol,
            "direction": direction,
            "entry": price,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "lot": lot,
            "confidence": confidence,
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        return signal
