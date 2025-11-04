"""
Advanced Multi-Pair SMC Bot with M1 Confirmation:
- M15 analysis for SMC zones: FVG, Liquidity Grab, Order Block
- Execute trades on M1 only when price touches detected zones
- Risk management with SL/TP and cooldown per symbol
- Dynamic filling mode detection
- CSV logging for trades and detected zones
"""

import MetaTrader5 as mt5
import time
from datetime import datetime
import csv
import os

# --------------------
# CONFIG
# --------------------
ACCOUNT   = 5039796656
PASSWORD  = "E!B0BnPx"
SERVER    = "MetaQuotes-Demo"
SYMBOLS   = ["GBPUSD", "EURUSD", "XAUUSD"]
LOT_SIZE  = 0.1
SL_PIPS   = 15
TP_PIPS   = 30
MAGIC     = 123456
COOLDOWN  = 60  # seconds per symbol
ANALYSIS_TF = mt5.TIMEFRAME_M15
EXECUTION_TF = mt5.TIMEFRAME_M1
BARS_ANALYSIS = 100
LOG_FILE = "smc_trades_log.csv"

# --------------------
# Logging helpers
# --------------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"{now()} | {msg}")

def log_to_csv(data_dict):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=data_dict.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(data_dict)

# --------------------
# MT5 Init
# --------------------
def init_mt5():
    if not mt5.initialize():
        log(f"❌ MT5 init failed: {mt5.last_error()}")
        return False
    if not mt5.login(ACCOUNT, PASSWORD, SERVER):
        log(f"❌ Login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    ai = mt5.account_info()
    if ai is None:
        log(f"❌ Failed to get account info: {mt5.last_error()}")
        mt5.shutdown()
        return False
    log(f"✅ Logged in: Account={ai.login} | Balance={ai.balance} | TradeAllowed={ai.trade_allowed}")
    return True

def ensure_symbol(symbol):
    si = mt5.symbol_info(symbol)
    if si is None:
        log(f"❌ Symbol {symbol} not found")
        return False, None
    if not si.visible:
        if not mt5.symbol_select(symbol, True):
            log(f"❌ Failed to enable {symbol}")
            return False, si
    return True, si

def can_trade():
    ai = mt5.account_info()
    return ai.trade_allowed if ai else False

# --------------------
# Place order (dynamic filling mode)
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    tick = mt5.symbol_info_tick(symbol)
    si = mt5.symbol_info(symbol)
    if not tick or not si:
        log(f"❌ Failed to get symbol info/tick for {symbol}")
        return None

    price = tick.ask if order_type == "buy" else tick.bid
    point = si.point
    sl = price - sl_pips * point if order_type == "buy" else price + sl_pips * point
    tp = price + tp_pips * point if order_type == "buy" else price - tp_pips * point

    # Detect supported filling mode
    if si.filling_mode & mt5.ORDER_FILLING_FOK:
        filling = mt5.ORDER_FILLING_FOK
    elif si.filling_mode & mt5.ORDER_FILLING_IOC:
        filling = mt5.ORDER_FILLING_IOC
    elif si.filling_mode & mt5.ORDER_FILLING_RETURN:
        filling = mt5.ORDER_FILLING_RETURN
    else:
        log(f"❌ No supported filling mode found for {symbol}")
        return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "SMC Multi-Pair Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    log(f"📤 Sending {order_type.upper()} {symbol} price={price} sl={sl} tp={tp} volume={lot} (filling={filling})")
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"✅ {order_type.upper()} order placed for {symbol} at {price}")
        log_to_csv({
            "time": now(),
            "symbol": symbol,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp
        })
        return result
    else:
        log(f"❌ Order failed {symbol} retcode={result.retcode}, comment={result.comment}, last_error={mt5.last_error()}")
        return None

# --------------------
# Detect SMC Zones
# --------------------
def detect_smc_zones(symbol, bars=BARS_ANALYSIS, analysis_tf=ANALYSIS_TF):
    rates = mt5.copy_rates_from_pos(symbol, analysis_tf, 0, bars)
    if rates is None or len(rates) < 3:
        return None

    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    closes = [r['close'] for r in rates]
    opens = [r['open'] for r in rates]

    signal = None
    fvg_zone = None
    lb_zone = None
    ob_zone = None

    # FVG detection
    for i in range(1, len(rates)-1):
        if opens[i+1] > closes[i-1]:
            fvg_zone = (closes[i-1], opens[i+1])
        elif opens[i+1] < closes[i-1]:
            fvg_zone = (opens[i+1], closes[i-1])

    # Liquidity Grab detection
    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_candle = rates[-1]
    if last_candle['high'] > prev_high:
        lb_zone = (prev_high, last_candle['high'])
        signal = "sell"
    elif last_candle['low'] < prev_low:
        lb_zone = (last_candle['low'], prev_low)
        signal = "buy"

    # Order Block detection
    for i in range(len(rates)-2, -1, -1):
        if closes[i] < opens[i] and closes[i+1] > closes[i]:
            ob_zone = (lows[i], highs[i])
            if signal is None:
                signal = "buy"
            break
        elif closes[i] > opens[i] and closes[i+1] < closes[i]:
            ob_zone = (lows[i], highs[i])
            if signal is None:
                signal = "sell"
            break

    if signal:
        log_to_csv({
            "time": now(),
            "symbol": symbol,
            "signal": signal,
            "fvg_zone": fvg_zone,
            "liquidity_grab": lb_zone,
            "order_block": ob_zone
        })
        return {
            'signal': signal,
            'fvg': fvg_zone,
            'liquidity_grab': lb_zone,
            'order_block': ob_zone
        }
    return None

# --------------------
# Helper: Price inside zone
# --------------------
def is_price_in_zone(price, zone):
    if zone is None:
        return False
    low, high = zone
    return low <= price <= high

# --------------------
# Main Loop
# --------------------
def main():
    if not init_mt5():
        log("MT5 init/login failed. Exiting.")
        return

    # Ensure all symbols are visible
    for symbol in SYMBOLS:
        ok, _ = ensure_symbol(symbol)
        if not ok:
            log(f"Skipping {symbol} - not available")
    
    # Initialize last trade times per symbol
    last_trade_times = {sym: 0 for sym in SYMBOLS}

    try:
        log("🚀 Starting Multi-Pair SMC Bot...")

        while True:
            for symbol in SYMBOLS:
                smc_info = detect_smc_zones(symbol)
                current_time = time.time()

                if smc_info and can_trade() and current_time - last_trade_times[symbol] > COOLDOWN:
                    tick = mt5.symbol_info_tick(symbol)
                    current_price = tick.ask if smc_info['signal'] == 'buy' else tick.bid

                    inside_any = any(is_price_in_zone(current_price, z) for z in [
                        smc_info['fvg'], smc_info['order_block'], smc_info['liquidity_grab']
                   
