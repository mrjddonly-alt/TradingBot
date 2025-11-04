import MetaTrader5 as mt5

ACCOUNT   = 5039796656          # replace with your account
PASSWORD  = "E!B0BnPx"    # replace with your password
SERVER    = "MetaQuotes-Demo"   # replace with broker’s server name

print("🔄 Initializing MT5...")
if not mt5.initialize():
    print("❌ MT5 initialization failed:", mt5.last_error())
    quit()

if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed:", mt5.last_error())
    mt5.shutdown()
    quit()
else:
    print(f"✅ Logged in to account {ACCOUNT} on {SERVER}")

mt5.shutdown()
