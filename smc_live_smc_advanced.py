"""
smc_live_smc_advanced.py
Advanced SMC Bot:
- M15 analysis for SMC zones: FVG, Liquidity Grab, Order Block
- M1 execution for precise entries
- Risk management with SL/TP and cooldown
- Verbose logging for all detected zones
"""

import MetaTrader5 as mt5
import time
from datetime import datetime

# --------------------
# CONFIG
# --------------------
ACCOUNT   = 5039796656
PASSWORD  = "E!B0BnPx"
SERVER    = "MetaQuotes-Demo"
SYMBOL    = "GBPUSD"
LOT_SIZE  = 0.1
SL_PIPS   = 15
TP_PIPS   = 30
MAGIC     = 123456
COOLDOWN  = 60  # seconds between trades
ANALYSIS_TF = mt5.TIMEFRAME_M15
EXECUTION_TF = mt5.TIMEFRAME_M1
BARS_ANALYSIS = 100  # M15 candles to scan

# --------------------
# Logging helpers
# --------------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"{now()} | {msg}")

# --------------------
# MT5 Init and Symbol Check
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
# Place order
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        log(f"❌ Failed to get tick for {symbol}")
        return None

    price = tick.ask if order_type=="buy" else tick.bid
    point = mt5.symbol_info(symbol).point
    sl = price - sl_pips*point if order_type=="buy" else price + sl_pips*point
    tp = price + tp_pips*point if order_type=="buy" else price - tp_pips*point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type=="buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": MAGIC,
        "comment": "SMC Advanced Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    log(f"📤 Sending {order_type.upper()} at price {price}")
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE and result.retcode != 1:
        log(f"❌ Order failed: {result} | last_error={mt5.last_error()}")
        return None
    log(f"✅ {order_type.upper()} order placed! Price={price} | SL={sl} | TP={tp}")
    return result

# --------------------
# SMC Zone Detection (FVG, Liquidity Grab, Order Block)
# --------------------
def detect_smc_zones(symbol, bars=BARS_ANALYSIS, analysis_tf=ANALYSIS_TF):
    """
    Detects SMC signals on M15:
    - FVG (Fair Value Gap)
    - Liquidity Grab
    - Order Block
    Returns dict with signal info or None
    """
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

    # --------------------
    # Detect Fair Value Gap (FVG)
    # --------------------
    for i in range(1, len(rates)-1):
        # bullish FVG: gap between low of current and high of previous candle
        if opens[i+1] > closes[i-1]:
            fvg_zone = (closes[i-1], opens[i+1])
        # bearish FVG: gap between high of current and low of previous candle
        elif opens[i+1] < closes[i-1]:
            fvg_zone = (opens[i+1], closes[i-1])

    # --------------------
    # Detect Liquidity Grab (stop hunt wicks)
    # --------------------
    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_candle = rates[-1]

    # wick above previous high -> buy liquidity grab
    if last_candle['high'] > prev_high:
        lb_zone = (prev_high, last_candle['high'])
        signal = "sell"  # price likely reverses down
    # wick below previous low -> sell liquidity grab
    elif last_candle['low'] < prev_low:
        lb_zone = (last_candle['low'], prev_low)
        signal = "buy"  # price likely reverses up

    # --------------------
    # Detect Order Block (last opposite candle before move)
    # --------------------
    # simple heuristic: last bearish candle before bullish breakout
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
        return {
            'signal': signal,
            'fvg': fvg_zone,
            'liquidity_grab': lb_zone,
            'order_block': ob_zone
        }
    return None

# --------------------
# Main Loop
# --------------------
def main():
    if not init_mt5():
        log("MT5 init/login failed. Exiting.")
        return

    ok, _ = ensure_symbol(SYMBOL)
    if not ok:
        log("Symbol check failed. Exiting.")
        mt5.shutdown()
        return

    last_trade_time = 0

    try:
        log("🚀 Starting Advanced SMC Bot with risk management...")

        while True:
            smc_info = detect_smc_zones(SYMBOL)
            current_time = time.time()

            if smc_info and can_trade() and current_time - last_trade_time > COOLDOWN:
                log(f"💡 SMC Signal Detected: {smc_info['signal'].upper()}")
                log(f"📌 FVG Zone: {smc_info['fvg']}")
                log(f"📌 Liquidity Grab Zone: {smc_info['liquidity_grab']}")
                log(f"📌 Order Block Zone: {smc_info['order_block']}")
                place_order(SYMBOL, LOT_SIZE, smc_info['signal'], SL_PIPS, TP_PIPS)
                last_trade_time = current_time
            else:
                log("📊 No SMC setup detected or waiting cooldown...")

            time.sleep(5)

    except KeyboardInterrupt:
        log("🛑 Bot stopped manually.")
    finally:
        mt5.shutdown()
        log("🔒 MT5 shutdown complete.")

if __name__ == "__main__":
    main()
