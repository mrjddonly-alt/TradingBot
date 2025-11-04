import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates

# ======================================
# 1️⃣ Load Trades CSV
# ======================================
trades_file = "USTEC_trades.csv"
try:
    df = pd.read_csv(trades_file)
    print("✅ Trades file loaded successfully!")
except FileNotFoundError:
    print("❌ Could not find", trades_file)
    exit()

# Normalize timestamp column
if 'timestamp_entry' in df.columns:
    print("⚠️ Using 'timestamp_entry' as 'timestamp'")
    df['timestamp'] = pd.to_datetime(df['timestamp_entry'])
elif 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
else:
    print("❌ No timestamp column found.")
    exit()

df['date_only'] = df['timestamp'].dt.date

# ======================================
# 2️⃣ Summarize Daily Performance
# ======================================
summary = df.groupby('date_only').agg(
    num_trades=('timestamp', 'count'),
    wins=('outcome', lambda x: (x == 'TP').sum()),
    total_pips=('result_pips', 'sum'),
)
summary['profit_per_trade'] = summary['total_pips'] / summary['num_trades']
summary['win_rate'] = summary['wins'] / summary['num_trades']
print("\n📊 Daily Summary:")
print(summary)

# ======================================
# 3️⃣ Load Candle Data
# ======================================
candles_file = "USTEC_candles.csv"
try:
    candles = pd.read_csv(candles_file)
    candles['time'] = pd.to_datetime(candles['time'])
    candles['date_only'] = candles['time'].dt.date
    print(f"✅ Candle data loaded with {len(candles)} rows")
except FileNotFoundError:
    print("⚠️ No candle data found — skipping chart.")
    candles = None

# ======================================
# 4️⃣ Pick Best Day (Trades + Candles)
# ======================================
best_day = None
if candles is not None:
    trade_days = df['date_only'].unique()
    candle_days = candles['date_only'].unique()
    common_days = np.intersect1d(trade_days, candle_days)

    if len(common_days) == 0:
        print("⚠️ No overlapping days between trades and candle data.")
    else:
        summary_common = summary.loc[summary.index.isin(common_days)]
        best_day = summary_common['profit_per_trade'].idxmax()
        print(f"\n🔥 Best day for detailed analysis: {best_day}")

# ======================================
# 5️⃣ Compute VWAP + ATR
# ======================================
if candles is not None:
    for col in ['open', 'high', 'low', 'close']:
        candles[col] = candles[col].astype(float)

    # VWAP
    candles['typical_price'] = (candles['high'] + candles['low'] + candles['close']) / 3
    candles['cum_vol_price'] = (candles['typical_price'] * candles['tick_volume']).cumsum()
    candles['cum_vol'] = candles['tick_volume'].cumsum()
    candles['VWAP'] = candles['cum_vol_price'] / candles['cum_vol']

    # ATR (14-period)
    high_low = candles['high'] - candles['low']
    high_close = np.abs(candles['high'] - candles['close'].shift())
    low_close = np.abs(candles['low'] - candles['close'].shift())
    candles['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    candles['ATR'] = candles['TR'].rolling(window=14).mean()

# ======================================
# 6️⃣ Plot Trades + VWAP + ATR for Best Day
# ======================================
if best_day is not None and candles is not None:
    candle_day = candles[candles['date_only'] == pd.to_datetime(best_day).date()]
    trades_day = df[df['date_only'] == pd.to_datetime(best_day).date()]

    if not candle_day.empty and not trades_day.empty:
        plt.figure(figsize=(14, 7))
        plt.plot(candle_day['time'], candle_day['close'], label='Close', color='grey', linewidth=1)
        plt.plot(candle_day['time'], candle_day['VWAP'], label='VWAP', color='blue', linewidth=2)
        plt.plot(candle_day['time'], candle_day['VWAP'] + candle_day['ATR'], '--', color='orange', label='VWAP + ATR')
        plt.plot(candle_day['time'], candle_day['VWAP'] - candle_day['ATR'], '--', color='orange', label='VWAP - ATR')

        # Plot trades
        for _, t in trades_day.iterrows():
            color = 'green' if t['outcome'] == 'TP' else ('red' if t['outcome'] == 'SL' else 'yellow')
            plt.scatter(t['timestamp'], t['entry_price'], color=color, s=50, edgecolor='black')
            plt.text(t['timestamp'], t['entry_price'], f"{t['result_pips']:.1f}", fontsize=8,
                     ha='center', va='bottom', color=color)

        plt.title(f"Trades + VWAP + ATR — {best_day}")
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.show()
    else:
        print(f"⚠️ No candle or trade data for {best_day}.")
else:
    print("⚠️ Skipping chart — best day not found or candle data missing.")
