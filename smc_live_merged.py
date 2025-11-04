"""
smc_live_merged.py
Stable base bot merging debug trade success into main SMC bot structure.
"""

import MetaTrader5 as mt5
import time
from datetime import datetime

# --------------------
# CONFIG
# --------------------
ACCOUNT   = 5039796656          # replace with your demo account number
PASSWORD  = "E!B0BnPx"          # replace with your demo password
SERVER    = "MetaQuotes-Demo"   # your broker's server
SYMBOL    = "GBPUSD"
LOT_SIZE  = 0.1
SL_PIPS   = 15
TP_PIPS   = 30
MAGIC     = 123456              # unique ID for your bot's trades

# --------------------
# Logging helpers
# --------------------
def now(): 
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"{now()} | {msg}")

# --------------------
# MT5 Login
# --------------------
def init_mt5():
    log("🔄 Initializing MT5...")
    if not mt5.initialize():
        log(f"❌ MT5 initialization failed: {mt5.last_error()}")
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

    log(f"✅ Logged in: Account={ai.login}, Balance={ai.balance}, Server={ai.server}, TradeAllowed={ai.trade_allowed}")
    return True

# --------------------
# Symbol check
# --------------------
def ensure_symbol(symbol):
    si = mt5.symbol_info(symbol)
    if si is None:
        log(f"❌ Symbol {symbol} not found")
        return False, None
    if not si.visible:
        log(f"📌 {symbol} not visible. Enabling symbol...")
        if not mt5.symbol_select(symbol, True):
            log(f"❌ Failed to enable {symbol}")
            return False, si
    log(f"✅ Symbol {symbol} ready")
    return True, si

# --------------------
# Place order function
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        log(f"❌ Failed to get tick for {symbol}: {mt5.last_error()}")
        return None

    price = tick.ask if order_type=="buy" else tick.bid
    point = mt5.symbol_info(symbol).point
    deviation = 20
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
        "deviation": deviation,
        "magic": MAGIC,
        "comment": "SMC Bot Merged",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    log(f"📤 Sending {order_type.upper()} order at price {price}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE and result.retcode != 1:
        log(f"❌ Order failed: {result} | last_error={mt5.last_error()}")
        return None

    log(f"✅ {order_type.upper()} order placed! Price={price}, SL={sl}, TP={tp}")
    return result

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

    try:
        log("🚀 Starting live SMC bot with risk management...")
        # Test order once to confirm everything works
        place_order(SYMBOL, LOT_SIZE, "buy", SL_PIPS, TP_PIPS)

        # Continuous loop placeholder
        while True:
            log("📊 Checking for SMC setups... (replace with real SMC logic)")
            time.sleep(5)  # wait before checking again

    except KeyboardInterrupt:
        log("🛑 Bot stopped manually.")
    finally:
        mt5.shutdown()
        log("🔒 MT5 shutdown complete.")

if __name__ == "__main__":
    main()
