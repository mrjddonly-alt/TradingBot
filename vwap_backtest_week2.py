import pandas as pd
import numpy as np
from itertools import product
import os

# ==========================
# Config
# ==========================
FILE =FILE = "C:/Users/mrjdd/OneDrive/Desktop/TradingBot/USTEC_1min.csv"
   # your exported MT5 file
START_WEEK2 = pd.Timestamp("2025-10-13 00:00:00")
END_WEEK2   = pd.Timestamp("2025-10-17 23:59:59")

# ==========================
# Utility functions
# ==========================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close  = np.abs(df['low']  - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_vwap(df):
    vol = np.where(df['volume'] == 0, df['tickvol'], df['volume'])
    df['cum_vol'] = vol.cumsum()
    df['cum_pv']  = (df['close'] * vol).cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    return df.drop(columns=['cum_vol','cum_pv'])

# ==========================
# Signal generation
# ==========================
def generate_signals(df, params):
    TP_mult   = params['TP_mult']
    SL_mult   = params['SL_mult']
    ATR_min   = params['ATR_min']
    VWAP_tol  = params['VWAP_tol']
    T_stop    = params['T_stop']

    trades = []

    for i in range(51, len(df) - T_stop - 1):
        row  = df.iloc[i]
        prev = df.iloc[i-1]

        if row['atr'] < ATR_min:
            continue

        # --- Long ---
        if row['close'] > row['vwap'] and row['ema20'] > row['ema50']:
            touch = abs(row['low'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
            momentum = row['close'] > prev['close']
            distance_ok = abs(row['close'] - row['ema20']) > 0.2 * row['atr']

            if touch and momentum and distance_ok:
                entry = row['close']
                TP = entry + TP_mult * row['atr']
                SL = entry - SL_mult * row['atr']
                future = df.iloc[i+1:i+T_stop]
                hit_TP = (future['high'] >= TP).any()
                hit_SL = (future['low'] <= SL).any()
                if hit_TP and not hit_SL:
                    outcome, result = "TP", TP - entry
                elif hit_SL and not hit_TP:
                    outcome, result = "SL", SL - entry
                else:
                    outcome, result = "TIMEOUT", 0
                trades.append({
                    "timestamp_entry": row['timestamp'],
                    "direction": "LONG",
                    "entry_price": entry,
                    "exit_price": entry + result,
                    "outcome": outcome,
                    "result_pips": result
                })

        # --- Short ---
        elif row['close'] < row['vwap'] and row['ema20'] < row['ema50']:
            touch = abs(row['high'] - row['vwap']) <= (row['vwap'] * VWAP_tol)
            momentum = row['close'] < prev['close']
            distance_ok = abs(row['close'] - row['ema20']) > 0.2 * row['atr']

            if touch and momentum and distance_ok:
                entry = row['close']
                TP = entry - TP_mult * row['atr']
                SL = entry + SL_mult * row['atr']
                future = df.iloc[i+1:i+T_stop]
                hit_TP = (future['low'] <= TP).any()
                hit_SL = (future['high'] >= SL).any()
                if hit_TP and not hit_SL:
                    outcome, result = "TP", entry - TP
                elif hit_SL and not hit_TP:
                    outcome, result = "SL", entry - SL
                else:
                    outcome, result = "TIMEOUT", 0
                trades.append({
                    "timestamp_entry": row['timestamp'],
                    "direction": "SHORT",
                    "entry_price": entry,
                    "exit_price": entry - result,
                    "outcome": outcome,
                    "result_pips": result
                })

    return pd.DataFrame(trades)

# ==========================
# Backtest
# ==========================
def backtest(df, param_grid):
    results = []
    for combo in param_grid:
        params = dict(zip(['TP_mult','SL_mult','ATR_min','VWAP_tol','T_stop'], combo))
        trades = generate_signals(df, params)
        if len(trades) == 0:
            continue
        num_trades = len(trades)
        wins = (trades['result_pips'] > 0).sum()
        win_rate = wins / num_trades
        expectancy = trades['result_pips'].mean()
        pf = trades[trades['result_pips']>0]['result_pips'].sum() / \
             abs(trades[trades['result_pips']<0]['result_pips'].sum() + 1e-6)
        results.append({
            **params,
            'num_trades': num_trades,
            'win_rate': round(win_rate,3),
            'expectancy': round(expectancy,3),
            'profit_factor': round(pf,2)
        })
    return pd.DataFrame(results).sort_values(by='expectancy', ascending=False)

# ==========================
# Load CSV (handle UTF-16 from MT5)
# ==========================
if not os.path.exists(FILE):
    print(f"❌ File '{FILE}' not found.")
    exit()

df = pd.read_csv(FILE, sep='\t', skiprows=1,
                 names=['date','time','open','high','low','close','tickvol','volume','spread'],
                 encoding='utf-8')  # change from utf-16 to utf-8


# Convert numeric
for col in ['open','high','low','close','tickvol','volume','spread']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Timestamp
df['date'] = df['date'].astype(str).str.strip()
df['time'] = df['time'].astype(str).str.strip()

df['timestamp'] = pd.to_datetime(
    df['date'] + ' ' + df['time'],
    format='%Y.%m.%d %H:%M:%S',
    errors='coerce'
)

# Drop rows where timestamp failed
df = df.dropna(subset=['timestamp'])

# Filter Week 2
df = df[(df['timestamp'] >= START_WEEK2) & (df['timestamp'] <= END_WEEK2)].copy()
if df.empty:
    print("❌ No data for Week 2 (2025-10-13 → 2025-10-17).")
    exit()
print(f"✅ Week 2 data loaded: {len(df)} rows")

# ==========================
# Indicators
# ==========================
df['ema20'] = ema(df['close'], 20)
df['ema50'] = ema(df['close'], 50)
df['atr']   = atr(df, 14)
df = compute_vwap(df)

# ==========================
# Parameter grid
# ==========================
TP_mults   = [1.5, 2.0]
SL_mults   = [1.0, 1.5]
ATR_mins   = [0.2, 0.5]
VWAP_tols  = [0.0008]
T_stops    = [50, 100]

param_grid = list(product(TP_mults, SL_mults, ATR_mins, VWAP_tols, T_stops))

# ==========================
# Run backtest
# ==========================
all_results = backtest(df, param_grid)
trades = generate_signals(df, dict(zip(['TP_mult','SL_mult','ATR_min','VWAP_tol','T_stop'],
                                       [1.5, 1.0, 0.2, 0.0008, 50])))

print(f"\n✅ Trades generated: {len(trades)}")
print(trades.head(10))

print("\n🔎 Top parameter sets:")
print(all_results.head(10))

# Save results
trades.to_csv("USTEC_week2_trades.csv", index=False)
df.to_csv("USTEC_week2_data.csv", index=False)
print("✅ Week 2 trades and data saved for analysis.")
