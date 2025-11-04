import MetaTrader5 as mt5

# Try to initialize MT5
if not mt5.initialize():
    print("❌ MT5 initialization failed")
else:
    print("✅ MT5 initialized successfully")

    # Check if account is logged in
    account_info = mt5.account_info()
    if account_info is None:
        print("❌ Not logged in")
    else:
        print(f"✅ Logged in: {account_info.login} | Balance={account_info.balance} | TradeAllowed={account_info.trade_allowed}")

    # Shutdown MT5 connection
    mt5.shutdown()
