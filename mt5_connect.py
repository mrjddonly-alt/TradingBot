import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# ============================
# 1) Connect to MT5
# ============================
if not mt5.initialize():
    print("MT5 initialization failed:", mt5.last_error())
    raise SystemExit

account_info = mt5.account_info()
if not account_info:
    print("Failed to get account info:", mt5.last_error())
    mt5.shutdown()
    raise SystemExit
print(f"Connected to account: {account_info.login}")
print(f"Balance: {account_info.balance}")

# ============================
# 2) Choose symbol, timeframe, bars
# ============================
symbol = "GBPUSD"               # Currency pair
timeframe = mt5.TIMEFRAME_M15    # 15-minute timeframe
bars = 480                      # Number of candles

# Make sure symbol is visible in MT5 Market Watch
if not mt5.symbol_select(symbol, True):
    print(f"Failed to select {symbol}. Please add it to Market Watch.")
    mt5.shutdown()
    raise SystemExit

# ============================
# 3) Fetch historical data
# ============================
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
if rates is None or len(rates) == 0:
    print("No data returned:", mt5.last_error())
    mt5.shutdown()
    raise SystemExit

# ============================
# 4) Format data into a table
# ============================
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")
df = df.rename(columns={
    "open": "Open", "high": "High", "low": "Low", "close": "Close",
    "tick_volume": "TickVolume", "spread": "Spread", "real_volume": "RealVolume"
})
df = df[["time", "Open", "High", "Low", "Close", "TickVolume", "Spread", "RealVolume"]]

# ============================
# 5) Show and save data
# ============================
print("\nLast 10 candles:")
print(df.tail(10).to_string(index=False))

csv_name = f"{symbol}_M15_last{bars}.csv"
df.to_csv(csv_name, index=False)
print(f"\nSaved: {csv_name}")

# ============================
# 6) Close MT5 connection
# ============================
mt5.shutdown()
