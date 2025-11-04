"""
smc_live_m15_m1.py
SMC Live Bot:
- Analyze M15 for Smart Money Concepts (Break of Structure)
- Execute trades on M1
- Risk management with SL/TP and cooldown
- Verbose logging
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
ANALYSIS_TF = mt5.TIMEFRAME_M15  # Higher timeframe for SMC
EXECUTION_TF = mt5.TIMEFRAME_M1  # Execution timeframe

# --------------------
# Logging helpers
# --------------------
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"{now()} | {msg}")

# --------------------
# MT5 Initialization
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
# Place order function
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
        "comment": "SMC Bot M15-M1",
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
# SMC detection function on M15
# --------------------
def detect_smc(symbol, analysis_tf=ANALYSIS_TF, bars=50):
    """
    Detects simple break of structure on higher timeframe (M15)
    Returns 'buy', 'sell', or None
    """
    rates = mt5.copy_rates_from_pos(symbol, analysis_tf, 0, bars)
    if rates is None or len(rates) < 3:
        return None

    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]
    closes = [r['close'] for r in rates]

    last_close = closes[-1]
    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])

    if last_close > prev_high:
        return "buy"
    if last_close < prev_low:
        return "sell"
    return None

# --------------------
# Main loop
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
        log("🚀 Starting live SMC bot with risk management...")

        while True:
            smc_signal = detect_smc(SYMBOL, analysis_tf=ANALYSIS_TF)
            current_time = time.time()

            if smc_signal and can_trade() and current_time - last_trade_time > COOLDOWN:
                log(f"💡 SMC setup detected on M15: {smc_signal.upper()} — executing on M1")
                place_order(SYMBOL, LOT_SIZE, smc_signal, SL_PIPS, TP_PIPS)
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
