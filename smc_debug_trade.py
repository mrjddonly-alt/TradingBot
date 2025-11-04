"""
smc_debug_trade.py
Debug MT5 connection and trade execution issues.
"""

import MetaTrader5 as mt5

ACCOUNT  = 5039796656
PASSWORD = "E!B0BnPx"
SYMBOL   = "GBPUSD"
LOT_SIZE = 0.1

print("🔄 Initializing MT5...")
if not mt5.initialize():
    print("❌ init failed:", mt5.last_error())
    quit()

info = mt5.account_info()
if info is None:
    print("❌ account_info() is None. Error:", mt5.last_error())
    mt5.shutdown()
    quit()

print(f"✅ Logged in MT5 terminal session -> Account: {info.login}, Server: {info.server}, TradeAllowed={info.trade_allowed}")

# Force re-login
if not mt5.login(ACCOUNT, PASSWORD, info.server):
    print("❌ Login failed:", mt5.last_error())
    mt5.shutdown()
    quit()
else:
    print("✅ Login confirmed in Python")

# --- Symbol check
if not mt5.symbol_select(SYMBOL, True):
    print(f"❌ Cannot select {SYMBOL}. Error:", mt5.last_error())
    mt5.shutdown()
    quit()
else:
    print(f"✅ Symbol {SYMBOL} is ready")

# --- Try sending a micro test order
tick = mt5.symbol_info_tick(SYMBOL)
if not tick:
    print("❌ No tick data. Error:", mt5.last_error())
    mt5.shutdown()
    quit()

price = tick.ask
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": SYMBOL,
    "volume": LOT_SIZE,
    "type": mt5.ORDER_TYPE_BUY,
    "price": price,
    "deviation": 50,
    "magic": 999,
    "comment": "DEBUG TEST",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_FOK,
}

print("📤 Sending test BUY...")
result = mt5.order_send(request)

print("📑 Result object:", result)
print("📌 Last error:", mt5.last_error())

mt5.shutdown()
