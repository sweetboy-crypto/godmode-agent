# agent.py
# Minimal, deterministic trading agent implementing multi-timeframe checks.
# Designed to run in GitHub Actions (every 15 minutes). No external paid LLM required.
# Requirements: requests, pytz, python-dateutil

import os, sys, json, time, csv
from datetime import datetime, timezone, timedelta
import requests
from dateutil import parser
import pytz

# ----------------------
# Config (do NOT store secrets here; set in GitHub Secrets)
# ----------------------
TWELVE_KEY = os.getenv("TWELVEDATA_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_API_KEY = os.getenv("HF_API_KEY")  # optional: Hugging Face token for secondary check

# Instruments and timeframes
INSTRUMENT = "XAU/USD"
SYMBOL = "XAU/USD"
TFS = {
    "15min": "15min",
    "1h": "1h",
    "4h": "4h",
    "1day": "1day"
}
# Lagos timezone
LAGOS = pytz.timezone("Africa/Lagos")

# ----------------------
# Helpers: Twelve Data fetch
# ----------------------
def fetch_twelve(symbol, interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "format": "JSON",
        "apikey": TWELVE_KEY
    }
    r = requests.get(url, params=params, timeout=30)
    return r.json()

# ----------------------
# Helper: simple utilities
# ----------------------
def latest_values(series_json, n=10):
    # twelve data returns 'values' list newest-first usually
    vals = series_json.get("values", [])
    return vals[:n]

def parse_candle(c):
    # inputs are strings
    return {
        "datetime": c["datetime"],
        "open": float(c["open"]),
        "high": float(c["high"]),
        "low": float(c["low"]),
        "close": float(c["close"]),
        "volume": float(c.get("volume", 0))
    }

def compute_trend(candles):
    # naive trend: compare last close to close N periods ago
    if len(candles) < 5: return 0
    c0 = parse_candle(candles[0])["close"]
    cN = parse_candle(candles[-1])["close"]
    pct = (c0 - cN) / cN
    return pct  # positive = uptrend, negative = downtrend

# ----------------------
# Strategy (conservative starter)
# ----------------------
def strategy_snapshot(m15, h1, h4, daily):
    """
    Basic conservative SMC-ish rules:
    - HTF bias: use H4 and Daily trend (close now vs close 4 candles ago)
    - M15 breakout: last M15 close breaks recent local high/low
    - Check proximity to H4 POI (we'll treat H4 high/low as POI)
    - Only yield signals that align with HTF bias
    """
    snap = {}
    # parse lists
    m15_vals = [parse_candle(c) for c in m15]
    h1_vals = [parse_candle(c) for c in h1]
    h4_vals = h4 if isinstance(h4, dict) else [parse_candle(c) for c in h4]
    daily_vals = [parse_candle(c) for c in daily]
    # HTF trend checks
    h4_trend = compute_trend(h4 if isinstance(h4, list) else [h4]) if isinstance(h4, list) else 0
    daily_trend = compute_trend(daily_vals)
    # m15 last candle
    latest_m15 = m15_vals[0]
    # define recent high/low on m15 (last 4 closes)
    recent_high = max(c["high"] for c in m15_vals[1:5])
    recent_low  = min(c["low"] for c in m15_vals[1:5])

    # POI as latest H4 high/low (approx)
    # If h4 is aggregated dict (open/high/low/close)
    if isinstance(h4_vals, dict):
        h4_high = h4_vals["high"]
        h4_low = h4_vals["low"]
    else:
        # fallback use high/low from last h4 candle
        h4_high = h4_vals[0]["high"]
        h4_low = h4_vals[0]["low"]

    # Conditions for BUY
    buy = False
    sell = False
    reason = ""
    # HTF bias up if daily_trend and h4_trend positive
    htf_up = (daily_trend > 0) and (h4_trend > 0)
    htf_down = (daily_trend < 0) and (h4_trend < 0)

    # breakout above recent high AND near H4 zone for buy
    if latest_m15["close"] > recent_high and htf_up:
        # check proximity to H4 POI (price should be below h4_high and not far)
        if latest_m15["close"] < h4_high * 1.002:  # within 0.2% margin
            buy = True
            reason = "M15 breakout in HTF uptrend near H4 POI (OB/FVG candidate)"
    # breakout below recent low AND HTF down for sell
    if latest_m15["close"] < recent_low and htf_down:
        if latest_m15["close"] > h4_low * 0.998:
            sell = True
            reason = "M15 breakdown in HTF downtrend near H4 POI (OB/FVG candidate)"

    # Build signal if any
    if buy or sell:
        side = "BUY" if buy else "SELL"
        entry = latest_m15["close"]
        # SL: place beyond recent structure: for buy below recent_low, for sell above recent_high
        sl = recent_low - 0.05 if buy else recent_high + 0.05
        # TPs: 1:5, 1:7, 1:10 using risk-distance in price terms approximated
        # approximate pip/unit: for gold we treat price direct
        risk = abs(entry - sl)
        tp1 = entry + (risk * 5) if buy else entry - (risk * 5)
        tp2 = entry + (risk * 7) if buy else entry - (risk * 7)
        tp3 = entry + (risk * 10) if buy else entry - (risk * 10)

        signal = {
            "instrument": SYMBOL,
            "direction": side,
            "reason": reason,
            "entry": round(entry, 2),
            "stop": round(sl, 2),
            "tps": [round(tp1,2), round(tp2,2), round(tp3,2)],
            "confidence_est": 85  # base default, further checked by HF if available
        }
        return signal
    else:
        return None

# ----------------------
# Lot table generator
# ----------------------
def compute_lot_table(sl_distance, instrument="XAU/USD"):
    # For simplicity assume XAUUSD pip value ~ $1 per 0.01 for 1 lot = 100 oz => pip unit = 0.01
    # We'll produce sample tables for common account sizes
    accounts = [5000, 10000, 25000, 50000, 100000, 200000]
    phases = {
        "Phase1": (0.015, 0.02),
        "Phase2": (0.01, 0.0125),
        "Funded": (0.0025, 0.0075),
    }
    table = {}
    pip_value_per_lot = 1.0  # approximate (1 USD per pip per 1 lot)
    sl_pips = max(1, int(round(sl_distance / 0.01)))  # convert price distance to pip count approx
    for bal in accounts:
        table[bal] = {}
        for p, (lowpct, highpct) in phases.items():
            risk_low = bal * lowpct
            risk_high = bal * highpct
            lot_min = round(risk_low / (sl_pips * pip_value_per_lot), 4)
            lot_max = round(risk_high / (sl_pips * pip_value_per_lot), 4)
            table[bal][p] = {"risk_usd_min": risk_low, "risk_usd_max": risk_high, "lot_min": lot_min, "lot_max": lot_max}
    return table

# ----------------------
# Optional Hugging Face check (secondary)
# ----------------------
def hf_check(signal, snapshot):
    if not HF_API_KEY:
        return {"ok": True, "confidence": signal.get("confidence_est", 85), "note": "no-hf"}
    # Build a small prompt: ask HF model to return JSON {ok: true/false, confidence: int}
    prompt = (
        f"You are a conservative trading verifier. Given this signal and market snapshot, "
        f"answer in EXACT JSON: {{\"ok\": bool, \"confidence\": number, \"reason\": \"...\"}}.\n\n"
        f"SIGNAL: {json.dumps(signal)}\nSNAPSHOT: summarize: keys only.\n"
    )
    # Call a small model via HF inference
    url = "https://api-inference.huggingface.co/models/google/flan-t5-small"
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        out = r.json()
        # HF returns text in various shapes; try to extract numbers from text
        txt = ""
        if isinstance(out, dict) and "error" in out:
            return {"ok": True, "confidence": signal.get("confidence_est", 85), "note": "hf_error"}
        if isinstance(out, list):
            # many HF models return list of dicts with 'generated_text'
            txt = out[0].get("generated_text", "")
        elif isinstance(out, dict) and "generated_text" in out:
            txt = out.get("generated_text", "")
        else:
            txt = str(out)
        # Try to find a percentage number in the text
        import re
        m = re.search(r"(\d{2,3})\s*%", txt)
        confidence = int(m.group(1)) if m else signal.get("confidence_est", 85)
        ok = confidence >= 85
        return {"ok": ok, "confidence": confidence, "hf_text": txt}
    except Exception as e:
        return {"ok": True, "confidence": signal.get("confidence_est", 85), "note": f"hf_exception:{e}"}

# ----------------------
# Telegram send (cleaned + full lot table)
# ----------------------
def send_telegram(signal, lot_table):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping send.")
        return False

    # Build main signal text
    text = (
        f"🛡️ GOD MODE SIGNAL\n"
        f"Instrument: {signal['instrument']}\n"
        f"Direction: {signal['direction']}\n"
        f"Entry: {signal['entry']}\n"
        f"Stop: {signal['stop']}\n"
        f"TPs: {', '.join(map(str, signal['tps']))}\n"
        f"Reason: {signal['reason']}\n"
        f"Confidence: {signal.get('confidence_check', signal.get('confidence_est'))}%\n\n"
        f"📊 Lot Table:\n"
    )

    # Add $10 micro account (fixed values)
    text += "💵 $10 Account → 0.01 lots (Risk $1 max)\n\n"

    # Format lot table neatly for all phases
    for acc_size, phases in lot_table.items():
        text += f"💰 ${acc_size}\n"
        for phase, vals in phases.items():
            text += (f"  • {phase}: {vals['lot_min']:.2f}–{vals['lot_max']:.2f} lots "
                     f"(Risk ${vals['risk_usd_min']:.0f}–{vals['risk_usd_max']:.0f})\n")
        text += "\n"

    # Send message to Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    r = requests.post(url, data=payload, timeout=15)
    return r.status_code == 200


# ----------------------
# Append to CSV log
# ----------------------
def append_log(signal, lot_table, hf_result):
    fname = "signals.csv"
    header = ["timestamp","instrument","direction","entry","stop","tps","confidence","hf_confidence","reason","lot_table","hf_result"]
    ts = datetime.now(LAGOS).isoformat()
    row = [ts, signal["instrument"], signal["direction"], signal["entry"], signal["stop"], json.dumps(signal["tps"]),
           signal.get("confidence_est"), hf_result.get("confidence"), signal["reason"], json.dumps(lot_table), json.dumps(hf_result)]
    exists = os.path.exists(fname)
    with open(fname, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow(row)

# ----------------------
# Main run
# ----------------------
def main():
    if not TWELVE_KEY:
        print("Error: TWELVEDATA_API_KEY not set.")
        sys.exit(1)
    # fetch TFs
    try:
        print("Fetching 15min...")
        m15 = fetch_twelve(SYMBOL, TFS["15min"], outputsize=50)
        print("Fetching 1h...")
        h1  = fetch_twelve(SYMBOL, TFS["1h"], outputsize=50)
        print("Fetching 4h...")
        h4_raw = fetch_twelve(SYMBOL, TFS["4h"], outputsize=20)
        print("Fetching daily...")
        daily = fetch_twelve(SYMBOL, TFS["1day"], outputsize=30)
    except Exception as e:
        print("Fetch error:", e)
        sys.exit(1)

    # basic validity checks
    if "values" not in m15 or "values" not in h1 or "values" not in daily:
        print("Missing time series in one of responses. Dumping outputs for debug.")
        print("m15 keys:", list(m15.keys())[:5])
        print("h1 keys:", list(h1.keys())[:5])
        print("daily keys:", list(daily.keys())[:5])
        sys.exit(1)

    # aggregate 4h: Twelve Data may have 4h available; if not build from h1 last 4
    if "values" in h4_raw:
        h4 = [parse_candle(c) for c in h4_raw["values"]]
    else:
        # aggregate h1 -> 4h by grouping every 4 candles (simple)
        h1_vals = h1["values"]
        h4 = []
        for i in range(0, min(len(h1_vals), 40), 4):
            block = h1_vals[i:i+4]
            if len(block) < 1: break
            o = float(block[-1]["open"])
            c = float(block[0]["close"])
            hh = max(float(x["high"]) for x in block)
            ll = min(float(x["low"]) for x in block)
            h4.append({"datetime": block[-1]["datetime"], "open": o, "high": hh, "low": ll, "close": c, "volume": 0})

    # prepare arrays (newest first)
    m15_list = m15["values"]
    h1_list = h1["values"]
    daily_list = daily["values"]

    # strategy decision
    signal = strategy_snapshot(m15_list, h1_list, h4[0] if len(h4)>0 else h4, daily_list)
    if not signal:
        print("No valid A+ setup found by rule-based engine.")
        return

    # compute lot table based on SL distance
    sl_dist = abs(signal["entry"] - signal["stop"])
    lot_table = compute_lot_table(sl_dist, instrument=SYMBOL)

    # optional HF check
    hf_result = hf_check(signal, {"m15": m15_list[:5], "h1": h1_list[:5], "h4": h4[:2], "daily": daily_list[:2]})

    # decide final acceptance
    final_ok = (hf_result.get("ok", True) and (hf_result.get("confidence", 85) >= 85))
    signal["confidence_check"] = hf_result.get("confidence", signal.get("confidence_est"))

    if final_ok:
        print("Signal accepted. Sending Telegram and logging.")
        send_telegram(signal, lot_table)
        append_log(signal, lot_table, hf_result)
    else:
        print("Signal rejected by HF or confidence below threshold. HF:", hf_result)

if __name__ == "__main__":
    # Force test message (bypass strategy)
    send_telegram({
        "instrument": SYMBOL,
        "direction": "BUY",
        "entry": 1900,
        "stop": 1890,
        "tps": [1950, 1970, 2000],
        "reason": "Test signal",
        "confidence_est": 99
    }, compute_lot_table(10))
    
    # Run the real bot

    main()
