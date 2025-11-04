import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates

# ===============================
# 1️⃣ Load Week 2 Trades
# ===============================
trades_file = "USTEC_week2_trades.csv"
try:
    df_trades = pd.read_csv(trades_file)
    print("✅ Trades file loaded successfully!")
except FileNotFoundError:
    print("❌ Could not find", trades_file)
    exit()

# Normalize timestamp column
if 'timestamp_entry' in df_trades.columns:
    df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp_entry'])
elif 'timestamp' in df_trades.columns:
    df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
else:
    print("❌ No timestamp column found in trades file.")
    exit()

df_trades['date_only'] = df_trades['timestamp'].dt.date

# ===============================
# 2️⃣ Filter Week 2 Dates
# ===============================
start_week2 = pd.to_datetime("2025-10-13")
end_week2 = pd.to_datetime("2025-10-17 23:59:59")
df_week2 = df_trades[(df_trades['timestamp'] >= start_week2) & (df_trades['timestamp'] <= end_week2)]

if df_week2.empty:
    print(f"⚠️ No trades found for Week 2 ({start_week2.date()}–{end_week2.date()})")
else:
    # Summarize week
    summary = df_week2.groupby('date_only').agg(
        num_trades=('timestamp', 'count'),
        wins=('outcome', lambda x: (x == 'TP').sum()),
        total_pips=('result_pips', 'sum')
    )
    summary['profit_per_trade'] = summary['total_pips'] / summary['num_trades']
    summary['win_rate'] = summary['wins'] / summary['num_trades']

    print("\n📊 Daily Summary (Week 2):")
    print(summary)

    best_day = summary['profit_per_trade'].idxmax()
    print(f"\n🔥 Best day for detailed analysis: {best_day}")

# ===============================
# 3️⃣ Load Week 2 Candle Data
# ===============================
candles_file = "USTEC_week2_candles.csv"
try:
    df_candles = pd.read_csv(candles_file)
    df_candles['time'] = pd.to_datetime(df_candles['time'])
    df_candles['date_only'] = df_candles['time'].dt.date
    print(f"✅ Candle data loaded with {len(df_candles)} rows")
except FileNotFoundError:
    print(f"❌ Candle file {candles_file} not found.")
    df_candles = None

# ===============================
# 4️⃣ Compute VWAP + ATR
# ===============================
if df_candles is not None and not df_week2.empty:
    for col in ['open','high','low','close','tick_volume']:
        df_candles[col] = df_candles[col].astype(float)

    # Typical price for VWAP
    df_candles['typical_price'] = (df_candles['high'] + df_candles['low'] + df_candles['close']) / 3
    df_candles['cum_vol_price'] = (df_candles['typical_price'] * df_candles['tick_volume']).cumsum()
    df_candles['cum_vol'] = df_candles['tick_volume'].cumsum()
    df_candles['VWAP'] = df_candles['cum_vol_price'] / df_candles['cum_vol']

    # ATR 14-period
    high_low = df_candles['high'] - df_candles['low']
    high_close = np.abs(df_candles['high'] - df_candles['close'].shift())
    low_close = np.abs(df_candles['low'] - df_candles['close'].shift())
    df_candles['TR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df_candles['ATR'] = df_candles['TR'].rolling(14).mean()

# ===============================
# 5️⃣ Plot Trades + VWAP + ATR for Best Day
# ===============================
if df_candles is not None and not df_week2.empty:
    trades_best = df_week2[df_week2['date_only'] == pd.to_datetime(best_day).date()]
    candles_best = df_candles[df_candles['date_only'] == pd.to_datetime(best_day).date()]

    if candles_best.empty:
        print(f"⚠️ No candle data for {best_day}. Cannot plot chart.")
    else:
        plt.figure(figsize=(14,7))
        plt.plot(candles_best['time'], candles_best['close'], color='grey', linewidth=1, label='Close')
        plt.plot(candles_best['time'], candles_best['VWAP'], color='blue', linewidth=2, label='VWAP')
        plt.plot(candles_best['time'], candles_best['VWAP'] + candles_best['ATR'], '--', color='orange', label='VWAP + ATR')
        plt.plot(candles_best['time'], candles_best['VWAP'] - candles_best['ATR'], '--', color='orange', label='VWAP - ATR')

        # Plot trades
        for _, t in trades_best.iterrows():
            color = 'green' if t['outcome']=='TP' else ('red' if t['outcome']=='SL' else 'yellow')
            plt.scatter(t['timestamp'], t['entry_price'], color=color, s=50, edgecolor='black')
            plt.text(t['timestamp'], t['entry_price'], f"{t['result_pips']:.1f}", fontsize=8,
                     ha='center', va='bottom', color=color)

        plt.title(f"Week 2 Trades + VWAP + ATR — {best_day}")
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.tight_layout()
        plt.show()
else:
    print("⚠️ Skipping visualization — trades or candle data missing.")
