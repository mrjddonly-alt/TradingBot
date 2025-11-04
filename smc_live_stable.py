"""
smc_live_demo_risk.py
Stable base bot for MT5 demo using Smart Money Concepts (SMC) logic.
"""

import MetaTrader5 as mt5
import time

# --------------------
# CONFIG
# --------------------
ACCOUNT   = 5039796656          # 🔑 replace with your demo account number
PASSWORD  = "E!B0BnPx"          # 🔑 replace with your demo password
SERVER    = "MetaQuotes-Demo"   # 🔑 replace with your broker's server name
SYMBOL    = "GBPUSD"
LOT_SIZE  = 0.1
SL_PIPS   = 15
TP_PIPS   = 30
MAGIC     = 123456              # unique ID for your bot's trades


# --------------------
# MT5 LOGIN
# --------------------
print("🔄 Initializing MT5...")
if not mt5.initialize():
    print("❌ MT5 initialization failed:", mt5.last_error())
    quit()

if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed:", mt5.last_error())
    mt5.shutdown()
    quit()

account_info = mt5.account_info()
print(f"✅ Logged in: {account_info.name} | Balance: {account_info.balance} | Server: {account_info.server}")


# --------------------
# ORDER FUNCTION
# --------------------
def place_order(symbol, lot, order_type, sl_pips, tp_pips):
    """Place a BUY/SELL order with SL & TP"""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("❌ Failed to get symbol tick:", mt5.last_error())
        return None

    price = tick.ask if order_type == "buy" else tick.bid
    point = mt5.symbol_info(symbol).point
    deviation = 20

    sl = price - sl_pips * point if order_type == "buy" else price + sl_pips * point
    tp = price + tp_pips * point if order_type == "buy" else price - tp_pips * point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": deviation,
        "magic": MAGIC,
        "comment": "SMC Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    print(f"📤 Sending {order_type.upper()} order at {price}")
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("❌ Order failed:", result)
    else:
        print(f"✅ {order_type.upper()} order placed! SL={sl}, TP={tp}")


# --------------------
# MAIN LOOP
# --------------------
print("🚀 Starting live SMC bot with risk management...")

try:
    while True:
        print("📊 Checking for SMC setups...")

        # For now: test BUY order
        place_order(SYMBOL, LOT_SIZE, "buy", SL_PIPS, TP_PIPS)

        # Exit after first trade (remove later for continuous logic)
        break  

        time.sleep(5)

except KeyboardInterrupt:
    print("🛑 Bot stopped manually.")

finally:
    mt5.shutdown()
    print("🔒 MT5 shutdown complete.")
