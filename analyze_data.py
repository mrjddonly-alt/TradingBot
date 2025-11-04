import pandas as pd
import mplfinance as mpf

# Load data
df = pd.read_csv("GBPUSD_M15_last480.csv")

# Prepare data
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

# Clean candlestick chart (no indicators)
mpf.plot(
    df,
    type='candle',
    style='charles',      # Clean style
    title='GBPUSD M15 - Price Action',
    ylabel='Price',
    volume=False,         # No volume bars
    figsize=(12, 6)
)
