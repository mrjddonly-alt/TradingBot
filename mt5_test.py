import MetaTrader5 as mt5

print("Initializing MT5...")
if not mt5.initialize():
    print("❌ MT5 init failed:", mt5.last_error())
    exit()

print("Logging in...")
if mt5.login(5039796656, "E!B0BnPx", "MetaQuotes-Demo"):
    print("✅ Logged in")
else:
    print("❌ Login failed:", mt5.last_error())

ai = mt5.account_info()
if ai:
    print("Account info:", ai.login, ai.balance, "TradeAllowed:", ai.trade_allowed)
else:
    print("❌ Failed to get account info")

mt5.shutdown()
