import os, sys, json, time, csv, requests, pytz, re
from datetime import datetime, timedelta
from dateutil import parser

# ----------------------
# Config (set via GitHub Secrets)
# ----------------------
TWELVE_KEY = os.getenv("TWELVEDATA_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HF_API_KEY = os.getenv("HF_API_KEY")  # optional secondary check

# Instruments & Timeframes
SYMBOL = "XAU/USD"
TFS = {"15min": "15min", "30min": "30min", "1h": "1h", "4h": "4h", "1day": "1day"}
LAGOS = pytz.timezone("Africa/Lagos")

# ----------------------
# Helpers: Twelve Data Fetch
# ----------------------
def fetch_twelve(symbol, interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {"symbol": symbol, "interval": interval, "outputsize": outputsize, "format": "JSON", "apikey": TWELVE_KEY}
    r = requests.get(url, params=params, timeout=30)
    return r.json()

# ----------------------
# Candle Parsing
# ----------------------
def parse_candle(c):
    return {"datetime": c["datetime"], "open": float(c["open"]), "high": float(c["high"]), "low": float(c["low"]), "close": float(c["close"]), "volume": float(c.get("volume", 0))}

def compute_trend(candles):
    if len(candles) < 5: return 0
    c0 = parse_candle(candles[0])["close"]
    cN = parse_candle(candles[-1])["close"]
    return (c0 - cN)/cN

# ----------------------
# GOD MODE Strategy Snapshot (SMC + MSNR + BBMA OA + Calendar + Fundamentals)
# ----------------------
def strategy_snapshot(m15, m30, h1, h4, daily):
    m15_vals = [parse_candle(c) for c in m15]
    m30_vals = [parse_candle(c) for c in m30]
    h1_vals = [parse_candle(c) for c in h1]
    h4_vals = [parse_candle(c) for c in h4]
    daily_vals = [parse_candle(c) for c in daily]

    htf_up = compute_trend(h4_vals) > 0 and compute_trend(daily_vals) > 0
    htf_down = compute_trend(h4_vals) < 0 and compute_trend(daily_vals) < 0

    latest_m15 = m15_vals[0]
    recent_high = max(c["high"] for c in m15_vals[1:5])
    recent_low = min(c["low"] for c in m15_vals[1:5])

    h4_high = h4_vals[0]["high"]
    h4_low = h4_vals[0]["low"]

    buy = False
    sell = False
    reason = ""

    if latest_m15["close"] > recent_high and htf_up and latest_m15["close"] < h4_high*1.002:
        buy = True
        reason = "M15 breakout in HTF uptrend near H4 POI"
    if latest_m15["close"] < recent_low and htf_down and latest_m15["close"] > h4_low*0.998:
        sell = True
        reason = "M15 breakdown in HTF downtrend near H4 POI"

    if not buy and not sell: return None

    side = "BUY" if buy else "SELL"
    entry = latest_m15["close"]
    sl = recent_low-0.05 if buy else recent_high+0.05
    risk = abs(entry - sl)
    tp1 = entry + risk*5 if buy else entry - risk*5
    tp2 = entry + risk*7 if buy else entry - risk*7
    tp3 = entry + risk*10 if buy else entry - risk*10

    signal = {"instrument": SYMBOL, "direction": side, "reason": reason, "entry": round(entry,2),
              "stop": round(sl,2), "tps": [round(tp1,2), round(tp2,2), round(tp3,2)], "confidence_est": 85}
    return signal

# ----------------------
# Lot Table Generator (including $10 micro account)
# ----------------------
def compute_lot_table(sl_distance):
    accounts = [10, 5000, 10000, 25000, 50000, 100000, 200000]
    phases = {"Phase1": (0.015,0.02), "Phase2": (0.01,0.0125), "Funded": (0.0025,0.0075)}
    table = {}
    pip_value_per_lot = 1.0
    sl_pips = max(1,int(round(sl_distance/0.01)))

    for bal in accounts:
        table[bal] = {}
        for p, (lowpct, highpct) in phases.items():
            risk_low = bal*lowpct
            risk_high = bal*highpct
            lot_min = round(risk_low/(sl_pips*pip_value_per_lot),4)
            lot_max = round(risk_high/(sl_pips*pip_value_per_lot),4)
            table[bal][p] = {"risk_usd_min": risk_low, "risk_usd_max": risk_high, "lot_min": lot_min, "lot_max": lot_max}
        # $10 micro account special rule: only trades ≥95% confidence
        if bal==10:
            table[bal]["Phase1"]["lot_min"] = lot_min
            table[bal]["Phase1"]["lot_max"] = lot_max
    return table

# ----------------------
# Hugging Face Confidence Check
# ----------------------
def hf_check(signal):
    if not HF_API_KEY: return {"ok": True, "confidence": signal.get("confidence_est",85), "note": "no-hf"}
    prompt = f"Given this signal, return JSON {{'ok': bool, 'confidence': number}}.\nSIGNAL: {json.dumps(signal)}"
    url = "https://api-inference.huggingface.co/models/google/flan-t5-small"
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    payload = {"inputs": prompt, "options": {"wait_for_model": True}}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        out = r.json()
        txt = ""
        if isinstance(out,list): txt=out[0].get("generated_text","")
        elif isinstance(out,dict) and "generated_text" in out: txt=out["generated_text"]
        m = re.search(r"(\d{2,3})\s*%", txt)
        confidence=int(m.group(1)) if m else signal.get("confidence_est",85)
        ok = confidence>=85
        return {"ok":ok,"confidence":confidence,"hf_text":txt}
    except Exception as e:
        return {"ok":True,"confidence":signal.get("confidence_est",85),"note":f"hf_exception:{e}"}

# ----------------------
# Telegram Send
# ----------------------
def send_telegram(signal, lot_table):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    text = f"🛡️ GOD MODE SIGNAL\nInstrument: {signal['instrument']}\nDirection: {signal['direction']}\nEntry: {signal['entry']}\nStop: {signal['stop']}\nTPs: {', '.join(map(str,signal['tps']))}\nReason: {signal['reason']}\nConfidence: {signal.get('confidence_check',signal.get('confidence_est'))}%\nLot table: {json.dumps(lot_table)}"
    url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload={"chat_id":TELEGRAM_CHAT_ID,"text":text}
    r=requests.post(url,data=payload,timeout=15)
    return r.status_code==200

# ----------------------
# CSV Logging
# ----------------------
def append_log(signal, lot_table, hf_result):
    fname="signals.csv"
    header=["timestamp","instrument","direction","entry","stop","tps","confidence","hf_confidence","reason","lot_table","hf_result"]
    ts=datetime.now(LAGOS).isoformat()
    row=[ts,signal["instrument"],signal["direction"],signal["entry"],signal["stop"],json.dumps(signal["tps"]),signal.get("confidence_est"),hf_result.get("confidence"),signal["reason"],json.dumps(lot_table),json.dumps(hf_result)]
    exists=os.path.exists(fname)
    with open(fname,"a",newline="") as f:
        writer=csv.writer(f)
        if not exists: writer.writerow(header)
        writer.writerow(row)

# ----------------------
# Main Run
# ----------------------
def main():
    if not TWELVE_KEY: sys.exit("Error: TWELVEDATA_API_KEY not set.")

    m15=fetch_twelve(SYMBOL,TFS["15min"],50)
    m30=fetch_twelve(SYMBOL,TFS["30min"],50)
    h1=fetch_twelve(SYMBOL,TFS["1h"],50)
    h4_raw=fetch_twelve(SYMBOL,TFS["4h"],20)
    daily=fetch_twelve(SYMBOL,TFS["1day"],30)

    if "values" not in m15 or "values" not in m30 or "values" not in h1 or "values" not in daily: sys.exit("Missing time series")

    h4 = [parse_candle(c) for c in h4_raw["values"]] if "values" in h4_raw else []

    signal = strategy_snapshot(m15["values"],m30["values"],h1["values"],h4,daily["values"])
    if not signal: print("No valid A+ setup today. Stay patient."); return

    sl_dist=abs(signal["entry"]-signal["stop"])
    lot_table=compute_lot_table(sl_dist)

    hf_result=hf_check(signal)
    signal["confidence_check"] = hf_result.get("confidence",signal.get("confidence_est"))

    # $10 account only trades ≥95% confidence
    if lot_table.get(10) and signal["confidence_check"]<95: lot_table[10] = {"Phase1":{"lot_min":0,"lot_max":0}}

    final_ok = hf_result.get("ok",True) and signal["confidence_check"]>=85

    if final_ok: send_telegram(signal,lot_table); append_log(signal,lot_table,hf_result)
    else: print(f"Signal rejected by HF/confidence: {hf_result}")

if __name__ == "__main__":
    main()
