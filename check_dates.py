import pandas as pd

trades = pd.read_csv("USTEC_trades.csv")
candles = pd.read_csv("USTEC_candles.csv")

# Detect which column holds the date
if 'timestamp_entry' in trades.columns:
    trades['timestamp'] = pd.to_datetime(trades['timestamp_entry'])
elif 'timestamp' in trades.columns:
    trades['timestamp'] = pd.to_datetime(trades['timestamp'])
else:
    raise Exception("No timestamp column found in trades CSV")

candles['time'] = pd.to_datetime(candles['time'])

# Show unique trade days
print("🟩 Trade days:", sorted(trades['timestamp'].dt.date.unique()))
print("🟦 Candle days:", sorted(candles['time'].dt.date.unique()))
